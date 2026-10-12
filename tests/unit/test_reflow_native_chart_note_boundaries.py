"""Independent original native-page chart, prose and real-note boundaries.

The portable PDFs copy original page operators at their original indices. The
whole-book style and complete consistent source rows are retained. Independent
physical review supplies note/prose/chart roles; converter roles are not truth.
"""
from collections import Counter
from dataclasses import asdict, fields, replace
from functools import lru_cache
from pathlib import Path
import copy
import hashlib
import json
import pymupdf
from PIL import Image, ImageDraw
import pytest
from cps.services.reflow import extract, skeleton, transcript_regions
from tests.unit.test_reflow_physical_footer_canonical_delivery import raw_page, digest, is_note

pytestmark = pytest.mark.unit
FIXTURE = Path(__file__).parents[1] / 'fixtures/reflow/physical_native_chart_note_boundaries.json'
CASES = [(567, 599), (567, 609), (567, 633), (569, 46), (569, 76), (569, 355)]
CROP_REASONS = {'scan_figure_band', 'scan_figure_side', 'native_spacing_uncertain'}


@lru_cache()
def data():
    return json.loads(FIXTURE.read_text())


def inputs(book, page):
    evidence = data()['books'][str(book)]
    record = evidence['pages'][str(page)]
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
    accepted = {field.name for field in fields(skeleton.BookStyle)}
    style = skeleton.BookStyle(**{k: v for k, v in values.items() if k in accepted})
    source = evidence['source_pdf']
    path = FIXTURE.parent / source['path']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == source['sha256']
    doc = pymupdf.open(path)
    assert list(doc[page].rect) == record['frame'] and doc[page].rotation == record['rotation']
    assert raw.source_geometry == record['source_geometry']
    original = copy.deepcopy(record['original_provenance'])
    assert original['verification']['source_pdf_sha256'] == evidence['original_pdf_sha256']
    original['verification']['source_pdf_sha256'] = source['sha256']
    assert original == record['provenance'], 'Only portable PDF fingerprint may change'
    rows = {}
    for target in record['source_rows']:
        row = raw.blocks[target['block_index']].lines[target['line_index']]
        assert digest(asdict(row)) == target['source_row_sha256']
        assert row.text == target['text'] and list(row.bbox) == target['bbox']
        rows[target['line_id']] = row
    assert len(rows) == sum(len(block.lines) for block in raw.text_blocks)
    assert record['independent_physical_review']['physically_viewed']
    return raw, style, rows, doc, record


def classify(book, page, path='pipeline'):
    raw, style, rows, doc, record = inputs(book, page)
    before = asdict(raw)
    # Exact pipeline mask. The candidate still has the unmasked original PDF
    # for independently qualified unmatched-glyph/source-frame obligations.
    probe = extract.ScanPixelProbe(doc, page,
        mask=[line.bbox for block in raw.text_blocks for line in block.lines])
    try:
        candidate = None
        if path == 'pipeline' and raw.transcript_unverified:
            candidate = transcript_regions.candidate(raw, copy.deepcopy(record['provenance']),
                doc, style, pixel_probe=probe, layer_trusted=True)
        measured = replace(raw, transcript_unverified=False) if path == 'native' else raw
        result = candidate[0] if candidate else skeleton.page_skeleton(
            measured, style, pixel_probe=probe, layer_trusted=True)
        assert asdict(raw) == before, 'No source text, uncertainty or geometry rewrite'
        return raw, rows, result, doc, candidate, record
    except BaseException:
        doc.close()
        raise


def owners(result, row):
    return [r for r in result.regions if any(row is line for line in r.lines + r.caption_lines)]


@pytest.mark.parametrize('book,page', CASES)
def test_actual_printed_note_rows_remain_notes_through_complete_candidate_pipeline(book, page):
    _, rows, result, doc, _, record = classify(book, page)
    try:
        wrong = []
        for lid in record['independent_physical_review']['printed_note_line_ids']:
            found = owners(result, rows[lid])
            if len(found) != 1 or not is_note(found[0]):
                wrong.append((lid, [(r.kind, r.reason) for r in found]))
        assert not wrong, wrong
    finally:
        doc.close()


