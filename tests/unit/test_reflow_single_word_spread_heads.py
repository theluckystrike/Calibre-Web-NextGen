"""Physically reviewed damaged single-word heads and detached folio components.

Frozen from the rejected 9b6 source74–82 context. Expectations preserve original
OCR strings/boxes; they do not adopt folio digits or publisher furniture roles.
"""
import copy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import pytest
from cps.services.reflow import extract, skeleton

pytestmark=pytest.mark.unit
FIXTURE=Path(__file__).parents[1]/'fixtures/reflow/single_word_spread_head_context.json'
FIXTURE_SHA='3754897045e6cdd102a3a86f3fb253bedb31820a99df80148f18e90a619b4457'
TARGETS=[(78,(45.12,18.48,169.92,26.4)),
 (78,(708.2399999999999,10.08,776.88,15.120000000000001)),
 (79,(715.68,14.639999999999999,759.1199999999999,19.2)),
 (79,(775.1999999999999,14.639999999999999,784.3199999999999,19.439999999999998)),
 (80,(715.1999999999999,20.639999999999997,785.28,26.639999999999997))]

def witness():
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest()==FIXTURE_SHA
    data=json.loads(FIXTURE.read_text());raws=[]
    for item in copy.deepcopy(data['raw_pages']):
        blocks=[]
        for b in item.pop('blocks'):
            lines=[extract.Line([extract.Span(**dict(s,bbox=tuple(s['bbox']))) for s in l['spans']],tuple(l['bbox']),spacing_uncertain=l.get('spacing_uncertain',False),transcription_uncertain=l.get('transcription_uncertain',False)) for l in b['lines']]
            blocks.append(extract.Block(b['number'],tuple(b['bbox']),lines,kind=b['kind']))
        images=[extract.Image(**dict(i,bbox=tuple(i['bbox']))) for i in item.pop('images')]
        raws.append(extract.RawPage(**dict(item,blocks=blocks,images=images)))
    return raws

def target(raws,page,box):
    raw=next(r for r in raws if r.pno==page)
    return raw,next(ln for b in raw.text_blocks for ln in b.lines if ln.bbox==box)

def inspect(raws,labels=None):
    before=[asdict(r)for r in raws]
    result=skeleton._repeated_scan_spread_heads(raws,table_labels=labels)
    assert [asdict(r)for r in raws]==before,'Source evidence must remain unchanged'
    return result

@pytest.mark.parametrize('page,box',TARGETS)
def test_actual_single_word_title_or_detached_folio_is_exact_source_furniture(page,box):
    raws=witness();raw,head=target(raws,page,box)
    assert head.bbox in inspect(raws).get(page,[]),'Exact physical margin components must not enter authored source sentences'

@pytest.mark.parametrize('boundary',['missing_peers','body_slot','gutter','table','native','word_height','caption','authored_title','detached_prose'])
def test_single_word_template_does_not_discard_unproved_authored_content(boundary):
    raws=witness();raw,head=target(raws,*TARGETS[1]);labels=None
    if boundary=='missing_peers':raws=[raw]
    elif boundary in ('body_slot','gutter'):
        dx=-300 if boundary=='gutter'else 0;dy=150 if boundary=='body_slot'else 0
        head.bbox=tuple(v+(dx if i%2==0 else dy)for i,v in enumerate(head.bbox))
        for span in head.spans:span.bbox=tuple(v+(dx if i%2==0 else dy)for i,v in enumerate(span.bbox))
    elif boundary=='table':labels={78:[head.bbox]}
    elif boundary=='native':
        for page in raws:page.images=[]
    elif boundary=='word_height':
        head.bbox=(head.bbox[0],head.bbox[1],head.bbox[2],head.bbox[1]+30)
        for span in head.spans:span.size=30;span.bbox=(span.bbox[0],span.bbox[1],span.bbox[2],span.bbox[1]+30)
    elif boundary=='caption':head.spans[0].text='Figure 15: ';head.spans[-1].text='example'
    elif boundary=='detached_prose':head.spans[0].text='looking for ordinary author prose';head.spans[-1].text=''
    elif boundary=='authored_title':
        raw=next(r for r in raws if r.pno==77)
        head=next(l for b in raw.text_blocks for l in b.lines if l.stripped=='15')
    assert head.bbox not in inspect(raws,labels).get(raw.pno,[])
