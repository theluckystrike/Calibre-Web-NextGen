"""Original Chart4 degree labels must not migrate into the printed-note lane.

The opposing printed date is a physically verified real note. This negative
uses the complete original retained page/style and unmasked native scan pixels;
all source geometry, literal rows and artwork remain independently observable.
"""
from collections import Counter
from dataclasses import asdict, fields
from functools import lru_cache
from pathlib import Path
import copy
import hashlib
import json
import pymupdf
from PIL import Image, ImageDraw
import pytest
from cps.services.reflow import extract, skeleton
from tests.unit.test_reflow_physical_footer_canonical_delivery import raw_page, digest, is_note

pytestmark = pytest.mark.unit
FIXTURE = Path(__file__).parents[1] / 'fixtures/reflow/physical_footer_chart_axis19.json'


@lru_cache()
def data():
    return json.loads(FIXTURE.read_text())


def classify():
    evidence = data()
    raw = raw_page(evidence['raw'])
    assert digest(asdict(raw)) == evidence['raw_sha256']
    values = copy.deepcopy(evidence['book_style'])
    for key, value in values.items():
        if isinstance(value, dict) and all(str(p).isdigit() for p in value):
            values[key] = {int(p): v for p, v in value.items()}
    values['folio_boxes'] = {p: tuple(box) for p, box in values['folio_boxes'].items()}
    for key in ('local_running_boxes', 'repeated_head_boxes', 'portrait_head_boxes',
                'scan_spread_head_boxes', 'scan_table_label_boxes', 'scan_note_lane_boxes'):
        values[key] = {p: [tuple(box) for box in boxes] for p, boxes in values[key].items()}
    accepted = {field.name for field in fields(skeleton.BookStyle)}
    style = skeleton.BookStyle(**{k: v for k, v in values.items() if k in accepted})
    rows = {}
    for target in evidence['role_expectations']:
        row = raw.blocks[target['block_index']].lines[target['line_index']]
        assert digest(asdict(row)) == target['source_row_sha256']
        assert row.text == target['text'] and list(row.bbox) == target['bbox']
        rows[target['line_id']] = row
    pixels = evidence['source_pixels']
    payload = (FIXTURE.parent / pixels['path']).read_bytes()
    assert hashlib.sha256(payload).hexdigest() == pixels['sha256']
    assert pixels['unmasked'] and pixels['source_geometry'] == raw.source_geometry
    doc = pymupdf.open()
    for _ in range(raw.pno + 1):
        doc.new_page(width=raw.width, height=raw.height)
    doc[raw.pno].insert_image(pymupdf.Rect(pixels['reading_bbox']), stream=payload)
    before = asdict(raw)
    probe = extract.ScanPixelProbe(doc, raw.pno,
        mask=[line.bbox for block in raw.text_blocks for line in block.lines])
    try:
        result = skeleton.page_skeleton(raw, style, pixel_probe=probe)
        assert asdict(raw) == before
        return raw, rows, result, doc
    except BaseException:
        doc.close()
        raise


@pytest.mark.parametrize('line_id', ['l18', 'l19', 'l20'])
def test_actual_chart_axis_and_authored_caption_are_neither_notes_nor_furniture(line_id):
    _, rows, result, doc = classify()
    try:
        row = rows[line_id]
        owners = [r for r in result.regions if any(row is line for line in r.lines + r.caption_lines)]
        assert len(owners) == 1
        assert not is_note(owners[0]) and owners[0].kind != 'furniture', (
            line_id, owners[0].kind, owners[0].reason)
    finally:
        doc.close()


def test_opposing_physically_printed_date_remains_owned_as_a_note():
    _, rows, result, doc = classify()
    try:
        owners = [r for r in result.regions if any(rows['l63'] is line for line in r.lines)]
        assert len(owners) == 1 and is_note(owners[0])
    finally:
        doc.close()


def test_chart_negative_preserves_all_original_source_rows_once():
    raw, _, result, doc = classify()
    try:
        expected = Counter(digest(asdict(line)) for b in raw.text_blocks for line in b.lines)
        actual = Counter(digest(asdict(line)) for r in result.regions for line in r.lines + r.caption_lines)
        assert actual == expected
    finally:
        doc.close()


