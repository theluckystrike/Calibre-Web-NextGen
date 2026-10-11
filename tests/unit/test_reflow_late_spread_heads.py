"""Exact late-book running heads remain furniture across chapter-opening gaps."""
from dataclasses import asdict
import json
from pathlib import Path
import pytest
from cps.services.reflow import extract,skeleton
pytestmark=pytest.mark.unit


def witness():
    data=json.loads((Path(__file__).parents[1]/'fixtures/reflow/late_spread_head_context.json').read_text());raws=[]
    for d in data['raw_pages']:
        blocks=[]
        for b in d.pop('blocks'):
            lines=[extract.Line([extract.Span(**dict(s,bbox=tuple(s['bbox'])))for s in l['spans']],tuple(l['bbox']),spacing_uncertain=l.get('spacing_uncertain',False),transcription_uncertain=l.get('transcription_uncertain',False))for l in b['lines']]
            blocks.append(extract.Block(b['number'],tuple(b['bbox']),lines,kind=b['kind']))
        images=[extract.Image(**dict(i,bbox=tuple(i['bbox'])))for i in d.pop('images')]
        raws.append(extract.RawPage(**dict(d,blocks=blocks,images=images)))
    return raws


def target(raws,page,side):
    raw=next(r for r in raws if r.pno==page)
    candidates=[l for b in raw.text_blocks for l in b.lines if l.bbox[1]<60 and (l.bbox[0]>450)==bool(side)]
    assert len(candidates)==1
    return raw,candidates[0]


def inspect(raws,table_labels=None):
    before=[asdict(r)for r in raws]
    proved=skeleton._repeated_scan_spread_heads(raws,table_labels=table_labels)
    assert [asdict(r)for r in raws]==before
    return proved


@pytest.mark.parametrize('page,side',[(48,1),(49,0),(49,1)])
def test_actual_running_head_stays_out_of_three_unfinished_source_sentences(page,side):
    raws=witness();raw,head=target(raws,page,side)
    assert head.bbox in inspect(raws).get(page,[]),'A genuine source running head must not interrupt during that/period, but here I/will, or profection/returns'


def test_original_chapter13_heading_remains_authored_body_content():
    raws=witness();raw=next(r for r in raws if r.pno==48)
    heading=next(l for b in raw.text_blocks for l in b.lines if l.bbox[0]<450 and l.stripped.startswith('CHAPTER 13:'))
    assert heading.bbox not in inspect(raws).get(48,[])


@pytest.mark.parametrize('boundary',['no_peers','reliable_wrong_folio','wrong_margin','large_heading','table','no_scan'])
def test_recurrent_margin_template_does_not_discard_unproved_headlike_content(boundary):
    raws=witness();raw,head=target(raws,49,1);labels=None
    if boundary=='no_peers':raws=[raw]
    elif boundary=='reliable_wrong_folio':head.spans[-1].text='999';head.spans[-1].uncertain=False
    elif boundary in ('wrong_margin','large_heading'):
        if boundary=='wrong_margin':
            head.bbox=tuple(v+100 if i in (1,3)else v for i,v in enumerate(head.bbox))
            for s in head.spans:s.bbox=tuple(v+100 if i in (1,3)else v for i,v in enumerate(s.bbox))
        else:
            head.bbox=(head.bbox[0],head.bbox[1],head.bbox[2],head.bbox[1]+24)
            for s in head.spans:s.size=24;s.bbox=(s.bbox[0],s.bbox[1],s.bbox[2],s.bbox[1]+24)
    elif boundary=='table':labels={49:[head.bbox]}
    elif boundary=='no_scan':
        for r in raws:r.images=[]
    assert head.bbox not in inspect(raws,labels).get(49,[])
