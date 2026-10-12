"""Repeated arbitrary numeric data do not establish original folio authority."""
from dataclasses import asdict
import copy,json
import pytest
from cps.services.reflow import extract,skeleton
from tests.unit.test_reflow_opaque_paired_furniture import FIXTURE,peer_style,furniture
from tests.unit.test_reflow_physical_footer_canonical_delivery import raw_page

pytestmark=pytest.mark.unit


def template_page(page,number):
    titlebox=(100,30,180,42);digitbox=(430,30,448,42);bodybox=(40,150,470,165)
    rows=[extract.Line([extract.Span('YEAR VALUES',9,'Times-Roman',0,titlebox,origin_y=40)],titlebox),
          extract.Line([extract.Span(number,9,'Times-Roman',0,digitbox,origin_y=40,transcription_uncertain=True)],digitbox),
          extract.Line([extract.Span('The authored table values and chart data remain source content.',12,'Times-Roman',0,bodybox,origin_y=162)],bodybox)]
    return extract.RawPage(page,504,720,[extract.Block(i,row.bbox,[row])for i,row in enumerate(rows)],
                           images=[extract.Image((0,0,504,720),1.0)])


@pytest.mark.parametrize('numbers',[['123']*5,['123','872','46','931','205']])
def test_repetition_alone_cannot_teach_uncertain_numeric_table_data_as_furniture(numbers):
    pages=[template_page(i,text)for i,text in enumerate(numbers)];before=[asdict(p)for p in pages]
    context=skeleton.book_style(pages)
    for raw in pages:
        row=raw.blocks[1].lines[0]
        owners=[r for r in skeleton.opaque_page_regions(raw,context)if any(row is ln for ln in r.lines)]
        assert len(owners)==1 and not furniture(owners[0]),[(r.kind,r.reason)for r in owners]
    assert [asdict(p)for p in pages]==before


@pytest.mark.parametrize('geometry',[
    {'space':'reading','orientation':90,'source_rotation':0,'page_rect':[0,0,504,720]},
    {'space':'native','orientation':0,'source_rotation':90,'page_rect':[0,0,504,720]},
    {'space':'native','orientation':0,'source_rotation':0,'page_rect':[0,0,400,600]},
    {'space':'unproved','orientation':0,'source_rotation':0,'page_rect':[0,0,504,720]},
])
def test_learned_real_pair_authority_does_not_clear_incompatible_frame(geometry):
    data=json.loads(FIXTURE.read_text());record=data['cases']['593'];raw=raw_page(record['raw'])
    context=peer_style(data['book_style'],raw)
    assert raw.pno in context.paired_margin_head_boxes,'Actual original peers must establish the positive authority first'
    proof=next(p for p in record['physical_source_rows']if p['line_id']=='l1')
    row=raw.blocks[proof['block_index']].lines[proof['line_index']]
    raw.source_geometry=copy.deepcopy(geometry);before=asdict(raw)
    owners=[r for r in skeleton.opaque_page_regions(raw,context)if any(row is ln for ln in r.lines)]
    assert len(owners)==1 and not furniture(owners[0]),[(r.kind,r.reason)for r in owners]
    assert asdict(raw)==before
