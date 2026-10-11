"""Peer-derived scan heads must not consume authored chart labels or body ink."""
import pytest
from tests.unit.test_reflow_single_word_spread_heads import witness,target,inspect,TARGETS
pytestmark=pytest.mark.unit

@pytest.mark.parametrize('boundary',['target_only','native_target','table_edge','body_edge','reliable_chart_word','interior_edge'])
def test_chart_only_folio_requires_source_peers_and_its_own_margin_proof(boundary):
    raws=witness();raw,edge=target(raws,*TARGETS[3]);labels=None
    if boundary=='target_only':raws=[raw]
    elif boundary=='native_target':raw.images=[]
    elif boundary=='table_edge':labels={79:[edge.bbox]}
    elif boundary in ('body_edge','interior_edge'):
        dx=-100 if boundary=='interior_edge'else 0;dy=120 if boundary=='body_edge'else 0
        edge.bbox=tuple(v+(dx if i%2==0 else dy)for i,v in enumerate(edge.bbox))
        for span in edge.spans:span.bbox=tuple(v+(dx if i%2==0 else dy)for i,v in enumerate(span.bbox))
    elif boundary=='reliable_chart_word':
        for span in edge.spans:
            span.text='Mercury';span.uncertain=False;span.transcription_uncertain=False;span.encoding_unresolved=False
    assert edge.bbox not in inspect(raws,labels).get(79,[]),boundary
