"""Physically reviewed native notes must retain their complete source groups.

Four original PDF pages retain their operators and page indices. Independent
source views qualify the six marker/citation pairs and neighboring authored
content. Producer note numbers and extraction adjacency are not the oracle.
"""
from collections import Counter
from dataclasses import asdict, fields, replace
from pathlib import Path
import copy
import hashlib
import json
import math

import pymupdf
from PIL import Image, ImageDraw
import pytest

from cps.services.reflow import extract, skeleton, transcript_regions
from tests.unit.test_reflow_physical_footer_canonical_delivery import raw_page, digest, is_note

pytestmark = pytest.mark.unit
FIXTURE = Path(__file__).parents[1] / 'fixtures/reflow/native_note_marker_context_complete.json'
PAGES = [34, 99, 100, 114]
GROUPS = [(34, 'l45', 'l44'), (99, 'l40', 'l38'), (99, 'l41', 'l39'),
          (100, 'l40', 'l38'), (100, 'l41', 'l39'), (114, 'l40', 'l39')]
TARGETS = [(page, row) for page, marker, citation in GROUPS for row in (marker, citation)]


def book_style(values):
    values = copy.deepcopy(values)
    for key, value in values.items():
        if isinstance(value, dict) and all(str(p).isdigit() for p in value):
            values[key] = {int(p): v for p, v in value.items()}
    accepted = {f.name for f in fields(skeleton.BookStyle)}
    return skeleton.BookStyle(**{k: v for k, v in values.items() if k in accepted})


def owners(result, row):
    return [region for region in result.regions
            if any(row is line for line in region.lines + region.caption_lines)]


@pytest.fixture(scope='module')
def actual_pages():
    fixture = json.loads(FIXTURE.read_text())
    path = FIXTURE.parent / fixture['source_pdf']['path']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == fixture['source_pdf']['sha256']
    measured = {}
    try:
        for page in PAGES:
            record = fixture['cases'][str(page)]
            assert record['physically_viewed']
            raw = raw_page(record['raw'])
            assert digest(asdict(raw)) == record['raw_sha256']
            assert raw.pno == page and raw.source_geometry == record['source_geometry']
            doc = pymupdf.open(path)
            measured[page] = (raw, {}, None, doc, record)
            assert list(doc[page].rect) == record['frame'] and doc[page].rotation == record['rotation']
            initial = doc[page].get_pixmap(matrix=pymupdf.Matrix(4, 4),
                colorspace=pymupdf.csGRAY, alpha=False)
            assert hashlib.sha256(initial.samples).hexdigest() == record['fullframe_bitmap_sha256']
            original = copy.deepcopy(record['original_provenance'])
            if 'source_pdf_sha256' in original.get('verification', {}):
                assert original['verification']['source_pdf_sha256'] == fixture['source_pdf']['original_sha256']
                original['verification']['source_pdf_sha256'] = fixture['source_pdf']['sha256']
            assert original == record['provenance'], 'Only the portable PDF fingerprint may be rebound'
            rows = {}
            for witness in record['source_rows']:
                row = raw.blocks[witness['block_index']].lines[witness['line_index']]
                assert digest(asdict(row)) == witness['source_row_sha256']
                assert json.loads(json.dumps(asdict(row))) == witness['source']
                assert row.text == witness['source_text'] and list(row.bbox) == witness['source_bbox']
                rows[witness['line_id']] = row
            before = asdict(raw)
            style = book_style(fixture['book_style'])
            probe = extract.ScanPixelProbe(doc, page,
                mask=[line.bbox for block in raw.text_blocks for line in block.lines])
            candidate = transcript_regions.candidate(raw, copy.deepcopy(record['provenance']),
                doc, style, pixel_probe=probe, layer_trusted=True) if raw.transcript_unverified else None
            if raw.transcript_unverified:
                assert candidate is not None, 'Mandatory source glyph coverage must remain qualified'
            result = candidate[0] if candidate else skeleton.page_skeleton(raw, style,
                pixel_probe=probe, layer_trusted=True)
            assert asdict(raw) == before, 'Preserve original source text, flags and geometry'
            measured[page] = (raw, rows, result, doc, record)
        yield measured
    finally:
        for _, _, _, doc, _ in measured.values():
            doc.close()


@pytest.mark.parametrize('page,line_id', TARGETS)
def test_each_physically_printed_marker_and_citation_has_one_note_owner(actual_pages, page, line_id):
    _, rows, result, _, _ = actual_pages[page]
    found = owners(result, rows[line_id])
    assert len(found) == 1 and is_note(found[0]), (page, line_id, [(r.kind, r.reason) for r in found])


@pytest.mark.parametrize('page,marker,citation', GROUPS)
def test_complete_note_pairs_preserve_measured_original_association(actual_pages, page, marker, citation):
    _, rows, result, _, record = actual_pages[page]
    found = owners(result, rows[marker])
    assert len(found) == 1 and is_note(found[0])
    region = found[0]
    assert any(rows[citation] is line for line in region.lines), (page, marker, citation)
    for other in record['note_groups']:
        if other['marker'] != marker:
            assert not any(rows[other['citation']] is line for line in region.lines), (
                'A source marker cannot claim its neighboring note citation', page, marker, other)
    for line_id in (marker, citation):
        assert all(a <= b + 1e-6 for a, b in zip(region.bbox[:2], rows[line_id].bbox[:2]))
        assert all(a >= b - 1e-6 for a, b in zip(region.bbox[2:], rows[line_id].bbox[2:]))
    # Original uncertainty may require number=None and a source-layout crop.
    # Ownership and association never depend on adopting a guessed digit.


