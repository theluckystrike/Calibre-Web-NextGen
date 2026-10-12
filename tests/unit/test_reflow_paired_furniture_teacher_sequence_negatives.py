"""Clear repeated table numbers cannot train an uncertain target folio."""
from dataclasses import asdict
import pytest
from cps.services.reflow import skeleton
from tests.unit.test_reflow_paired_furniture_learned_authority import template_page
from tests.unit.test_reflow_opaque_paired_furniture import furniture

pytestmark=pytest.mark.unit

@pytest.mark.parametrize('numbers',[['123']*5,['123','872','46','931','205']])
def test_four_clear_nonprogressing_table_values_do_not_authorize_uncertain_target(numbers):
    pages=[template_page(i,value)for i,value in enumerate(numbers)]
    for raw in pages[:4]:raw.blocks[1].lines[0].spans[0].transcription_uncertain=False
    assert all(not raw.blocks[1].lines[0].spans[0].transcription_uncertain for raw in pages[:4])
    assert pages[4].blocks[1].lines[0].spans[0].transcription_uncertain
    before=[asdict(raw)for raw in pages];context=skeleton.book_style(pages)
    raw=pages[4];row=raw.blocks[1].lines[0]
    owners=[r for r in skeleton.opaque_page_regions(raw,context)if any(row is ln for ln in r.lines)]
    assert len(owners)==1 and not furniture(owners[0]),[(r.kind,r.reason)for r in owners]
    assert [asdict(raw)for raw in pages]==before
