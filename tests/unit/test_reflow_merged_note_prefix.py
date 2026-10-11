"""Actual merged note marker is proved by source pixels, never decoded."""
from dataclasses import asdict
import json
from pathlib import Path
import pymupdf
import pytest
from cps.services.reflow import extract, skeleton
pytestmark=pytest.mark.unit

def witness():
    data = json.loads((Path(__file__).parents[1] / 'fixtures/reflow/merged_prefix_scan_footer.json').read_text())
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




def pixels(raw,variant=None):
    doc=pymupdf.open();page=doc.new_page(width=raw.width,height=raw.height)
    page.insert_image(pymupdf.Rect(440,513,790,560),filename=str(Path(__file__).parents[1]/'fixtures/reflow/merged_prefix_scan_footer.png'))
    if variant:
        page.draw_rect(pymupdf.Rect(457.5,547.5,463,552),color=None,fill=(1,1,1),overlay=True)
        if variant in ('baseline','large','quote'):
            top,bottom=(551,554)if variant=='baseline'else(547.5,554)if variant=='large'else(548.3,549.5)
            for x in (458.35,461.68):page.draw_rect(pymupdf.Rect(x,top,x+.67,bottom),color=None,fill=(0,0,0),overlay=True)
        if variant=='joined':page.draw_rect(pymupdf.Rect(458.35,548.3,470,551.3),color=None,fill=(0,0,0),overlay=True)
    return doc

def test_actual_pixels_prove_small_raised_prefix_inside_merged_word_box():
    raw,style=witness();target=next(b for b in raw.blocks if b.number==15)
    with pixels(raw) as doc:
        proof=extract.ScanPixelProbe(doc,0).source_raised_prefix(target.lines[0].spans[0].bbox)
    assert proof is not None
    assert set(proof)>={'prefix_bbox','lexical_bbox','gap'}
    assert 457.5<=proof['prefix_bbox'][0]<=459
    assert 462<=proof['prefix_bbox'][2]<=463.5
    assert proof['gap']>=4.5
    assert proof['prefix_bbox'][3]<=proof['lexical_bbox'][3]-2

@pytest.mark.parametrize('variant',['removed','baseline','large','quote','joined'])
def test_prefix_probe_rejects_absent_unraised_large_quote_or_joined_ink(variant):
    raw,style=witness();target=next(b for b in raw.blocks if b.number==15)
    with pixels(raw,variant) as doc:
        assert extract.ScanPixelProbe(doc,0).source_raised_prefix(target.lines[0].spans[0].bbox) is None

def test_actual_single_row_bibliography_leaves_connectionwith_Mars_sentence():
    raw,style=witness();target=next(b for b in raw.blocks if b.number==15);before=asdict(raw)
    with pixels(raw) as doc:
        body,notes=skeleton._split_off_notes(raw,style,skeleton.PageSkeleton(raw.pno,raw.width,raw.height),extract.ScanPixelProbe(doc,0))
    assert asdict(raw)==before
    owned=[n for n in notes if any(l in n.lines for l in target.lines)]
    assert len(owned)==1,'The printed Ramesey note must not remain between connection with and Mars'
    assert owned[0].number is None and owned[0].uncertain
    assert all(l in owned[0].lines for l in target.lines)
    assert not any(l in b.lines for b in body for l in target.lines)
    assert sorted(id(l)for b in raw.blocks for l in b.lines)==sorted([id(l)for b in body for l in b.lines]+[id(l)for n in notes for l in n.lines])

@pytest.mark.parametrize('boundary',['removed_prefix','baseline_prefix','large_prefix','caption','table','native','body_type','not_terminal'])
def test_merged_prefix_footer_needs_source_pixels_and_footer_geometry(boundary):
    raw,style=witness();target=next(b for b in raw.blocks if b.number==15);variant=None
    if boundary.endswith('_prefix'):variant={'removed_prefix':'removed','baseline_prefix':'baseline','large_prefix':'large'}[boundary]
    elif boundary=='caption':target.lines[0].spans[0].text='Chart 7 '
    elif boundary=='table':style.scan_table_label_boxes[raw.pno]=[target.bbox]
    elif boundary=='native':
        for sp in target.lines[0].spans:sp.font='Times'
    elif boundary=='body_type':
        for sp in target.lines[0].spans:sp.size=11.5
    elif boundary=='not_terminal':
        later=extract.Line([extract.Span('Ordinary body paragraph continues below this source label.',11,'ocr',0,(458,570,788,582),582)],(458,570,788,582))
        raw.blocks.append(extract.Block(999,later.bbox,[later]))
    before=asdict(raw)
    with pixels(raw,variant) as doc:
        body,notes=skeleton._split_off_notes(raw,style,skeleton.PageSkeleton(raw.pno,raw.width,raw.height),extract.ScanPixelProbe(doc,0))
    assert asdict(raw)==before
    assert not any(l in n.lines for n in notes for l in target.lines)
    assert all(any(l in b.lines for b in body)for l in target.lines)
