"""Literal source footers: own complete notes, and preserve unproved prose/tables.

Root-owned independent source controls. No fixture changes or classifier calls
are allowed to manufacture the source evidence used by the lane learner.
"""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import pytest
from cps.services.reflow import extract, skeleton
pytestmark = pytest.mark.unit
FIXTURES = json.loads((Path(__file__).parents[1] / 'fixtures/reflow/damaged_footer_continuations.json').read_text())
INKS = {(561,56):(454.26667277,545.119995,456.93333944,547.78666178),
        (561,88):(458.69,515.09,460.69,517.09)}

class Probe:
    def __init__(self, ink=None): self.ink=ink
    def source_ink_bounds(self, box):
        b=self.ink
        if b and box[0]<=b[0] and box[1]<=b[1] and box[2]>=b[2] and box[3]>=b[3]: return b
        return None
    ink_bounds=source_ink_bounds

def witness(book, page):
    d=deepcopy(next(f for f in FIXTURES if (f['book'],f['page'])==(book,page)))
    geom=d['source_geometry'];rect=geom['page_rect'];w,h=rect[2]-rect[0],rect[3]-rect[1]
    if geom.get('orientation') in (90,270): w,h=h,w
    groups={}
    for row in d['rows']:
        s=row['source'];line=extract.Line([extract.Span(**dict(sp,bbox=tuple(sp['bbox']))) for sp in s['spans']],tuple(s['bbox']))
        groups.setdefault(row['block_index'],[]).append(line)
    blocks=[]
    for n,ls in groups.items():
        box=(min(l.bbox[0] for l in ls),min(l.bbox[1] for l in ls),max(l.bbox[2] for l in ls),max(l.bbox[3] for l in ls))
        blocks.append(extract.Block(n,box,ls))
    raw=extract.RawPage(page,w,h,blocks,images=[extract.Image((0,0,w,h),1)],source_geometry=geom,text_layer_invisible=True)
    targets=[l for b in blocks if b.number in d['target_blocks'] for l in b.lines]
    return raw,targets

def split(raw, style, probe=None):
    return skeleton._split_off_notes(raw,style,skeleton.PageSkeleton(raw.pno,raw.width,raw.height),probe)

def assert_owned_and_conserved(raw, targets, style, probe=None):
    before=asdict(raw);body,notes=split(raw,style,probe)
    for row in targets:
        assert not any(row in b.lines for b in body),f'Printed footer remains body: {row.text}'
        assert sum(row in n.lines for n in notes)==1
    assert all(n.number is None and n.uncertain for n in notes if any(l in targets for l in n.lines))
    assert asdict(raw)==before
    assert sum(len(l.spans) for b in body for l in b.lines)+sum(len(l.spans) for n in notes for l in n.lines)==sum(len(l.spans) for b in raw.blocks for l in b.lines)
    assert all(any(l in b.lines for b in body) for src in raw.blocks for l in src.lines if l not in targets)
    if probe and probe.ink:
        ink=probe.ink
        assert any(n.bbox[0]<=ink[0] and n.bbox[1]<=ink[1] and n.bbox[2]>=ink[2] and n.bbox[3]>=ink[3] for n in notes), 'Unowned printed opening ink must remain inside note evidence'

@pytest.mark.parametrize('page',[45,56,88])
def test_detached_footer_owns_every_small_type_continuation_despite_ocr_outliers(page):
    raw,targets=witness(561,page)
    assert_owned_and_conserved(raw,targets,skeleton.BookStyle(body_size=11),Probe(INKS.get((561,page))))

def test_rounded_ocr_type_does_not_hide_the_actual_566_source8_note():
    raw,targets=witness(566,8)
    assert_owned_and_conserved(raw,targets,skeleton.BookStyle(body_size=9))

def learned_style(peers):
    style=skeleton.BookStyle(body_size=11)
    learner=getattr(skeleton,'_repeated_scan_note_lanes',None)
    style.scan_note_lane_boxes=learner(peers,11,{}) if learner else {}
    return style

def peer_pages(side):
    return [witness(561,p)[0] for p in ([9,19,67] if side=='right' else [14,26,69])]

@pytest.mark.parametrize('page,side',[(15,'left'),(52,'right')])
def test_three_independently_marked_source_pages_prove_the_matching_unmarked_note_lane(page,side):
    raw,targets=witness(561,page)
    # Target participates in matching, but cannot prove itself: it has no marker.
    style=learned_style(peer_pages(side)+[raw])
    assert_owned_and_conserved(raw,targets,style)

@pytest.mark.parametrize('setup',['two_pages','duplicate_page','wrong_side','unproved_peers'])
def test_weak_or_other_side_recurrence_does_not_own_markerless_prose(setup):
    raw,targets=witness(561,52);peers=peer_pages('right')
    if setup=='two_pages': peers=peers[:2]
    elif setup=='duplicate_page': peers=[deepcopy(peers[0]) for _ in range(3)]
    elif setup=='wrong_side': peers=peer_pages('left')
    else:
        for p in peers:
            for b in p.blocks:
                for l in b.lines:
                    for s in l.spans:
                        if not any(c.isalnum() for c in s.text):s.uncertain=False
    body,notes=split(raw,learned_style(peers+[raw]))
    assert not any(l in n.lines for n in notes for l in targets)
    assert all(any(l in b.lines for b in body) for l in targets)