@pytest.mark.parametrize('scope', ['top_axis', 'bottom_axis', 'wheel'])
def test_original_chart_ink_remains_in_body_figures_including_its_bottom_axis(scope):
    raw, rows, result, doc = classify()
    try:
        box = pymupdf.Rect(data()['full_chart_source_scope'] if scope == 'wheel'
                          else rows['l18' if scope == 'top_axis' else 'l19'].bbox)
        pix = doc[raw.pno].get_pixmap(clip=box, matrix=pymupdf.Matrix(3, 3),
            colorspace=pymupdf.csGRAY, alpha=False)
        covered = Image.new('L', (pix.width, pix.height), 0)
        draw = ImageDraw.Draw(covered)
        for region in result.regions:
            if region.kind != 'figure' or is_note(region):
                continue
            common = box & pymupdf.Rect(region.bbox)
            if not common.is_empty:
                draw.rectangle(((common.x0-box.x0)*3, (common.y0-box.y0)*3,
                    (common.x1-box.x0)*3, (common.y1-box.y0)*3), fill=255)
        mask = covered.tobytes()
        ink = sum(v < 200 for v in pix.samples)
        retained = sum(v < 200 and mask[i] > 0 for i, v in enumerate(pix.samples))
        assert ink > 100
        assert retained / ink >= .99, (scope, retained, ink,
            [(r.kind, r.reason, r.bbox) for r in result.regions if r.kind == 'figure'])
    finally:
        doc.close()


# The actual native-transcript source pages below contain timelines/TOC, not
# notes. Their portable PDF copies preserve original page indices and operators.
# Verification binds the derivative PDF; independent full-page and unmatched-
# glyph render equality binds those bytes back to the original authored pages.
STRUCTURAL_FIXTURE = FIXTURE.parent / 'physical_footer_structural_negatives.json'


@lru_cache()
def structural_data():
    return json.loads(STRUCTURAL_FIXTURE.read_text())


def structural_inputs(book, page):
    evidence = structural_data()['books'][str(book)]
    record = evidence['pages'][str(page)]
    raw = raw_page(record['raw'])
    assert digest(asdict(raw)) == record['raw_sha256']
    values = copy.deepcopy(evidence['book_style'])
    for key, value in values.items():
        if isinstance(value, dict) and all(str(p).isdigit() for p in value):
            values[key] = {int(p): v for p, v in value.items()}
    values['folio_boxes'] = {p: tuple(box) for p, box in values['folio_boxes'].items()}
    values['local_running_boxes'] = {p: tuple(box) for p, box in values['local_running_boxes'].items()}
    for key in ('repeated_head_boxes', 'portrait_head_boxes',
                'scan_spread_head_boxes', 'scan_table_label_boxes', 'scan_note_lane_boxes'):
        values[key] = {p: [tuple(box) for box in boxes] for p, boxes in values[key].items()}
    accepted = {field.name for field in fields(skeleton.BookStyle)}
    style = skeleton.BookStyle(**{k: v for k, v in values.items() if k in accepted})
    source = evidence['source_pdf']
    path = STRUCTURAL_FIXTURE.parent / source['path']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == source['sha256']
    doc = pymupdf.open(path)
    assert list(doc[page].rect) == record['frame'] and doc[page].rotation == record['rotation']
    assert raw.source_geometry == record['source_geometry']
    original = copy.deepcopy(record['original_provenance'])
    if 'source_pdf_sha256' in original.get('verification', {}):
        assert original['verification']['source_pdf_sha256'] == evidence['original_pdf_sha256']
        original['verification']['source_pdf_sha256'] = source['sha256']
    assert original == record['provenance'], 'Only the portable PDF fingerprint may be rebound'
    # Every row binds exact retained source literal, geometry and hash.
    rows = {}
    for target in record['source_rows']:
        row = raw.blocks[target['block_index']].lines[target['line_index']]
        assert digest(asdict(row)) == target['source_row_sha256']
        assert row.text == target['text'] and list(row.bbox) == target['bbox']
        rows[target['line_id']] = row
    assert len(rows) == sum(len(b.lines) for b in raw.text_blocks)
    return raw, style, rows, doc, record


