"""Cold original peer context; source/role oracles remain immutable."""
from pathlib import Path
from dataclasses import asdict
from functools import lru_cache
import copy,gzip,hashlib,json
from cps.services.reflow import skeleton
from tests.unit.test_reflow_physical_footer_canonical_delivery import raw_page,digest
FIXTURE=Path(__file__).parents[1]/'fixtures/reflow/roman_footer_original_peer_context.json.gz'
@lru_cache()
def data():
 assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest()=='ac0d0ae13f8756aa3cd89c2fb30d57681f5bf77e70b5e4edd3fbb3c5c4858024'
 values=json.loads(gzip.decompress(FIXTURE.read_bytes()))
 assert all({p:digest(r)for p,r in b['raw_pages'].items()}==b['raw_sha256']for b in values['books'].values())
 return values

def peers(book):
 return [raw_page(r)for r in data()['books'][str(book)]['raw_pages'].values()]

def supplement(context,raw,original_sha256):
 if not hasattr(skeleton,'_repeated_contents_folios'):return context
 books=[b for b in data()['books'].values()if b['original_source_sha256']==original_sha256]
 if not books:return context
 assert len(books)==1
 book=books[0]
 if str(raw.pno)not in book['raw_pages']:return context
 assert digest(asdict(raw))==book['raw_sha256'][str(raw.pno)]
 originals=[raw_page(r)for r in book['raw_pages'].values()];before=[asdict(r)for r in originals]
 context.contents_folio_boxes=copy.deepcopy(skeleton._repeated_contents_folios(originals,context.body_size))
 assert [asdict(r)for r in originals]==before
 return context
