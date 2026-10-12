"""Six physically verified native note rows must reach the printed-note lane.

The original PDF operators, retained raw rows/flags and complete learned book
context are portable fixtures. Independent full-page and note-detail views
qualify these six rows; converter classifications are not the role oracle.
"""
from collections import Counter
from dataclasses import asdict, fields
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
FIXTURE = Path(__file__).parents[1] / 'fixtures/reflow/native_residual_printed_notes.json'
TARGETS = [(569, 'l23'), (569, 'l24'), (570, 'l28'), (570, 'l29'), (570, 'l30'), (570, 'l31')]


@pytest.fixture(scope='module')
def actual_pages():
    proof = json.loads(FIXTURE.read_text())
    measured = {}
    try:
        for bid, record in proof['cases'].items():
            book = int(bid)
            assert record['physically_viewed']
            raw = raw_page(record['raw'])
            assert digest(asdict(raw)) == record['raw_sha256']
            values = copy.deepcopy(record['book_style'])
            for key, value in values.items():
                if isinstance(value, dict) and all(str(p).isdigit() for p in value):
                    values[key] = {int(p): v for p, v in value.items()}
            for key in ('folio_boxes', 'local_running_boxes'):
                values[key] = {p: tuple(box) for p, box in values[key].items()}
            for key in ('repeated_head_boxes', 'portrait_head_boxes', 'scan_spread_head_boxes',
                        'scan_table_label_boxes', 'scan_note_lane_boxes'):
                values[key] = {p: [tuple(box) for box in boxes] for p, boxes in values[key].items()}
            accepted = {f.name for f in fields(skeleton.BookStyle)}
            style = skeleton.BookStyle(**{k: v for k, v in values.items() if k in accepted})
            path = FIXTURE.parent / record['source_pdf']['path']
            assert hashlib.sha256(path.read_bytes()).hexdigest() == record['source_pdf']['sha256']
            doc = pymupdf.open(path)
            measured[book] = (raw, {}, None, doc, record)
            page = record['page']
            assert raw.pno == page
            assert list(doc[page].rect) == record['frame'] and doc[page].rotation == record['rotation']
            assert raw.source_geometry == record['source_geometry']
            initial = doc[page].get_pixmap(matrix=pymupdf.Matrix(4, 4),
                colorspace=pymupdf.csGRAY, alpha=False)
            assert hashlib.sha256(initial.samples).hexdigest() == record['fullframe_bitmap_sha256']
            original = copy.deepcopy(record['original_provenance'])
            if 'source_pdf_sha256' in original.get('verification', {}):
                assert original['verification']['source_pdf_sha256'] == record['original_pdf_sha256']
                original['verification']['source_pdf_sha256'] = record['source_pdf']['sha256']
            assert original == record['provenance'], 'Only the portable source PDF fingerprint may be rebound'
            rows = {}
            for target in record['source_rows']:
                row = raw.blocks[target['block_index']].lines[target['line_index']]
                assert digest(asdict(row)) == target['source_row_sha256']
                assert row.text == target['text'] and list(row.bbox) == target['bbox']
                rows[target['line_id']] = row
            for target in record['printed_note_targets']:
                assert json.loads(json.dumps(asdict(rows[target['line_id']]))) == target['source']
            for target in record['authored_context']:
                row = rows[target['line_id']]
                assert json.loads(json.dumps(asdict(row))) == target['source']
                assert digest(asdict(row)) == target['source_row_sha256']
            before = asdict(raw)
            probe = extract.ScanPixelProbe(doc, page,
                mask=[line.bbox for block in raw.text_blocks for line in block.lines])
            candidate = transcript_regions.candidate(raw, copy.deepcopy(record['provenance']),
                doc, style, pixel_probe=probe, layer_trusted=True) if raw.transcript_unverified else None
            if raw.transcript_unverified:
                assert candidate is not None, 'No whole-page fallback may waive original source glyph obligations'
            result = candidate[0] if candidate else skeleton.page_skeleton(raw, style,
                pixel_probe=probe, layer_trusted=True)
            assert asdict(raw) == before, 'Retain all original uncertainty, source text and geometry'
            measured[book] = (raw, rows, result, doc, record)
        yield measured
    finally:
        for _, _, _, doc, _ in measured.values():
            doc.close()


@pytest.mark.parametrize('book,line_id', TARGETS)
def test_physically_printed_native_note_row_has_exactly_one_note_lane_owner(actual_pages, book, line_id):
    _, rows, result, _, _ = actual_pages[book]
    row = rows[line_id]
    owners = [r for r in result.regions if any(row is line for line in r.lines+r.caption_lines)]
    assert len(owners) == 1
    assert is_note(owners[0]), (line_id, row.text, owners[0].kind, owners[0].reason)


