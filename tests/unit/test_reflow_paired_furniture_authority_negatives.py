"""Unregistered source data and incompatible frames cannot certify folio furniture."""
from dataclasses import asdict
import copy,json

import pytest
from cps.services.reflow import extract,skeleton
from tests.unit.test_reflow_physical_footer_canonical_delivery import raw_page
from tests.unit.test_reflow_opaque_paired_furniture import FIXTURE,style,furniture

pytestmark=pytest.mark.unit


@pytest.mark.parametrize('label',['YEAR VALUES','CHART VALUES'])
def test_unregistered_smallcaps_and_edge_numeric_data_have_no_furniture_authority(label):
    titlebox=(100,30,180,42);digitbox=(430,30,448,42);bodybox=(40,150,470,165)
    title=extract.Line([extract.Span(label,9,'Times-Roman',0,titlebox)],titlebox)
    digit=extract.Line([extract.Span('123',9,'Times-Roman',0,digitbox,transcription_uncertain=True)],digitbox)
    body=extract.Line([extract.Span('The authored table values and chart data remain source content.',12,'Times-Roman',0,bodybox)],bodybox)
    raw=extract.RawPage(0,504,720,[extract.Block(i,line.bbox,[line])for i,line in enumerate([title,digit,body])])
    raw.images=[extract.Image((0,0,504,720),1.0)]
    assert raw.is_page_scan
    before=asdict(raw);context=skeleton.BookStyle(body_size=12)
    regions=skeleton.opaque_page_regions(raw,context)
    owners=[r for r in regions if any(digit is line for line in r.lines)]
    assert len(owners)==1 and not furniture(owners[0]),[(r.kind,r.reason)for r in owners]
    assert asdict(raw)==before


@pytest.mark.parametrize('geometry',[
    {'space':'reading','orientation':90,'source_rotation':0,'page_rect':[0,0,504,720]},
    {'space':'native','orientation':0,'source_rotation':90,'page_rect':[0,0,504,720]},
    {'space':'native','orientation':0,'source_rotation':0,'page_rect':[0,0,400,600]},
    {'space':'unproved','orientation':0,'source_rotation':0,'page_rect':[0,0,504,720]},
])
def test_original_native_pair_cannot_clear_incompatible_source_frame(geometry):
    data=json.loads(FIXTURE.read_text());record=data['cases']['593'];raw=raw_page(record['raw'])
    raw.source_geometry=copy.deepcopy(geometry);before=asdict(raw);context=style(data['book_style'])
    proof=next(p for p in record['physical_source_rows']if p['line_id']=='l1')
    digit=raw.blocks[proof['block_index']].lines[proof['line_index']]
    regions=skeleton.opaque_page_regions(raw,context)
    owners=[r for r in regions if any(digit is line for line in r.lines)]
    assert len(owners)==1 and not furniture(owners[0]),[(r.kind,r.reason)for r in owners]
    assert asdict(raw)==before