@pytest.mark.parametrize('boundary',['body_type','attached','caption','table'])
def test_note_lane_does_not_absorb_body_type_attached_caption_or_table(boundary):
    raw,targets=witness(561,52)
    if boundary=='body_type':
        for l in targets:
            for s in l.spans:s.size=11
    elif boundary=='attached':
        for l in targets:
            l.bbox=tuple(v-20 if i in (1,3) else v for i,v in enumerate(l.bbox))
            for s in l.spans:s.bbox=tuple(v-20 if i in (1,3) else v for i,v in enumerate(s.bbox));s.origin_y-=20
        b=next(b for b in raw.blocks if any(l in targets for l in b.lines));b.bbox=targets[0].bbox
    elif boundary=='caption':targets[0].spans[0].text='Chart 7 '
    style=learned_style(peer_pages('right')+[raw])
    if boundary=='table':style.scan_table_label_boxes={raw.pno:[targets[0].bbox]}
    body,notes=split(raw,style)
    assert not any(l in n.lines for n in notes for l in targets)
    assert all(any(l in b.lines for b in body) for l in targets)

def test_small_footer_seed_does_not_swallow_a_later_larger_body_paragraph():
    raw,targets=witness(561,56)
    for s in targets[-1].spans:s.size=11
    body,notes=split(raw,skeleton.BookStyle(body_size=11),Probe(INKS[(561,56)]))
    assert any(targets[-1] in b.lines for b in body)
    assert not any(targets[-1] in n.lines for n in notes)

def test_native_worksheet_text_is_outside_the_ocr_footer_repair():
    d=json.loads((Path(__file__).parents[1]/'fixtures/reflow/native_scan_table.json').read_text())
    blocks=[]
    for b in d.pop('blocks'):
        ls=[]
        for l in b['lines']:
            ss=[extract.Span(**dict(s,bbox=tuple(s['bbox']))) for s in l['spans']]
            ls.append(extract.Line(ss,tuple(l['bbox']),spacing_uncertain=l.get('spacing_uncertain',False),transcription_uncertain=l.get('transcription_uncertain',False)))
        blocks.append(extract.Block(b['number'],tuple(b['bbox']),ls,kind=b['kind']))
    images=[extract.Image(**dict(i,bbox=tuple(i['bbox']))) for i in d.pop('images')]
    raw=extract.RawPage(**dict(d,blocks=blocks,images=images))
    class NativeProbe:
        def source_ink_bounds(self,box):
            # A small raised stroke next to VENUS can belong to its worksheet.
            return (box[2]-3,box[1]+1,box[2]-1,box[1]+3)
        ink_bounds=source_ink_bounds
    result=skeleton._detached_scan_note_territories(raw,skeleton.BookStyle(body_size=9),NativeProbe())
    assert not result,'Trustworthy Cambria worksheet labels must stay native text'

def test_note_reclamation_preserves_full_page_anchor_checks_for_chart_degrees():
    data=json.loads((Path(__file__).parents[1]/'fixtures/reflow/scan_chart_note_anchors.json').read_text())
    d=data['raw'];blocks=[]
    for b in d.pop('blocks'):
        ls=[]
        for l in b['lines']:
            ss=[extract.Span(**dict(s,bbox=tuple(s['bbox']))) for s in l['spans']]
            ls.append(extract.Line(ss,tuple(l['bbox']),spacing_uncertain=l.get('spacing_uncertain',False),transcription_uncertain=l.get('transcription_uncertain',False)))
        blocks.append(extract.Block(b['number'],tuple(b['bbox']),ls,kind=b['kind']))
    images=[extract.Image(**dict(i,bbox=tuple(i['bbox']))) for i in d.pop('images')]
    raw=extract.RawPage(**dict(d,blocks=blocks,images=images))
    values=data['style']
    for key in ['folio_boxes','local_running_boxes','repeated_head_boxes','portrait_head_boxes','scan_spread_head_boxes','scan_table_label_boxes','scan_note_lane_boxes']:
        values[key]={int(p):[tuple(box) for box in boxes] for p,boxes in values[key].items()}
    style=skeleton.BookStyle(**values);before=asdict(raw)
    label=next(l for b in raw.blocks for l in b.lines if l.text=='27° BP o7')
    body,notes=split(raw,style)
    assert any(label in b.lines for b in body), 'Removing footer anchors must not turn chart degrees into note270'
    assert not any(label in n.lines for n in notes)
    assert asdict(raw)==before
    assert sum(len(l.spans) for b in body for l in b.lines)+sum(len(l.spans) for n in notes for l in n.lines)==sum(len(l.spans) for b in raw.blocks for l in b.lines)
