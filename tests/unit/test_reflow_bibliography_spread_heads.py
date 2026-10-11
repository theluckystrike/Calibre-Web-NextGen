"""Running heads above bibliography/list text remain distinct from authored headings."""
from dataclasses import asdict
import json
from pathlib import Path
import pytest
from cps.services.reflow import extract,skeleton
pytestmark=pytest.mark.unit


def witness():
    data=json.loads((Path(__file__).parents[1]/'fixtures/reflow/bibliography_spread_head_context.json').read_text());raws=[]
    for d in data['raw_pages']:
        blocks=[]
        for b in d.pop('blocks'):
            lines=[extract.Line([extract.Span(**dict(s,bbox=tuple(s['bbox'])))for s in l['spans']],tuple(l['bbox']),spacing_uncertain=l.get('spacing_uncertain',False),transcription_uncertain=l.get('transcription_uncertain',False))for l in b['lines']]
            blocks.append(extract.Block(b['number'],tuple(b['bbox']),lines,kind=b['kind']))
        images=[extract.Image(**dict(i,bbox=tuple(i['bbox'])))for i in d.pop('images')]
        raws.append(extract.RawPage(**dict(d,blocks=blocks,images=images)))
    return raws


def head(raw,side):
    rows=[l for b in raw.text_blocks for l in b.lines if l.bbox[1]<60 and (l.bbox[0]>450)==bool(side)]
    assert len(rows)==1
    return rows[0]


def inspect(raws,labels=None):
    before=[asdict(r)for r in raws];result=skeleton._repeated_scan_spread_heads(raws,table_labels=labels)
    assert [asdict(r)for r in raws]==before
    return result


@pytest.mark.parametrize('side',[0,1])
def test_actual_bibliography_margin_head_is_furniture(side):
    raws=witness();raw=next(r for r in raws if r.pno==60)
    assert head(raw,side).bbox in inspect(raws).get(60,[])


def test_elections_is_authored_body_heading_below_the_running_head():
    raws=witness();raw=next(r for r in raws if r.pno==60)
    elections=next(l for b in raw.text_blocks for l in b.lines if l.stripped=='Elections')
    assert elections.bbox not in inspect(raws).get(60,[])


@pytest.mark.parametrize('side',[0,1])
@pytest.mark.parametrize('boundary',['too_few_other_pages','reliable_wrong_folio','wrong_margin','large_heading','table','no_scan','no_stable_peer_folios'])
def test_typographic_tolerance_cannot_establish_unproved_body_or_table_territory(side,boundary):
    raws=witness();raw=next(r for r in raws if r.pno==60);line=head(raw,side);labels=None
    if boundary=='too_few_other_pages':raws=[r for r in raws if r.pno in (59,60,61)]
    elif boundary=='reliable_wrong_folio':
        span=line.spans[0 if side==0 else -1];span.text='999';span.uncertain=False;span.transcription_uncertain=False;span.encoding_unresolved=False
    elif boundary=='wrong_margin':
        line.bbox=tuple(v+100 if i in (1,3)else v for i,v in enumerate(line.bbox))
        for span in line.spans:span.bbox=tuple(v+100 if i in (1,3)else v for i,v in enumerate(span.bbox))
    elif boundary=='large_heading':
        line.bbox=(line.bbox[0],line.bbox[1],line.bbox[2],line.bbox[1]+24)
        for span in line.spans:span.size=24;span.bbox=(span.bbox[0],span.bbox[1],span.bbox[2],span.bbox[1]+24)
    elif boundary=='table':labels={60:[line.bbox]}
    elif boundary=='no_scan':
        for r in raws:r.images=[]
    elif boundary=='no_stable_peer_folios':
        for r in raws:
            if r.pno==60:continue
            for panel in (0,1):
                rows=[l for b in r.text_blocks for l in b.lines if l.bbox[1]<60 and (l.bbox[0]>450)==bool(panel)]
                if not rows:continue
                span=rows[0].spans[0 if panel==0 else -1];span.text='999';span.uncertain=False;span.transcription_uncertain=False;span.encoding_unresolved=False
    assert line.bbox not in inspect(raws,labels).get(60,[])