@pytest.mark.parametrize('book,line_id', TARGETS)
def test_physically_printed_native_note_pixels_are_not_inside_a_main_body_artwork_crop(actual_pages, book, line_id):
    raw, rows, result, doc, _ = actual_pages[book]
    wrong = []
    for region in result.regions:
        if region.kind not in ('figure', 'artwork') or is_note(region):
            continue
        common = pymupdf.Rect(rows[line_id].bbox) & pymupdf.Rect(region.bbox)
        if common.is_empty:
            continue
        pix = doc[raw.pno].get_pixmap(clip=common, matrix=pymupdf.Matrix(4, 4),
            colorspace=pymupdf.csGRAY, alpha=False)
        ink = sum(v < 200 for v in pix.samples)
        if ink > 2:
            wrong.append((region.kind, region.reason, ink, list(common)))
    assert not wrong, (line_id, wrong)


@pytest.mark.parametrize('book', [569, 570])
def test_native_note_policy_preserves_every_original_source_row_once(actual_pages, book):
    raw, _, result, _, _ = actual_pages[book]
    expected = Counter(digest(asdict(line)) for b in raw.text_blocks for line in b.lines)
    actual = Counter(digest(asdict(line)) for r in result.regions for line in r.lines+r.caption_lines)
    assert actual == expected, {'missing': expected-actual, 'duplicated': actual-expected}


@pytest.mark.parametrize('book', [569, 570])
def test_original_native_page_and_each_note_glyph_render_are_unchanged(actual_pages, book):
    raw, _, _, doc, record = actual_pages[book]
    # MuPDF's small vector clips can differ with glyph-cache render order.
    # Preserve exact original complete-page pixels before and after the producer
    # probes, then project each source glyph territory from that same full frame.
    pix = doc[raw.pno].get_pixmap(matrix=pymupdf.Matrix(4, 4), colorspace=pymupdf.csGRAY, alpha=False)
    assert hashlib.sha256(pix.samples).hexdigest() == record['fullframe_bitmap_sha256']
    image = Image.frombytes('L', (pix.width, pix.height), pix.samples)
    for witness in record['note_bitmap_scopes']:
        crop = image.crop(witness['pixelbox'])
        assert list(crop.size) == witness['pixel_size']
        assert hashlib.sha256(crop.tobytes()).hexdigest() == witness['source_pixels_sha256']
        assert witness['source_pixels_sha256'] == witness['derivative_pixels_sha256']
        assert sum(v < 200 for v in crop.tobytes()) == witness['source_dark_pixels'] > 2


@pytest.mark.parametrize('book', [569, 570])
def test_adjacent_physically_authored_source_context_remains_outside_note_and_furniture_lanes(actual_pages, book):
    _, rows, result, _, record = actual_pages[book]
    for target in record['authored_context']:
        row = rows[target['line_id']]
        owners = [r for r in result.regions if any(row is line for line in r.lines+r.caption_lines)]
        assert len(owners) == 1
        assert not is_note(owners[0]) and owners[0].kind != 'furniture', (
            target['line_id'], target['physical_role'], row.text, owners[0].kind, owners[0].reason)


def test_adjacent_original_figure12_wheel_ink_is_preserved_outside_the_note_territory(actual_pages):
    raw, _, result, doc, record = actual_pages[569]
    pix = doc[raw.pno].get_pixmap(matrix=pymupdf.Matrix(4, 4), colorspace=pymupdf.csGRAY, alpha=False)
    source = Image.frombytes('L', (pix.width, pix.height), pix.samples)
    for scope in record['chart_support_scopes']:
        assert scope['outside_notes'] and scope['must_preserve_dark_pixels']
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
            if common.is_empty:
                continue
            draw.rectangle((math.floor(common.x0*4)-pix.x-pixelbox[0],
                            math.floor(common.y0*4)-pix.y-pixelbox[1],
                            math.ceil(common.x1*4)-pix.x-pixelbox[0]-1,
                            math.ceil(common.y1*4)-pix.y-pixelbox[1]-1), fill=255)
        data, covered = image.tobytes(), mask.tobytes()
        ink = sum(v < 200 for v in data)
        retained = sum(v < 200 and covered[i] > 0 for i, v in enumerate(data))
        assert ink > 100 and retained/ink >= .99, (retained, ink)


@pytest.mark.parametrize('marker,lexical,other_lexical', [('l28', 'l30', 'l31'), ('l29', 'l31', 'l30')])
def test_measured_source_marker_is_associated_with_its_actual_same_baseline_note_text(
        actual_pages, marker, lexical, other_lexical):
    _, rows, result, _, _ = actual_pages[570]
    owners = [r for r in result.regions if any(rows[marker] is line for line in r.lines)]
    assert len(owners) == 1 and is_note(owners[0])
    assert any(rows[lexical] is line for line in owners[0].lines), (marker, lexical)
    assert not any(rows[other_lexical] is line for line in owners[0].lines), (
        'Extraction order must not attach both source notes to the second label', marker, lexical)