@pytest.mark.parametrize('book,page', CASES)
def test_original_native_pages_conserve_every_source_row_once(book, page):
    raw, _, result, doc, _, _ = classify(book, page)
    try:
        expected = Counter(digest(asdict(line)) for b in raw.text_blocks for line in b.lines)
        actual = Counter(digest(asdict(line)) for r in result.regions for line in r.lines + r.caption_lines)
        assert actual == expected, {'missing': expected - actual, 'duplicated': actual - expected}
    finally:
        doc.close()


@pytest.mark.parametrize('book,page', CASES)
def test_body_figures_do_not_reprint_the_physically_verified_native_note_ink(book, page):
    raw, rows, result, doc, _, record = classify(book, page)
    try:
        wrong = []
        for r in result.regions:
            if r.kind != 'figure' or is_note(r):
                continue
            for lid in record['independent_physical_review']['printed_note_line_ids']:
                common = pymupdf.Rect(r.bbox) & pymupdf.Rect(rows[lid].bbox)
                if common.is_empty:
                    continue
                pix = doc[raw.pno].get_pixmap(clip=common, matrix=pymupdf.Matrix(3, 3),
                    colorspace=pymupdf.csGRAY, alpha=False)
                ink = sum(v < 200 for v in pix.samples)
                if ink > 2:
                    wrong.append((lid, r.reason, ink, list(common)))
        assert not wrong, wrong
    finally:
        doc.close()


@pytest.mark.parametrize('book,page', CASES)
def test_portable_source_frame_and_glyph_pixels_equal_independently_rendered_original(book, page):
    raw, _, _, doc, record = inputs(book, page)
    try:
        scopes = [record['frame']] + record['original_provenance']['verification'].get('unmatched_pdf_boxes', [])
        assert len(scopes) == len(record['render_equality'])
        for box, witness in zip(scopes, record['render_equality']):
            assert box == witness['bbox'] and witness['equal']
            pix = doc[raw.pno].get_pixmap(clip=pymupdf.Rect(box), matrix=pymupdf.Matrix(2, 2),
                colorspace=pymupdf.csGRAY, alpha=False)
            assert [pix.width, pix.height] == witness['pixel_size']
            actual = hashlib.sha256(pix.samples).hexdigest()
            assert actual == witness['source_pixels_sha256'] == witness['derivative_pixels_sha256']
    finally:
        doc.close()


def test_actual_599_candidate_retains_all_five_unmatched_chart_glyph_obligations():
    _, _, result, doc, candidate, record = classify(567, 599)
    try:
        boxes = record['original_provenance']['verification']['unmatched_pdf_boxes']
        assert len(boxes) == 5
        assert candidate is not None, 'Real chart glyph obligations must not force whole-page refusal'
        for box in boxes:
            rect = pymupdf.Rect(box)
            found = [r for r in result.regions if r.kind == 'figure' and r.reason in CROP_REASONS
                     and (rect & pymupdf.Rect(r.bbox)).get_area() / rect.get_area() >= .99]
            assert len(found) == 1, (box, [(r.reason, r.bbox) for r in found])
        assert not any(r.reason == 'unrecovered_scan_layer' for r in result.regions)
    finally:
        doc.close()


@pytest.mark.parametrize('line_id', ['l24', 'l25', 'l26', 'l33', 'l35', 'l45'])
def test_actual_599_reliable_authored_prose_remains_live_body(line_id):
    _, rows, result, doc, _, record = classify(567, 599)
    try:
        assert line_id in record['independent_physical_review']['reliable_live_prose_line_ids']
        row = rows[line_id]
        assert not row.transcription_uncertain
        assert all(not s.uncertain and not s.transcription_uncertain and not s.encoding_unresolved for s in row.spans)
        found = owners(result, row)
        assert len(found) == 1 and found[0].kind == 'body', (
            line_id, [(r.kind, r.reason) for r in found])
    finally:
        doc.close()