def structural_classify(book, page, path):
    from cps.services.reflow import transcript_regions
    raw, style, rows, doc, record = structural_inputs(book, page)
    before = asdict(raw)
    probe = extract.ScanPixelProbe(doc, page,
        mask=[line.bbox for block in raw.text_blocks for line in block.lines])
    try:
        candidate = None
        if path == 'pipeline' and raw.transcript_unverified:
            candidate = transcript_regions.candidate(raw, copy.deepcopy(record['provenance']),
                doc, style, pixel_probe=probe, layer_trusted=True)
        if path == 'native':
            # This is the candidate's measured native source path, retaining all
            # original source rows/flags except its explicit whole-page refusal.
            from dataclasses import replace
            measured = replace(raw, transcript_unverified=False)
        else:
            measured = raw
        result = candidate[0] if candidate else skeleton.page_skeleton(
            measured, style, pixel_probe=probe, layer_trusted=True)
        assert asdict(raw) == before
        return raw, rows, result, doc, candidate
    except BaseException:
        doc.close()
        raise


STRUCTURAL_CASES = [(567, 592, 'native'), (567, 592, 'pipeline'),
                    (567, 613, 'native'), (567, 613, 'pipeline'),
                    (569, 7, 'native'), (569, 7, 'pipeline')]


@pytest.mark.parametrize('book,page,path', STRUCTURAL_CASES)
def test_actual_timeline_and_toc_full_source_page_has_no_printed_note_territory(book, page, path):
    _, _, result, doc, _ = structural_classify(book, page, path)
    try:
        assert not [r for r in result.regions if is_note(r)], [
            (r.kind, r.reason, r.number, [l.text for l in r.lines])
            for r in result.regions if is_note(r)]
    finally:
        doc.close()


@pytest.mark.parametrize('book,page,path', STRUCTURAL_CASES)
def test_actual_timeline_and_toc_preserves_every_original_source_row_once(book, page, path):
    raw, _, result, doc, _ = structural_classify(book, page, path)
    try:
        expected = Counter(digest(asdict(line)) for b in raw.text_blocks for line in b.lines)
        actual = Counter(digest(asdict(line)) for r in result.regions for line in r.lines + r.caption_lines)
        assert actual == expected
    finally:
        doc.close()


@pytest.mark.parametrize('page,path,line_ids', [
    (592, 'native', ['l58', 'l59', 'l60', 'l61', 'l62', 'l63', 'l64', 'l69', 'l70', 'l71']),
    (592, 'pipeline', ['l58', 'l59', 'l60', 'l61', 'l62', 'l63', 'l64', 'l69', 'l70', 'l71']),
    (613, 'native', ['l73', 'l74', 'l75', 'l76', 'l77', 'l78', 'l79', 'l80', 'l81']),
    (613, 'pipeline', ['l73', 'l74', 'l75', 'l76', 'l77', 'l78', 'l79', 'l80', 'l81']),
])
def test_complete_physically_viewed_timeline_tail_stays_in_reading_context(page, path, line_ids):
    _, rows, result, doc, _ = structural_classify(567, page, path)
    try:
        for lid in line_ids:
            owners = [r for r in result.regions if any(rows[lid] is line for line in r.lines + r.caption_lines)]
            assert len(owners) == 1, (page, path, lid, len(owners))
            assert not is_note(owners[0]) and owners[0].kind != 'furniture', (
                page, path, lid, owners[0].kind, owners[0].reason)
    finally:
        doc.close()


def test_actual613_candidate_covers_its_unmatched_original_zodiac_glyph_without_fullpage_refusal():
    from cps.services.reflow import transcript_regions
    _, _, result, doc, candidate = structural_classify(567, 613, 'pipeline')
    try:
        assert candidate is not None, 'Actual source glyph must keep complete candidate crop coverage'
        proof = candidate[1]
        record = structural_data()['books']['567']['pages']['613']
        assert proof['unmatched_pdf_boxes'] == record['provenance']['verification']['unmatched_pdf_boxes']
        assert len(proof['owners']) == len(proof['unmatched_pdf_boxes']) == 1
        for box, owner in zip(proof['unmatched_pdf_boxes'], proof['owners']):
            matches = [r for r in result.regions if r.kind == 'figure'
                and r.reason in transcript_regions._CROPS
                and list(r.bbox) == owner['bbox'] and transcript_regions._inside(box, r.bbox)]
            assert len(matches) == 1
        assert not any(r.reason == 'unrecovered_scan_layer' for r in result.regions)
    finally:
        doc.close()