@pytest.mark.parametrize('page,line_id', TARGETS)
def test_note_source_ink_is_excluded_from_every_main_body_artwork_crop(actual_pages, page, line_id):
    _, rows, result, doc, _ = actual_pages[page]
    wrong = []
    for region in result.regions:
        if region.kind not in ('figure', 'artwork') or is_note(region):
            continue
        common = pymupdf.Rect(rows[line_id].bbox) & pymupdf.Rect(region.bbox)
        if common.is_empty:
            continue
        pix = doc[page].get_pixmap(clip=common, matrix=pymupdf.Matrix(4, 4),
            colorspace=pymupdf.csGRAY, alpha=False)
        ink = sum(v < 200 for v in pix.samples)
        if ink > 2:
            wrong.append((region.kind, region.reason, ink, list(common)))
    assert not wrong, (page, line_id, wrong)


@pytest.mark.parametrize('page', PAGES)
def test_every_original_source_row_is_retained_exactly_once(actual_pages, page):
    raw, _, result, _, _ = actual_pages[page]
    expected = Counter(digest(asdict(line)) for block in raw.text_blocks for line in block.lines)
    actual = Counter(digest(asdict(line)) for region in result.regions
                     for line in region.lines + region.caption_lines)
    assert actual == expected, {'missing': expected-actual, 'duplicated': actual-expected}


@pytest.mark.parametrize('page', PAGES)
def test_original_page_and_all_note_bitmap_territories_remain_exact(actual_pages, page):
    _, _, _, doc, record = actual_pages[page]
    pix = doc[page].get_pixmap(matrix=pymupdf.Matrix(4, 4), colorspace=pymupdf.csGRAY, alpha=False)
    assert hashlib.sha256(pix.samples).hexdigest() == record['fullframe_bitmap_sha256']
    image = Image.frombytes('L', (pix.width, pix.height), pix.samples)
    for scope in record['note_bitmap_scopes']:
        crop = image.crop(scope['pixelbox'])
        assert list(crop.size) == scope['pixel_size']
        assert hashlib.sha256(crop.tobytes()).hexdigest() == scope['sha256']
        assert sum(v < 200 for v in crop.tobytes()) == scope['dark_pixels'] > 2


@pytest.mark.parametrize('page', PAGES)
def test_physically_authored_neighbors_remain_outside_notes_and_furniture(actual_pages, page):
    _, rows, result, _, record = actual_pages[page]
    for line_id in record['authored_context_ids']:
        found = owners(result, rows[line_id])
        assert len(found) == 1 and not is_note(found[0]) and found[0].kind != 'furniture', (
            page, line_id, [(r.kind, r.reason) for r in found])


@pytest.mark.parametrize('index', [0, 1])
def test_adjacent_physically_viewed_wheel_ink_keeps_a_source_figure_owner(actual_pages, index):
    _, _, result, doc, record = actual_pages[34]
    scope = record['art_support_scopes'][index]
    pix = doc[34].get_pixmap(matrix=pymupdf.Matrix(4, 4), colorspace=pymupdf.csGRAY, alpha=False)
    source = Image.frombytes('L', (pix.width, pix.height), pix.samples)
    box = pymupdf.Rect(scope['bbox'])
    pixelbox = [math.floor(box.x0*4)-pix.x, math.floor(box.y0*4)-pix.y,
                math.ceil(box.x1*4)-pix.x, math.ceil(box.y1*4)-pix.y]
    image = source.crop(pixelbox)
    mask = Image.new('L', image.size, 0)
    draw = ImageDraw.Draw(mask)
    for region in result.regions:
        if region.kind != 'figure' or is_note(region):
            continue
        common = box & pymupdf.Rect(region.bbox)
        if not common.is_empty:
            draw.rectangle((math.floor(common.x0*4)-pix.x-pixelbox[0],
                            math.floor(common.y0*4)-pix.y-pixelbox[1],
                            math.ceil(common.x1*4)-pix.x-pixelbox[0]-1,
                            math.ceil(common.y1*4)-pix.y-pixelbox[1]-1), fill=255)
    data, covered = image.tobytes(), mask.tobytes()
    ink = sum(v < 200 for v in data)
    retained = sum(v < 200 and covered[i] > 0 for i, v in enumerate(data))
    assert ink > 100 and retained/ink >= .99, (index, retained, ink)


@pytest.mark.parametrize('dx,dy', [(180, 0), (0, -80)])
def test_constructed_crossblock_marker_cannot_borrow_distant_or_wrong_column_citation(dx, dy):
    """Counterfactual source geometry; not a claim about an authored PDF page."""
    fixture = json.loads(FIXTURE.read_text())
    raw = raw_page(fixture['cases']['99']['raw'])
    marker = raw.blocks[7].lines[0]
    citation = raw.blocks[6].lines[1]
    shifted = lambda b: (b[0]+dx, b[1]+dy, b[2]+dx, b[3]+dy)
    spans = [replace(s, bbox=shifted(s.bbox), origin_y=s.origin_y+dy) for s in marker.spans]
    moved = replace(marker, bbox=shifted(marker.bbox), spans=spans)
    raw.blocks[7] = replace(raw.blocks[7], bbox=shifted(raw.blocks[7].bbox), lines=[moved])
    before = asdict(raw)
    result = skeleton.page_skeleton(raw, book_style(fixture['book_style']), layer_trusted=True)
    assert asdict(raw) == before
    assert not any(is_note(region) and any(moved is row for row in region.lines)
                   and any(citation is row for row in region.lines) for region in result.regions)
