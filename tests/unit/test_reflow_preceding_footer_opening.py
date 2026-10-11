"""A physically raised damaged note precedes an independently proved footer.

Exact source56115 geometry; the glyph remains unnumbered and unread.
"""
from dataclasses import asdict
import json
from pathlib import Path
import pytest
from cps.services.reflow import extract, skeleton
pytestmark = pytest.mark.unit

def witness():
    data = json.loads((Path(__file__).parents[1] / 'fixtures/reflow/preceding_scan_footer.json').read_text())
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



def assert_partition(raw,style):
    before=asdict(raw);body,notes=split(raw,style)
    assert asdict(raw)==before
    assert sorted(id(l)for b in raw.blocks for l in b.lines)==sorted([id(l)for b in body for l in b.lines]+[id(l)for n in notes for l in n.lines])
    return body,notes

def test_actual_preceding_bibliography_note_leaves_Ifit_perverts_sentence_whole():
    raw,style=witness();target=next(b for b in raw.blocks if b.number==12)
    body,notes=assert_partition(raw,style)
    owned=[n for n in notes if any(l in n.lines for l in target.lines)]
    assert len(owned)==1,'The printed bibliography must not remain between If it and perverts'
    assert all(l in owned[0].lines for l in target.lines)
    assert owned[0].number is None and owned[0].uncertain
    assert not any(l in b.lines for b in body for l in target.lines)
    assert any(l.text.rstrip().endswith('If it')for b in body for l in b.lines)

@pytest.mark.parametrize('boundary',['no_independent_anchor','reliable_degree','baseline_degree','large_degree','alphabetic_degree','marker_shift','text_shift','large_gap','body_height','caption','table','native'])
def test_degree_shaped_opening_needs_independent_footer_and_original_geometry(boundary):
    raw,style=witness();target=next(b for b in raw.blocks if b.number==12);anchor=next(b for b in raw.blocks if b.number==13);marker=target.lines[0].spans[0]
    if boundary=='no_independent_anchor':raw.blocks.remove(anchor)
    elif boundary=='reliable_degree':marker.uncertain=False
    elif boundary=='baseline_degree':marker.bbox=tuple(v+6 if i in (1,3)else v for i,v in enumerate(marker.bbox))
    elif boundary=='large_degree':marker.size=11
    elif boundary=='alphabetic_degree':marker.text='a '
    elif boundary in ('marker_shift','text_shift'):
        sp=marker if boundary=='marker_shift'else target.lines[0].spans[1]
        sp.bbox=tuple(v+12 if i in (0,2)else v for i,v in enumerate(sp.bbox))
    elif boundary=='large_gap':
        anchor.bbox=tuple(v+20 if i in (1,3)else v for i,v in enumerate(anchor.bbox))
        for l in anchor.lines:
            l.bbox=tuple(v+20 if i in (1,3)else v for i,v in enumerate(l.bbox))
            for sp in l.spans:sp.bbox=tuple(v+20 if i in (1,3)else v for i,v in enumerate(sp.bbox))
    elif boundary=='body_height':
        for l in target.lines:
            for sp in l.spans[1:] if l is target.lines[0] else l.spans:
                sp.size=11;sp.bbox=(sp.bbox[0],sp.bbox[1],sp.bbox[2],sp.bbox[1]+11)
    elif boundary=='caption':marker.text='Chart 7 '
    elif boundary=='table':style.scan_table_label_boxes[raw.pno]=[target.bbox]
    elif boundary=='native':
        for l in target.lines:
            for sp in l.spans:sp.font='Times'
    body,notes=assert_partition(raw,style)
    assert not any(l in n.lines for n in notes for l in target.lines)
    assert all(any(l in b.lines for b in body)for l in target.lines)
