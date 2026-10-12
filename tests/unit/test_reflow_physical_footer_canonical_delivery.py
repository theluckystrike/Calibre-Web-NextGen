"""ROOT-owned whole-stage footer delivery and source-ink conservation tests.

The source pixels and complete retained pages are real original-PDF evidence.
The oracle was physically reviewed independently. Split ownership alone cannot
pass: no ordinary body figure may contain any printed-note glyph territory.
"""
from collections import Counter
from dataclasses import asdict, fields
from functools import lru_cache
from pathlib import Path
import copy
import hashlib
import json
import pymupdf
import pytest
from cps.services.reflow import extract, skeleton

pytestmark = pytest.mark.unit
FIXTURE = Path(__file__).parents[1] / 'fixtures/reflow/physical_footer_canonical_delivery.json'


def digest(values):
    return hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


@lru_cache()
def data():
    return json.loads(FIXTURE.read_text())


def raw_page(values):
    values = copy.deepcopy(values)
    blocks = []
    for block in values.pop('blocks'):
        lines = []
        for line in block.pop('lines'):
            spans = [extract.Span(**dict(s, bbox=tuple(s['bbox']))) for s in line.pop('spans')]
            lines.append(extract.Line(**dict(line, spans=spans, bbox=tuple(line['bbox']))))
        blocks.append(extract.Block(**dict(block, lines=lines, bbox=tuple(block['bbox']))))
    images = [extract.Image(**dict(i, bbox=tuple(i['bbox']))) for i in values.pop('images')]
    return extract.RawPage(**dict(values, blocks=blocks, images=images))


def inputs(case):
    book = data()['books'][str(case['book'])]
    record = book['pages'][str(case['page'])]
    raw = raw_page(record['raw'])
    assert digest(asdict(raw)) == record['raw_sha256']
    values = copy.deepcopy(book['book_style'])
    for key, value in values.items():
        if isinstance(value, dict) and all(str(p).isdigit() for p in value):
            values[key] = {int(p): v for p, v in value.items()}
    for key in ('folio_boxes',):
        values[key] = {p: tuple(box) for p, box in values[key].items()}
    for key in ('local_running_boxes', 'repeated_head_boxes', 'portrait_head_boxes',
                'scan_spread_head_boxes', 'scan_table_label_boxes', 'scan_note_lane_boxes'):
        values[key] = {p: [tuple(box) for box in boxes] for p, boxes in values[key].items()}
    # The retained whole-book style contains actual independent peer context.
    # Older source versions simply do not have newly introduced profile fields.
    accepted = {f.name for f in fields(skeleton.BookStyle)}
    style = skeleton.BookStyle(**{k: v for k, v in values.items() if k in accepted})
    rows = []
    for target in case['printed_note_rows']:
        row = raw.blocks[target['block_index']].lines[target['line_index']]
        assert digest(asdict(row)) == target['source_row_sha256']
        assert row.text == target['text'] and list(row.bbox) == target['bbox']
        rows.append(row)
    pixels = record['source_pixels']
    payload = (FIXTURE.parent / pixels['path']).read_bytes()
    assert hashlib.sha256(payload).hexdigest() == pixels['sha256']
    assert pixels['source_geometry'] == raw.source_geometry and pixels['unmasked']
    doc = pymupdf.open()
    # Canonical figure analysis addresses probe._doc[raw.pno], so page identity
    # is preserved rather than silently exercising a different pixel frame.
    for _ in range(raw.pno + 1):
        doc.new_page(width=raw.width, height=raw.height)
    doc[raw.pno].insert_image(pymupdf.Rect(pixels['reading_bbox']), stream=payload)
    return raw, style, rows, doc


def classify(case):
    raw, style, rows, doc = inputs(case)
    try:
        before = asdict(raw)
        probe = extract.ScanPixelProbe(doc, raw.pno,
            mask=[line.bbox for block in raw.text_blocks for line in block.lines])
        result = skeleton.page_skeleton(raw, style, pixel_probe=probe)
        assert asdict(raw) == before, 'Canonical analysis must not rewrite source literal or geometry'
        return raw, rows, result, doc
    except BaseException:
        doc.close()
        raise


def is_note(region):
    return region.kind == 'note' or region.reason == 'ocr_uncertain_note'


POSITIVES = [c for c in data()['cases'] if c['physically_verified_note']]
NEGATIVES = [c for c in data()['cases'] if not c['physically_verified_note']]


@pytest.mark.parametrize('case', POSITIVES, ids=lambda c: c['name'])
def test_full_canonical_stage_keeps_every_physically_printed_note_row(case):
    raw, rows, result, doc = classify(case)
    try:
        wrong = []
        for target, row in zip(case['printed_note_rows'], rows):
            owners = [r for r in result.regions if any(row is line for line in r.lines)]
            if len(owners) != 1 or not is_note(owners[0]):
                wrong.append((target['line_id'], [(r.kind, r.reason) for r in owners]))
        assert not wrong, wrong
    finally:
        doc.close()


