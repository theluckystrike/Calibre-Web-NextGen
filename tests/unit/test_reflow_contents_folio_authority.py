"""Original Roman footer teachers cannot turn isolated authored words into furniture."""
from dataclasses import asdict
from pathlib import Path
import copy,gzip,hashlib,json
import pymupdf
import pytest
from cps.services.reflow import skeleton
from tests.unit.reflow_contents_folio_source_context import data,peers,supplement,FIXTURE
from tests.unit.test_reflow_opaque_paired_furniture import style
pytestmark=pytest.mark.unit
CASES=[(569,9),(569,16),(570,8),(570,11)]
CONTEXT=Path(__file__).parents[1]/'fixtures/reflow/new_note_disposition_original_context.json.gz'
def inputs(book,page):
 originals=peers(book);raw=next(r for r in originals if r.pno==page)
 record=json.loads(gzip.decompress(CONTEXT.read_bytes()))['cases'][f'{book}:{page}']
 context=style(record['style'])
 return originals,raw,context

def footer(raw):
 return max((line for block in raw.text_blocks for line in block.lines if line.stripped),key=lambda l:l.bbox[1])

@pytest.mark.parametrize('book,page',CASES)
def test_actual_uncertain_original_folios_have_other_original_source_teachers(book,page):
 originals,raw,context=inputs(book,page);before=[asdict(r)for r in originals]
 context=supplement(context,raw,data()['books'][str(book)]['original_source_sha256'])
 assert skeleton._contents_footer_folio(footer(raw),raw,context)
 assert [asdict(r)for r in originals]==before

@pytest.mark.parametrize('book,page',CASES)
def test_same_page_contents_and_footer_shape_without_peer_authority_abstain(book,page):
 _,raw,context=inputs(book,page)
 assert not skeleton._contents_footer_folio(footer(raw),raw,context)

@pytest.mark.parametrize('book,page',CASES)
def test_uncertain_authored_end_cannot_borrow_neighboring_folio_progression(book,page):
 originals,raw,context=inputs(book,page)
 target=footer(raw);target.spans[0].text='END';target.transcription_uncertain=True
 for span in target.spans:span.transcription_uncertain=True
 method=getattr(skeleton,'_repeated_contents_folios',None);assert callable(method)
 context.contents_folio_boxes=method(originals,context.body_size)
 assert not skeleton._contents_footer_folio(target,raw,context)

@pytest.mark.parametrize('book,page',CASES)
def test_uncertain_peer_literals_do_not_teach_the_uncertain_target(book,page):
 originals,raw,context=inputs(book,page)
 for peer in originals:
  row=footer(peer)if peer.text_blocks else None
  if row:
   row.transcription_uncertain=True
   for span in row.spans:span.transcription_uncertain=True
 method=getattr(skeleton,'_repeated_contents_folios',None);assert callable(method)
 context.contents_folio_boxes=method(originals,context.body_size)
 assert not skeleton._contents_footer_folio(footer(raw),raw,context)

@pytest.mark.parametrize('book,page',CASES)
def test_clear_nonprogressing_roman_peers_do_not_teach_an_uncertain_target(book,page):
 originals,raw,context=inputs(book,page)
 for peer in originals:
  if peer is raw or not peer.text_blocks:continue
  row=footer(peer);row.spans[0].text='ix';row.transcription_uncertain=False
  for span in row.spans:span.uncertain=span.transcription_uncertain=span.encoding_unresolved=False
 method=getattr(skeleton,'_repeated_contents_folios',None);assert callable(method)
 context.contents_folio_boxes=method(originals,context.body_size)
 assert not skeleton._contents_footer_folio(footer(raw),raw,context)

def test_all_original_peer_operator_pixels_remain_exact():
 for book in data()['books'].values():
  source=book['source_pdf'];path=FIXTURE.parent/source['path']
  assert hashlib.sha256(path.read_bytes()).hexdigest()==source['sha256']
  with pymupdf.open(path)as doc:
   for page,proof in book['source_pixels'].items():
    p=doc[int(page)];assert list(p.rect)==proof['frame']and p.rotation==proof['rotation']
    pixels=p.get_pixmap(matrix=pymupdf.Matrix(2,2),colorspace=pymupdf.csGRAY,alpha=False)
    assert hashlib.sha256(pixels.samples).hexdigest()==proof['fullframe_sha256']
