"""A second damaged raised opening inside a source-proved footer, not a chart degree."""
from dataclasses import asdict
import json
from pathlib import Path
import pytest
from cps.services.reflow import extract, skeleton

pytestmark = pytest.mark.unit


def witness():
    data = json.loads((Path(__file__).parents[1] / 'fixtures/reflow/adjacent_scan_footer.json').read_text())
    d = data['raw']; blocks = []
    for b in d.pop('blocks'):
        lines = [extract.Line([extract.Span(**dict(s, bbox=tuple(s['bbox']))) for s in l['spans']], tuple(l['bbox']), spacing_uncertain=l.get('spacing_uncertain', False), transcription_uncertain=l.get('transcription_uncertain', False)) for l in b['lines']]
        blocks.append(extract.Block(b['number'], tuple(b['bbox']), lines, kind=b['kind']))
    images = [extract.Image(**dict(i, bbox=tuple(i['bbox']))) for i in d.pop('images')]
    raw = extract.RawPage(**dict(d, blocks=blocks, images=images))
    values = data['style']
    for key in ['folio_boxes', 'local_running_boxes', 'repeated_head_boxes', 'portrait_head_boxes', 'scan_spread_head_boxes', 'scan_table_label_boxes', 'scan_note_lane_boxes']:
        values[key] = {int(p): [tuple(box) for box in boxes] for p, boxes in values[key].items()}
    return raw, skeleton.BookStyle(**values)


def split(raw, style):
    return skeleton._split_off_notes(raw, style, skeleton.PageSkeleton(raw.pno, raw.width, raw.height))


def test_entire_adjacent_printed_footer_leaves_body_despite_ocr_degree_and_type_outliers():
    raw, style = witness(); rows = [l for b in raw.blocks if b.number in (5, 6) for l in b.lines]
    assert rows[0].spans[0].text.strip() == '®'
    assert rows[-1].spans[0].text.strip() == '°'
    before = asdict(raw); body, notes = split(raw, style)
    matched = [n for n in notes if any(l in n.lines for l in rows)]
    assert len(matched) == 1
    assert all(l in matched[0].lines for l in rows), 'Printed second note must not invalidate its preceding source-note crop'
    assert matched[0].number is None and matched[0].uncertain
    assert not any(l in b.lines for b in body for l in rows)
    assert matched[0].bbox[3] >= 561.84 - .01
    assert asdict(raw) == before
    assert sorted(id(l) for b in raw.blocks for l in b.lines) == sorted([id(l) for b in body for l in b.lines] + [id(l) for n in notes for l in n.lines])


@pytest.mark.parametrize('boundary', ['unproved_seed', 'reliable', 'baseline', 'large', 'marker_indent', 'text_indent', 'deep_overlap', 'large_gap', 'body_type', 'caption', 'table', 'native'])
def test_ambiguous_degree_opening_needs_an_independent_aligned_source_note(boundary):
    raw, style = witness(); first = next(b for b in raw.blocks if b.number == 5); later = next(b for b in raw.blocks if b.number == 6); marker = later.lines[0].spans[0]
    if boundary == 'unproved_seed': first.lines[0].spans[0].uncertain = False
    elif boundary == 'reliable': marker.uncertain = False
    elif boundary == 'baseline': marker.bbox = tuple(v + 5 if i in (1, 3) else v for i, v in enumerate(marker.bbox))
    elif boundary == 'large': marker.size = 11
    elif boundary in ('marker_indent', 'text_indent'):
        s = marker if boundary == 'marker_indent' else later.lines[0].spans[1]
        s.bbox = tuple(v + 8 if i in (0, 2) else v for i, v in enumerate(s.bbox))
    elif boundary in ('deep_overlap', 'large_gap'):
        delta = -6 if boundary == 'deep_overlap' else 10
        later.bbox = tuple(v + delta if i in (1, 3) else v for i, v in enumerate(later.bbox))
        for l in later.lines:
            l.bbox = tuple(v + delta if i in (1, 3) else v for i, v in enumerate(l.bbox))
            for s in l.spans: s.bbox = tuple(v + delta if i in (1, 3) else v for i, v in enumerate(s.bbox))
    elif boundary == 'body_type':
        for s in later.lines[0].spans[1:]: s.size = 11
    elif boundary == 'caption': marker.text = 'Chart 7 '
    elif boundary == 'table': style.scan_table_label_boxes = {raw.pno: [later.bbox]}
    elif boundary == 'native':
        for s in later.lines[0].spans: s.font = 'Times'
    before = asdict(raw); body, notes = split(raw, style)
    assert not any(l in n.lines for n in notes for l in later.lines)
    assert all(any(l in b.lines for b in body) for l in later.lines)
    assert asdict(raw) == before
