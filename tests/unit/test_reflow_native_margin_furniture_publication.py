"""A native full-page figure must not publish a qualified contents folio.

The fixture is source-bound to the original PDF and final canonical source
inventory.  It exercises native-page furniture selection and the publisher's
actual image path; it does not use a prior EPUB crop as expected content.
"""
import copy
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from cps.services.reflow import build_epub, extract

pytestmark = pytest.mark.unit
FIXTURE = (Path(__file__).parent / 'fixtures' /
           'native_margin_furniture_publication' / 'book570_p0016')
SRC = 'images/fig_p0000_0.jpg'


def _fixture():
    manifest = json.loads((FIXTURE / 'fixture.json').read_text())
    raw_inventory = (FIXTURE / 'source_inventory.json').read_bytes()
    assert hashlib.sha256(raw_inventory).hexdigest() == manifest['source_inventory_sha256']
    inventory = json.loads(raw_inventory)
    row = next(row for row in inventory['lines'] if row['id'] == 'l58')
    role = next(region for region in inventory['regions']
                if region['id'] == 'r30')
    assert role['suggested_kind'] == 'furniture'
    assert role['reason'] == 'contents_footer_folio'
    assert role['line_ids'] == ['l58']
    assert row['sha256'] == manifest['qualified_furniture_role']['row_sha256']
    assert row['source']['spans'][0]['text'] == 'xv'
    return manifest, inventory


def _typed_inventory(raw):
    inventory = copy.deepcopy(raw)
    for row in inventory['lines']:
        source = row['source']
        spans = [extract.Span(**span) for span in source['spans']]
        row['source'] = extract.Line(spans, tuple(source['bbox']),
            source.get('spacing_uncertain', False),
            source.get('transcription_uncertain', False))
    return inventory


def _book(inventory):
    return SimpleNamespace(
        source_inventory={0: _typed_inventory(inventory)},
        figures=[dict(_fixture()[0]['canonical_figure'], pno=0)],
        pages={0: []}, notes=[], furniture=['xv'], source_region_protection={},
    )


def _opened_pdf():
    import fitz
    return fitz.open(stream=(FIXTURE / 'source_page.pdf').read_bytes(), filetype='pdf')


def _opened_wrong_prior_page_pdf():
    import fitz
    return fitz.open(stream=(FIXTURE / 'wrong_prior_page.pdf').read_bytes(),
                     filetype='pdf')


def _published(monkeypatch, book, doc, required=()):
    # Keep this test focused on the publication ownership transform.  Source
    # scan-edge discovery has its own tests and is not an input to the native
    # full-frame path.
    monkeypatch.setattr(extract, 'region_has_ink', lambda *args, **kwargs: True)
    monkeypatch.setattr(build_epub, '_source_scan_edges', lambda *args: [])
    monkeypatch.setattr('cps.services.reflow.crop_edges.trim_source_edges',
                        lambda data, *args, **kwargs: (data, [], False))
    monkeypatch.setattr('cps.services.reflow.crop_edges.trim_scan_borders',
                        lambda data: (data, []))

    class Package:
        def __init__(self):
            self.images = {}

        def image(self, src, data):
            self.images[src] = data

    package = Package()
    chapter = SimpleNamespace(blocks=['<img src="%s" />' % SRC])
    presentation = {}
    missing, blanks = build_epub._figure_images(
        [chapter], doc, book, package, required_source_regions=required,
        figure_presentation=presentation)
    assert missing == [] and blanks == []
    return package.images[SRC], presentation[SRC]


def _dark_pixels(data):
    image = Image.open(io.BytesIO(data)).convert('L')
    return image, [(x, y) for y in range(image.height) for x in range(image.width)
                   if image.getpixel((x, y)) < 180]


def test_canonical_native_margin_selector_owns_only_the_folio_component():
    manifest, inventory = _fixture()
    book = _book(inventory)
    with _opened_pdf() as doc:
        furniture, protected = build_epub._native_margin_furniture_pixel_boxes(
            doc, book, 0, book.figures[0])
    role = manifest['qualified_furniture_role']
    assert furniture == [tuple(role['bbox'])]
    assert tuple(role['bbox']) not in protected
    assert any(box != tuple(role['bbox']) for box in protected)
    assert book.source_inventory[0]['regions'] == inventory['regions']