@pytest.mark.parametrize('scope', ['bbox', 'upper_rim_bbox', 'lower_rim_bbox'])
def test_actual_599_complete_chart110_ink_remains_in_qualified_native_figure_crops(scope):
    raw, _, result, doc, _, record = classify(567, 599, path='native')
    try:
        physical = record['independent_physical_review']['chart110_ink_scope']
        assert physical['physically_viewed']
        box = pymupdf.Rect(physical[scope])
        pix = doc[raw.pno].get_pixmap(clip=box, matrix=pymupdf.Matrix(3, 3),
            colorspace=pymupdf.csGRAY, alpha=False)
        mask = Image.new('L', (pix.width, pix.height), 0)
        draw = ImageDraw.Draw(mask)
        for r in result.regions:
            if r.kind != 'figure' or r.reason not in CROP_REASONS or is_note(r):
                continue
            common = box & pymupdf.Rect(r.bbox)
            if not common.is_empty:
                draw.rectangle(((common.x0-box.x0)*3, (common.y0-box.y0)*3,
                    (common.x1-box.x0)*3, (common.y1-box.y0)*3), fill=255)
        covered = mask.tobytes()
        ink = sum(v < 200 for v in pix.samples)
        retained = sum(v < 200 and covered[i] > 0 for i, v in enumerate(pix.samples))
        assert ink > 100
        assert retained / ink >= .99, (scope, retained, ink,
            [(r.reason, r.bbox) for r in result.regions if r.kind == 'figure'])
    finally:
        doc.close()


def test_actual_599_authored_section_heading_remains_outside_note_and_furniture_lanes():
    raw, rows, result, doc, _, record = classify(567, 599)
    try:
        assert 'l34' in record['independent_physical_review']['authored_heading_line_ids']
        found = owners(result, rows['l34'])
        # Existing hidden-layer heading policy keeps this authored title as
        # original pixels. Demand its own complete source crop, not live OCR
        # or absorption into a giant table/chart/whole-page fallback.
        assert len(found) == 1 and not is_note(found[0]) and found[0].kind != 'furniture', [(r.kind, r.reason) for r in found]
        box = pymupdf.Rect(rows['l34'].bbox)
        dedicated = [r for r in result.regions if r.kind == 'figure' and not is_note(r)
                     and all(abs(a-b) <= .25 for a, b in zip(r.bbox, box))]
        assert len(dedicated) == 1, [(r.reason, r.bbox) for r in result.regions if r.kind == 'figure']
        physical = record['independent_physical_review']
        assert (box & pymupdf.Rect(physical['chart110_ink_scope']['bbox'])).is_empty
        assert all((box & pymupdf.Rect(rows[lid].bbox)).is_empty
                   for lid in physical['printed_note_line_ids'] + physical['source_caption_line_ids'])
        pix = doc[raw.pno].get_pixmap(clip=box, matrix=pymupdf.Matrix(3, 3),
            colorspace=pymupdf.csGRAY, alpha=False)
        assert sum(v < 200 for v in pix.samples) > 100
    finally:
        doc.close()


def test_actual_592_authored_section_heading_keeps_its_source_owner():
    # The original32 module supplies its already-bound portable source. Its
    # uncertainty is retained: this control demands source ownership rather
    # than pretending uncertain OCR is reliable live text.
    from tests.unit.test_reflow_physical_footer_chart_axis import structural_classify
    raw, rows, result, doc, _ = structural_classify(567, 592, 'pipeline')
    try:
        proof = data()['independent_authored_heading_preservation']
        assert digest(asdict(raw)) == proof['raw_page_sha256']
        row = rows[proof['line_id']]
        assert digest(asdict(row)) == proof['source_object_sha256']
        assert row.text == proof['literal'] and list(row.bbox) == proof['bbox']
        found = owners(result, row)
        assert len(found) == 1 and not is_note(found[0]) and found[0].kind != 'furniture', (
            proof['line_id'], [(r.kind, r.reason) for r in found])
    finally:
        doc.close()


@pytest.mark.parametrize('path', ['native', 'pipeline'])
def test_actual_609_hirohito_timeline_fields_remain_outside_printed_note_lane(path):
    _, rows, result, doc, _, record = classify(567, 609, path=path)
    try:
        wrong = []
        ids = record['independent_physical_review']['timeline_line_ids']
        assert len(ids) == 8
        for lid in ids:
            found = owners(result, rows[lid])
            if len(found) != 1 or is_note(found[0]) or found[0].kind == 'furniture':
                wrong.append((lid, [(r.kind, r.reason) for r in found]))
        assert not wrong, wrong
    finally:
        doc.close()
