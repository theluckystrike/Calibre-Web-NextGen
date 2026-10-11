"""Actual three-line continuation of printed footnote5, source17 LEFT.

The source scan's measured divider proves its territory; no missing numeral
or corrected text is supplied. A short final body line must stay above it.
"""
from dataclasses import asdict
import json
from pathlib import Path
import pytest
from cps.services.reflow import extract,skeleton
pytestmark=pytest.mark.unit


def witness():
    data=json.loads((Path(__file__).parents[1]/'fixtures/reflow/unmarked_ruled_scan_footer.json').read_text());d=data['raw'];blocks=[]
    for b in d.pop('blocks'):
        lines=[extract.Line([extract.Span(**dict(s,bbox=tuple(s['bbox'])))for s in l['spans']],tuple(l['bbox']),spacing_uncertain=l.get('spacing_uncertain',False),transcription_uncertain=l.get('transcription_uncertain',False))for l in b['lines']]
        blocks.append(extract.Block(b['number'],tuple(b['bbox']),lines,kind=b['kind']))
    images=[extract.Image(**dict(i,bbox=tuple(i['bbox'])))for i in d.pop('images')]
    raw=extract.RawPage(**dict(d,blocks=blocks,images=images));values=data['style']
    for key in ['folio_boxes','local_running_boxes','repeated_head_boxes','portrait_head_boxes','scan_spread_head_boxes','scan_table_label_boxes','scan_note_lane_boxes']:
        values[key]={int(p):[tuple(box)for box in boxes]for p,boxes in values[key].items()}
    return raw,skeleton.BookStyle(**values)


class ActualDivider:
    """Unmodified source-pixel measurements recorded before the converter fix."""
    def __init__(self,boundary=None):
        self.boundary=boundary;self.queries=[]
        self.ink=(114.68000030517578,511.67332967122394,395.34666697184247,516.3399963378906)
        self.separator=dict(slope=-.003984948782368461,max_thickness=1.3333333333333333,occupied_fraction=.9404494382022472)
        if boundary=='misaligned':self.ink=tuple(v+30 if i in (0,2)else v for i,v in enumerate(self.ink))
        elif boundary=='thick':self.separator['max_thickness']=3
        elif boundary=='low_coverage':self.separator['occupied_fraction']=.5
        elif boundary=='body_overlap':self.ink=(self.ink[0],480,self.ink[2],484)
        elif boundary=='note_overlap':self.ink=(self.ink[0],519,self.ink[2],522)
    def source_ink_bounds(self,box):
        self.queries.append(tuple(box))
        if self.boundary=='absent':return None
        if box[0]<=self.ink[0] and box[1]<=self.ink[1] and box[2]>=self.ink[2] and box[3]>=self.ink[3]:return self.ink
        return None
    ink_bounds=source_ink_bounds
    def thin_separator(self,box,max_thickness):
        if self.boundary=='no_separator':return None
        return self.separator


def split(raw,style,probe):
    before=asdict(raw)
    body,notes=skeleton._split_off_notes(raw,style,skeleton.PageSkeleton(raw.pno,raw.width,raw.height),probe)
    assert asdict(raw)==before
    old=[id(l)for b in raw.blocks for l in b.lines];new=[id(l)for b in body for l in b.lines]+[id(l)for n in notes for l in n.lines]
    assert sorted(old)==sorted(new)
    return body,notes


def test_actual_unmarked_printed_footer_continuation_uses_source_divider():
    raw,style=witness();block=next(b for b in raw.blocks if b.number==5);probe=ActualDivider()
    body,notes=split(raw,style,probe)
    assert all(any(l in n.lines for n in notes)for l in block.lines)
    assert not any(l in b.lines for b in body for l in block.lines)
    owned=[n for n in notes if any(l in n.lines for l in block.lines)]
    assert len(owned)==1 and owned[0].number is None and owned[0].uncertain
    assert any(l.text=='for all situations.'for b in body for l in b.lines)
    # The blank source query starts AFTER the final short body line, rather
    # than trusting the earlier wide row used for typography.
    assert any(q[1]>=484.34-.01 and q[3]<=518.62+.01 for q in probe.queries)


@pytest.mark.parametrize('boundary',['absent','misaligned','thick','low_coverage','no_separator','body_overlap','note_overlap','no_probe','body_type','caption','table','native','single_row'])
def test_small_terminal_prose_needs_the_complete_source_divider_proof(boundary):
    raw,style=witness();block=next(b for b in raw.blocks if b.number==5);probe=ActualDivider(boundary)
    if boundary=='no_probe':probe=None
    elif boundary=='body_type':
        for l in block.lines:
            for s in l.spans:s.size=style.body_size+1;s.bbox=(s.bbox[0],s.bbox[1],s.bbox[2],s.bbox[1]+style.body_size)
    elif boundary=='caption':block.lines[0].spans[0].text='Chart 7 '
    elif boundary=='table':style.scan_table_label_boxes[raw.pno]=[block.bbox]
    elif boundary=='native':
        for l in block.lines:
            for s in l.spans:s.font='Times'
    elif boundary=='single_row':block.lines=block.lines[:1];block.bbox=block.lines[0].bbox
    body,notes=split(raw,style,probe)
    assert not any(l in n.lines for n in notes for l in block.lines)
    assert all(any(l in b.lines for b in body)for l in block.lines)
