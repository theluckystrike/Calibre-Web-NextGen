"""A physically reviewed timeline field must have one reading channel.

The original native page, retained literal/flags and whole-book style come from
the existing portable source fixture. Independent source review identifies this
one row as a timeline field. It must keep its source ink in one ordinary image
owner without also emitting that field as live body prose.
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
from tests.unit.test_reflow_physical_footer_chart_axis import (
    STRUCTURAL_FIXTURE, structural_classify, structural_data,
)
from cps.services.reflow import extract, skeleton, transcript_regions
from tests.unit.test_reflow_physical_footer_canonical_delivery import digest, is_note, raw_page

pytestmark = pytest.mark.unit
FIXTURE = Path(__file__).parents[1] / 'fixtures/reflow/native_tablefield_single_delivery.json'


CASES = [(592, 'l4'), (592, 'l55'), (592, 'l61'), (608, 'l70')]


def source608(proof):
    record = proof['pages']['608']
    raw = raw_page(record['raw'])
    assert digest(asdict(raw)) == record['raw_sha256']
    values = copy.deepcopy(record['style'])
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
    pdf = FIXTURE.parent / record['source_pdf']['path']
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == record['source_pdf']['sha256']
    doc = pymupdf.open(pdf)
    before = asdict(raw)
    try:
        assert list(doc[608].rect) == record['frame'] and doc[608].rotation == record['rotation']
        assert raw.source_geometry == record['source_geometry']
        original = copy.deepcopy(record['original_provenance'])
        assert original['verification']['source_pdf_sha256'] == proof['original_pdf_sha256']
        original['verification']['source_pdf_sha256'] = record['source_pdf']['sha256']
        assert original == record['provenance']
        rows = {}
        for witness in record['source_rows']:
            row = raw.blocks[witness['block_index']].lines[witness['line_index']]
            assert digest(asdict(row)) == witness['source_row_sha256']
            rows[witness['line_id']] = row
        probe = extract.ScanPixelProbe(doc, 608,
            mask=[line.bbox for block in raw.text_blocks for line in block.lines])
        candidate = transcript_regions.candidate(raw, copy.deepcopy(record['provenance']),
            doc, style, pixel_probe=probe, layer_trusted=True) if raw.transcript_unverified else None
        if raw.transcript_unverified:
            assert candidate is not None, 'Original source-frame/glyph obligations must retain a valid candidate'
        result = candidate[0] if candidate else skeleton.page_skeleton(
            raw, style, pixel_probe=probe, layer_trusted=True)
        for box in record['original_provenance']['verification'].get('unmatched_pdf_boxes', []):
            rect = pymupdf.Rect(box)
            covered = [r for r in result.regions if r.kind == 'figure' and not is_note(r)
                and (rect & pymupdf.Rect(r.bbox)).get_area() / rect.get_area() >= .99]
            assert len(covered) == 1, ('Original unmatched source glyph must have one complete image owner', box)
        assert asdict(raw) == before
        return raw, rows, result, doc, record['render_equality']
    except BaseException:
        doc.close()
        raise


@pytest.fixture(scope='module')
def actual_fields():
    proof = json.loads(FIXTURE.read_text())
    assert proof['physical_review']['physically_viewed']
    assert hashlib.sha256(STRUCTURAL_FIXTURE.read_bytes()).hexdigest() == proof['structural_fixture_sha256']
    source = structural_data()['books']['567']
    assert source['original_pdf_sha256'] == proof['original_pdf_sha256']
    assert source['source_pdf'] == proof['portable_pdf']
    raw, rows, result, doc, _ = structural_classify(567, 592, 'pipeline')
    pages = {592: (raw, rows, result, doc, source['pages']['592']['render_equality'])}
    try:
        pages[608] = source608(proof)
        for page, (raw, rows, result, doc, witnesses) in pages.items():
            assert not any(r.reason == 'unrecovered_scan_layer' for r in result.regions)
            for witness in witnesses:
                pixels = doc[page].get_pixmap(clip=pymupdf.Rect(witness['bbox']),
                    matrix=pymupdf.Matrix(2, 2), colorspace=pymupdf.csGRAY, alpha=False)
                assert hashlib.sha256(pixels.samples).hexdigest() == witness['source_pixels_sha256']
            for target in proof['targets']:
                if target['page'] != page:
                    continue
                row = rows[target['line_id']]
                assert target['physical_role'] == 'ordinary_timeline_field'
                assert json.loads(json.dumps(asdict(row))) == target['source']
                assert digest(asdict(row)) == target['source_row_sha256']
                assert row.text == target['text'] and list(row.bbox) == target['bbox']
        yield pages
    finally:
        for _, _, _, doc, _ in pages.values():
            doc.close()


@pytest.mark.parametrize('page,line_id', CASES)
def test_original_timeline_field_is_not_also_live_body_prose(actual_fields, page, line_id):
    _, rows, result, _, _ = actual_fields[page]
    row = rows[line_id]
    owners = [r for r in result.regions if any(row is line for line in r.lines + r.caption_lines)]
    assert len(owners) == 1, [(r.kind, r.reason) for r in owners]
    assert not is_note(owners[0]) and owners[0].kind != 'furniture'
    assert owners[0].kind != 'body', (
        'Physically verified timeline field still has a live BODY reading channel',
        row.text, [(r.kind, r.reason, r.bbox) for r in owners])


@pytest.mark.parametrize('page,line_id', CASES)
def test_original_timeline_field_has_one_image_owner_covering_its_actual_source_ink(actual_fields, page, line_id):
    raw, rows, result, doc, _ = actual_fields[page]
    row = rows[line_id]
    scale = 4
    pix = doc[raw.pno].get_pixmap(clip=pymupdf.Rect(row.bbox),
        matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csGRAY, alpha=False)
    ink = sum(v < 200 for v in pix.samples)
    assert ink > 100, 'Independent unmasked original field pixels must be present'
    complete = []
    for region in result.regions:
        if region.kind != 'figure' or is_note(region) or region.reason == 'unrecovered_scan_layer':
            continue
        common = pymupdf.Rect(row.bbox) & pymupdf.Rect(region.bbox)
        if common.is_empty:
            continue
        mask = Image.new('L', (pix.width, pix.height), 0)
        draw = ImageDraw.Draw(mask)
        draw.rectangle((math.floor(common.x0*scale)-pix.x, math.floor(common.y0*scale)-pix.y,
                        math.ceil(common.x1*scale)-pix.x-1, math.ceil(common.y1*scale)-pix.y-1), fill=255)
        covered = mask.tobytes()
        retained = sum(v < 200 and covered[i] > 0 for i, v in enumerate(pix.samples))
        if retained / ink >= .99:
            complete.append(region)
    assert len(complete) == 1, [(r.kind, r.reason, r.bbox) for r in complete]


@pytest.mark.parametrize('page', [592, 608])
def test_timeline_channel_arbitration_preserves_every_original_source_row_once(actual_fields, page):
    raw, _, result, _, _ = actual_fields[page]
    expected = Counter(digest(asdict(line)) for block in raw.text_blocks for line in block.lines)
    actual = Counter(digest(asdict(line)) for r in result.regions for line in r.lines + r.caption_lines)
    assert actual == expected, {'missing': expected-actual, 'duplicated': actual-expected}


def measured_field(top, *, prefix='', reliable=False, inflated=False, left=40, height=11.34):
    """Construct a measured control, not a claimed authored book row.

    The separate symbol span can have an inflated OCR box while the original
    code/date spans share their own measured type and baseline. Every complete
    line keeps its original symbol pixels and complete box.
    """
    baseline = top + 8.95
    spans = []
    if prefix:
        box = (left, top-3.16 if inflated else top, left+12, top+height)
        spans.append(extract.Span(prefix+' ', 8.62, 'body', 0, box,
            origin_y=baseline, transcription_uncertain=not reliable))
    start = left+16 if prefix else left
    spans.append(extract.Span('L2 - 1/2/2020', 9.32, 'body', 0,
        (start, top, left+110, top+height), origin_y=baseline))
    whole = (left, min(s.bbox[1] for s in spans), left+110, top+height)
    return extract.Line(spans, whole)


def classified_field_ids(lines):
    before = [asdict(line) for line in lines]
    kept = [(extract.Block(i, line.bbox, [line]), [line]) for i, line in enumerate(lines)]
    found = skeleton._scan_numeric_field_rows(kept, skeleton.BookStyle(body_size=11.3))
    assert [asdict(line) for line in lines] == before
    return found


@pytest.mark.parametrize('position,inflated', [('inside', True), ('after', False), ('before', False)])
def test_original_field_type_and_bounded_edge_use_independent_strict_run(position, inflated):
    anchors = [measured_field(t) for t in [100, 111, 122, 133]]
    if position == 'inside':
        anchors = [measured_field(t) for t in [100, 111, 133, 144]]
        target = measured_field(122, prefix='IlL', inflated=inflated)
    else:
        target = measured_field(144 if position == 'after' else 89, prefix="Yvk'")
    found = classified_field_ids(anchors+[target])
    assert all(id(line) in found for line in anchors), 'Strict original anchors must actually qualify'
    assert id(target) in found, ('Original code/date type and bounded anchor pitch must retain field',
        position, asdict(target))


@pytest.mark.parametrize('prefix', ['and', 'AND'])
def test_reliable_lexical_prefix_never_becomes_an_uncertain_table_symbol(prefix):
    anchors = [measured_field(t) for t in [100, 111, 122, 133]]
    target = measured_field(144, prefix=prefix, reliable=True)
    found = classified_field_ids(anchors+[target])
    assert all(id(line) in found for line in anchors)
    assert id(target) not in found


@pytest.mark.parametrize('boundary', ['no-strict-run', 'two-strict-anchors', 'distant',
                                     'field-height', 'different-lane', 'outward-chain'])
def test_uncertain_prefix_extension_cannot_create_or_escape_its_original_strict_anchors(boundary):
    anchors = [measured_field(t) for t in [100, 111, 122, 133]]
    target = measured_field(144, prefix="Yvk'")
    extra = []
    if boundary == 'no-strict-run':
        anchors = [measured_field(t, prefix='IlL') for t in [100, 111, 122, 133]]
    elif boundary == 'two-strict-anchors':
        anchors = anchors[:2]
        target = measured_field(122, prefix="Yvk'")
    elif boundary == 'distant':
        target = measured_field(200, prefix="Yvk'")
    elif boundary == 'field-height':
        target = measured_field(144, prefix="Yvk'", height=20)
    elif boundary == 'different-lane':
        target = measured_field(144, prefix="Yvk'", left=250)
    elif boundary == 'outward-chain':
        extra = [target]
        target = measured_field(155, prefix="Yvk'")
    found = classified_field_ids(anchors+extra+[target])
    if boundary not in ('no-strict-run', 'two-strict-anchors'):
        assert all(id(line) in found for line in anchors)
    assert id(target) not in found, ('Unproved source prefix must remain a prose obstacle', boundary)
