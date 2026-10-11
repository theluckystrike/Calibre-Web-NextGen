"""Actual source88 LEFT footer; independent from the prior RIGHT-side witness."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import pytest
from cps.services.reflow import extract, skeleton

pytestmark = pytest.mark.unit


def witness():
    data = json.loads((Path(__file__).parents[1] / 'fixtures/reflow/close_scan_footer.json').read_text())
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


def target(raw):
    return [l for b in raw.blocks if b.number in (6, 7) for l in b.lines]


def conserve(raw, before, body, notes):
    assert asdict(raw) == before
    old = [id(l) for b in raw.blocks for l in b.lines]
    new = [id(l) for b in body for l in b.lines] + [id(l) for n in notes for l in n.lines]
    assert sorted(old) == sorted(new)


def test_actual_close_raised_footer_and_its_short_outlying_ocr_tail_are_one_note():
    raw, style = witness(); rows = target(raw); before = asdict(raw)
    assert rows[0].spans[0].text.strip() == '©'
    assert rows[-1].text == 'be disregarded.'
    body, notes = split(raw, style)
    matches = [n for n in notes if any(l in n.lines for l in rows)]
    assert len(matches) == 1, 'All printed left-footnote rows must leave body flow together'
    note = matches[0]
    assert all(l in note.lines for l in rows)
    assert note.number is None and note.uncertain
    assert not any(l in b.lines for b in body for l in rows)
    assert note.bbox[0] <= 37.92 and note.bbox[1] <= 535.92
    assert note.bbox[2] >= 373.92 - .01 and note.bbox[3] >= 564.72 - .01
    assert any(l.text.endswith('seek to') for b in body for l in b.lines)
    assert any(l.text.startswith('peer beneath') for b in body for l in b.lines)
    conserve(raw, before, body, notes)


@pytest.mark.parametrize('boundary', ['reliable_marker', 'alphabetic_marker', 'degree_marker', 'baseline_marker', 'large_marker', 'attached', 'body_type', 'caption', 'table', 'native', 'no_hanging_row'])
def test_close_gap_does_not_by_itself_turn_unproved_prose_into_a_note(boundary):
    raw, style = witness(); rows = target(raw); opening = rows[0].spans[0]
    if boundary == 'reliable_marker': opening.uncertain = False
    elif boundary == 'alphabetic_marker': opening.text = 'a '
    elif boundary == 'degree_marker': opening.text = '° '
    elif boundary == 'baseline_marker': opening.bbox = tuple(v + 5 if i in (1, 3) else v for i, v in enumerate(opening.bbox))
    elif boundary == 'large_marker': opening.size = 11
    elif boundary == 'attached':
        for b in raw.blocks:
            if b.number not in (6, 7): continue
            b.bbox = tuple(v - 4 if i in (1, 3) else v for i, v in enumerate(b.bbox))
            for l in b.lines:
                l.bbox = tuple(v - 4 if i in (1, 3) else v for i, v in enumerate(l.bbox))
                for s in l.spans:
                    s.bbox = tuple(v - 4 if i in (1, 3) else v for i, v in enumerate(s.bbox)); s.origin_y -= 4
    elif boundary == 'body_type':
        for l in rows:
            for s in l.spans[1:]: s.size = 11
    elif boundary == 'caption': opening.text = 'Chart 7 '
    elif boundary == 'table': style.scan_table_label_boxes = {raw.pno: [next(b.bbox for b in raw.blocks if b.number == 6)]}
    elif boundary == 'native':
        for l in rows:
            for s in l.spans: s.font = 'Times'
    elif boundary == 'no_hanging_row':
        b = next(b for b in raw.blocks if b.number == 6); b.lines = b.lines[:1]; b.bbox = b.lines[0].bbox
        rows = target(raw)
    before = asdict(raw); body, notes = split(raw, style)
    assert not any(l in n.lines for n in notes for l in rows)
    assert all(any(l in b.lines for b in body) for l in rows)
    conserve(raw, before, body, notes)


@pytest.mark.parametrize('boundary', ['body_type', 'far_below', 'other_indent', 'caption', 'table', 'native'])
def test_close_footer_does_not_swallow_unproved_short_following_body(boundary):
    raw, style = witness(); tail = next(b for b in raw.blocks if b.number == 7)
    if boundary == 'body_type':
        for s in tail.lines[0].spans: s.size = 11
    elif boundary in ('far_below', 'other_indent'):
        indices = (1, 3) if boundary == 'far_below' else (0, 2)
        tail.bbox = tuple(v + 10 if i in indices else v for i, v in enumerate(tail.bbox))
        for l in tail.lines:
            l.bbox = tuple(v + 10 if i in indices else v for i, v in enumerate(l.bbox))
            for s in l.spans: s.bbox = tuple(v + 10 if i in indices else v for i, v in enumerate(s.bbox))
    elif boundary == 'caption': tail.lines[0].spans[0].text = 'Chart 7 '
    elif boundary == 'table': style.scan_table_label_boxes = {raw.pno: [tail.bbox]}
    elif boundary == 'native':
        for s in tail.lines[0].spans: s.font = 'Times'
    before = asdict(raw); body, notes = split(raw, style)
    assert not any(l in n.lines for n in notes for l in tail.lines)
    assert all(any(l in b.lines for b in body) for l in tail.lines)
    conserve(raw, before, body, notes)