def test_native_page_identity_mismatch_cannot_erase_a_different_folio():
    """The xv role must not authorize erasing the neighboring page's xiv."""
    manifest, inventory = _fixture()
    book = _book(inventory)
    with _opened_wrong_prior_page_pdf() as doc:
        assert doc.page_count == 1
        assert 'xiv' in doc[0].get_text()
        assert 'xv' not in doc[0].get_text()
        furniture, protected = build_epub._native_margin_furniture_pixel_boxes(
            doc, book, 0, book.figures[0])
    assert manifest['source_pdf_page_index'] == 16
    assert manifest['negative_control_pdf_page_index'] == 15
    assert manifest['qualified_furniture_role']['text'] == 'xv'
    assert furniture == []
    assert protected == []


def test_native_figure_publication_removes_folio_and_preserves_unowned_context(monkeypatch):
    manifest, inventory = _fixture()
    book = _book(inventory)
    with _opened_pdf() as doc:
        figure = book.figures[0]
        original = extract.crop_jpeg(doc, 0, figure['bbox'])
        published, presentation = _published(monkeypatch, book, doc)
    source, before = _dark_pixels(original)
    output, after = _dark_pixels(published)
    padding = presentation.get('reading_image_geometry', {}).get('padding', [0, 0, 0, 0])
    assert output.size == (source.width + padding[0] + padding[2],
                           source.height + padding[1] + padding[3])
    assert before and after
    # The source folio must leave the body image; no rectangular strip may be
    # cleared, and changes stay within the owned glyph plus its measured 3pt lane.
    x0, y0, x1, y1 = manifest['canonical_figure']['bbox']
    rx0, ry0, rx1, ry1 = manifest['qualified_furniture_role']['bbox']
    left = (rx0 - x0 - 3) * source.width / (x1 - x0)
    top = (ry0 - y0 - 3) * source.height / (y1 - y0)
    right = (rx1 - x0 + 3) * source.width / (x1 - x0)
    bottom = (ry1 - y0 + 3) * source.height / (y1 - y0)
    pad_left, pad_top = padding[:2]
    assert not any(left + pad_left <= x <= right + pad_left and
                   top + pad_top <= y <= bottom + pad_top and
                   output.getpixel((x, y)) < 180 for x, y in after)
    for y in range(source.height):
        for x in range(source.width):
            if left <= x <= right and top <= y <= bottom:
                continue
            assert source.getpixel((x, y)) == output.getpixel(
                (x + pad_left, y + pad_top)), (x, y)
    assert book.figures[0]['bbox'] == manifest['canonical_figure']['bbox']
    assert book.source_inventory[0]['sha256'] == inventory['sha256']


@pytest.mark.parametrize('damage', [
    'missing_geometry', 'mismatched_geometry', 'rotated', 'cropped_source',
    'partial_bitmap', 'native_vector_only', 'nonmargin_role', 'role_conflict',
    'body_overlap', 'note_overlap', 'required_resource',
])
def test_native_margin_furniture_fails_closed_without_exact_context(monkeypatch, damage):
    manifest, inventory = _fixture()
    book = _book(inventory)
    inv = book.source_inventory[0]
    role = next(region for region in inv['regions'] if region['id'] == 'r30')
    figure = book.figures[0]
    doc = _opened_pdf()
    try:
        if damage == 'missing_geometry':
            inv.pop('source_geometry')
        elif damage == 'mismatched_geometry':
            inv['source_geometry'] = {'space': 'reading'}
        elif damage == 'rotated':
            doc[0].set_rotation(90)
        elif damage == 'cropped_source':
            page = doc[0]
            page.set_cropbox((0, 0, page.rect.width - 1, page.rect.height))
        elif damage == 'partial_bitmap':
            inv['raw_images'][0]['bbox'][2] -= 2
            inv['raw_images'][0]['area_ratio'] = .98
        elif damage == 'native_vector_only':
            inv['raw_images'] = []
        elif damage == 'nonmargin_role':
            role['bbox'] = [role['bbox'][0], 300, role['bbox'][2], 308]
        elif damage == 'role_conflict':
            conflicting = copy.deepcopy(role)
            conflicting.update(id='r-conflict', suggested_kind='caption',
                               reason='figure_caption')
            inv['regions'].append(conflicting)
        elif damage == 'body_overlap':
            book.pages[0] = [SimpleNamespace(kind='p', bbox=tuple(role['bbox']),
                                             line_boxes=[tuple(role['bbox'])])]
        elif damage == 'note_overlap':
            book.notes = [SimpleNamespace(pno=0, bbox=tuple(role['bbox']))]
        if damage == 'required_resource':
            original = extract.crop_jpeg(doc, 0, figure['bbox'])
            output, _ = _published(monkeypatch, book, doc, required={SRC})
            assert output == build_epub._figure_crop_margin(original, figure)
            return
        owned, protected = build_epub._native_margin_furniture_pixel_boxes(
            doc, book, 0, figure)
        assert owned == [], damage
        assert protected == [], damage
    finally:
        doc.close()