@pytest.mark.parametrize('case', POSITIVES, ids=lambda c: c['name'])
def test_body_figure_core_does_not_reprint_any_physically_owned_note_ink(case):
    raw, rows, result, doc = classify(case)
    try:
        overlaps = []
        for region in result.regions:
            if region.kind != 'figure' or is_note(region):
                continue
            for target, row in zip(case['printed_note_rows'], rows):
                common = pymupdf.Rect(region.bbox) & pymupdf.Rect(row.bbox)
                if common.is_empty:
                    continue
                # An empty overlap/padded white margin does not prove reprint.
                # Count actual original note ink in the figure's core rectangle.
                pix = doc[raw.pno].get_pixmap(clip=common,
                    matrix=pymupdf.Matrix(3, 3), colorspace=pymupdf.csGRAY, alpha=False)
                ink = sum(sample < 200 for sample in pix.samples)
                if ink > 2:
                    overlaps.append((target['line_id'], region.reason, ink, list(common)))
        assert not overlaps, overlaps
    finally:
        doc.close()


@pytest.mark.parametrize('case', data()['cases'], ids=lambda c: c['name'])
def test_canonical_stage_conserves_every_original_source_row_exactly_once(case):
    raw, _, result, doc = classify(case)
    try:
        expected = Counter(digest(asdict(line)) for block in raw.text_blocks for line in block.lines)
        actual = Counter(digest(asdict(line)) for r in result.regions
            for line in r.lines + r.caption_lines)
        assert actual == expected, {'missing': expected - actual, 'duplicated': actual - expected}
    finally:
        doc.close()


@pytest.mark.parametrize('case', NEGATIVES, ids=lambda c: c['name'])
def test_real_chart_table_and_quoted_body_pages_are_not_absorbed_as_notes(case):
    raw, _, result, doc = classify(case)
    try:
        assert not [r for r in result.regions if is_note(r)]
    finally:
        doc.close()


def test_native_source_body_with_raised_reference_stays_body():
    # A real native PDF text layer, rather than a font-only mutation of a scan
    # note, establishes this negative's source provenance and body typography.
    with pymupdf.open() as doc:
        page = doc.new_page(width=350, height=500)
        page.insert_textbox((30, 30, 320, 420),
            'An authored paragraph explains the diagram and continues in ordinary body type. ' * 8,
            fontsize=10)
        page.insert_text((30, 450), 'The concluding body sentence includes a reference', fontsize=10)
        page.insert_text((257, 446), '3', fontsize=5)
        raw = extract.read_page(doc, 0)
        before = asdict(raw)
        result = skeleton.page_skeleton(raw, skeleton.BookStyle(body_size=10))
        assert not any(is_note(r) for r in result.regions)
        assert any('concluding body sentence' in r.text for r in result.regions if r.kind == 'body')
        assert asdict(raw) == before


@pytest.mark.parametrize('book,page,scope', [
    (566, 30, (490, 256, 720, 426)),
    (566, 47, (145, 155, 350, 225)),
    (561, 4, (65, 40, 330, 290)),
    (561, 42, (60, 145, 370, 180)),
])
def test_real_neighboring_chart_and_table_source_ink_remains_in_figures(book, page, scope):
    # Physically viewed source interior subscopes already present in baseline,
    # excluding notes/prose. Full-source chart recall remains a separate
    # diagnostic; later publishing can expand a canonical figure core.
    # In particular56630's old speculative carrier starts BELOW the caption:
    # deleting that empty proposal is allowed; deleting the real table is not.
    from PIL import Image, ImageDraw
    case = next(c for c in data()['cases'] if c['book'] == book and c['page'] == page)
    raw, _, result, doc = classify(case)
    try:
        box = pymupdf.Rect(scope)
        pix = doc[raw.pno].get_pixmap(clip=box, matrix=pymupdf.Matrix(3, 3),
            colorspace=pymupdf.csGRAY, alpha=False)
        mask = Image.new('L', (pix.width, pix.height), 0)
        draw = ImageDraw.Draw(mask)
        for region in result.regions:
            if region.kind != 'figure' or is_note(region):
                continue
            common = box & pymupdf.Rect(region.bbox)
            if not common.is_empty:
                draw.rectangle(((common.x0 - box.x0) * 3, (common.y0 - box.y0) * 3,
                    (common.x1 - box.x0) * 3, (common.y1 - box.y0) * 3), fill=255)
        covered = mask.tobytes()
        ink = sum(sample < 200 for sample in pix.samples)
        conserved = sum(sample < 200 and covered[i] != 0 for i, sample in enumerate(pix.samples))
        assert ink > 100, 'The actual preservation scope must contain meaningful original source ink'
        assert conserved / ink >= .99, (book, page, conserved, ink,
            [(r.reason, r.bbox) for r in result.regions if r.kind == 'figure'])
    finally:
        doc.close()


@pytest.mark.parametrize('book,page,prefix', [
    (566, 30, 'Figure 10: Table of major dignities'),
    (561, 4, 'Chart 1:'),
    (561, 27, 'The Order of the Cosmos'),
    (561, 94, 'Appendix:'),
    (561, 94, 'Some Popular Fallacies'),
    (566, 26, 'to the overall style of energy'),
    (566, 25, 'and the Ahwaz, and the boundaries'),
])
def test_real_caption_and_opposing_authored_opener_rows_remain_source_content(book, page, prefix):
    case = next(c for c in data()['cases'] if c['book'] == book and c['page'] == page)
    raw, _, result, doc = classify(case)
    try:
        targets = [line for block in raw.text_blocks for line in block.lines if line.text.startswith(prefix)]
        assert len(targets) == 1, 'The literal preservation target is unique in this physical source page'
        row = targets[0]
        owners = [r for r in result.regions if any(row is line for line in r.lines + r.caption_lines)]
        assert len(owners) == 1
        assert not is_note(owners[0]) and owners[0].kind != 'furniture'
    finally:
        doc.close()