@pytest.mark.parametrize('book,page', [(567, 592), (567, 613), (569, 7)])
def test_portable_original_source_page_and_glyph_pixels_match_independent_render_witness(book, page):
    _, _, _, doc, record = structural_inputs(book, page)
    try:
        for witness in record['render_equality']:
            pix = doc[page].get_pixmap(clip=pymupdf.Rect(witness['bbox']),
                matrix=pymupdf.Matrix(2, 2), colorspace=pymupdf.csGRAY, alpha=False)
            actual = hashlib.sha256(pix.samples).hexdigest()
            assert [pix.width, pix.height] == witness['pixel_size']
            assert actual == witness['source_pixels_sha256'] == witness['derivative_pixels_sha256']
            assert witness['equal']
    finally:
        doc.close()


@pytest.mark.parametrize('path', ['native', 'pipeline'])
def test_actual_toc_chapter_numbers_titles_and_destinations_remain_authored_contents(path):
    _, rows, result, doc, _ = structural_classify(569, 7, path)
    try:
        for lid in ['l36', 'l37', 'l38', 'l49', 'l50', 'l51']:
            owners = [r for r in result.regions if any(rows[lid] is line for line in r.lines + r.caption_lines)]
            assert len(owners) == 1, (lid, len(owners))
            assert not is_note(owners[0]) and owners[0].kind != 'furniture', (
                lid, rows[lid].text, owners[0].kind, owners[0].reason)
    finally:
        doc.close()



def test_actual613_authored_right_paragraphs_remain_live_beneath_chart120():
    raw, rows, result, doc, _ = structural_classify(567, 613, 'pipeline')
    try:
        # Independently viewed substantive source paragraphs, explicitly not
        # captions/chart labels. Their original source spans are all reliable.
        for lid in ['l53', 'l54', 'l66', 'l68', 'l72']:
            row = rows[lid]
            assert not row.transcription_uncertain
            assert not any(s.uncertain or s.transcription_uncertain or s.encoding_unresolved for s in row.spans)
            owners = [r for r in result.regions if any(row is line for line in r.lines)]
            assert len(owners) == 1 and owners[0].kind == 'body', (
                lid, row.text, [(r.kind, r.reason) for r in owners])
    finally:
        doc.close()



def test_actual570_contents_destinations_and_topic_rows_remain_contents_not_notes():
    raw, rows, result, doc, _ = structural_classify(570, 6, 'pipeline')
    try:
        record = structural_data()['books']['570']['pages']['6']
        review = record['independent_physical_review']
        assert review['physically_viewed'] and review['printed_note_rows'] == []
        expected = Counter(digest(asdict(line)) for b in raw.text_blocks for line in b.lines)
        actual = Counter(digest(asdict(line)) for r in result.regions for line in r.lines + r.caption_lines)
        assert actual == expected
        for source in review['claimed_source_rows']:
            row = rows[source['line_id']]
            assert digest(asdict(row)) == source['source_row_sha256']
            assert row.text == source['text'] and list(row.bbox) == source['bbox']
            owners = [r for r in result.regions if any(row is line for line in r.lines + r.caption_lines)]
            assert len(owners) == 1 and not is_note(owners[0]) and owners[0].kind != 'furniture', (
                source['line_id'], row.text, [(r.kind, r.reason) for r in owners])
        assert not any(is_note(r) for r in result.regions)
        # Portable page reproduces the independent original source render.
        for witness in record['render_equality']:
            pix = doc[6].get_pixmap(clip=pymupdf.Rect(witness['bbox']),
                matrix=pymupdf.Matrix(2, 2), colorspace=pymupdf.csGRAY, alpha=False)
            assert hashlib.sha256(pix.samples).hexdigest() == witness['source_pixels_sha256']
    finally:
        doc.close()
