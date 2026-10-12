"""Portable original-operator complete-page source-note regression gate.

The source oracle is the immutable primary203 physical review, not converter
roles. Actual rotated original PDF operators supply all pixel questions.
"""
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import gzip,hashlib,json,sys
sys.path.insert(0,str(Path.cwd()))
import pymupdf
import pytest
from cps.services.reflow import assess,extract,skeleton,transcript_regions
from cps.services.reflow.source_display import SourceDisplay
from tests.unit.test_reflow_physical_footer_canonical_delivery import raw_page,digest
from tests.unit.test_reflow_opaque_paired_furniture import style,furniture
from tests.unit.test_reflow_opaque_source_note_families import note

FIXTURE=Path(__file__).with_name('source56188_canonical_note_context.json.gz')
if not FIXTURE.exists():
 FIXTURE=Path(__file__).parents[1]/'fixtures/reflow/source56188_canonical_note_context.json.gz'

@pytest.fixture(scope='module')
def classified():
 r=json.loads(gzip.decompress(FIXTURE.read_bytes()));path=FIXTURE.parent/r['source_pdf']
 assert hashlib.sha256(path.read_bytes()).hexdigest()==r['source_pdf_sha256']
 assert r['physical_proof_sha256']=='2a2ea576fd0ffe84429ecd0695ddbde056c4fa2b204403d3175ed9f57e27becc'
 assert r['physical_review_sha256']=='b38b5cf38807e78276541db88850a908d1dc8658d72e37413079954b09dc86ee'
 assert r['original_source_pdf_sha256']=='e9be0523bb94c371b538e422754ae4a7a85bf552427aa267830c4161176dec87'
 raw=raw_page(r['raw']);before=asdict(raw);assert digest(before)==r['raw_sha256']
 rows={p['id']:raw.blocks[p['block_index']].lines[p['line_index']]for p in r['all_source_rows']}
 for p in r['all_source_rows']:assert digest(asdict(rows[p['id']]))==p['source_sha256']
 for p in r['physical_note_roles']:assert digest(asdict(rows[p['line_id']]))==p['source_row_sha256']
 context=style(r['style']);context_before=asdict(context)
 with pymupdf.open(path)as doc:
  assert list(doc[88].rect)==r['pdf_page_rect']and doc[88].rotation==r['pdf_page_rotation']==0
  assert raw.source_geometry==r['source_geometry']and raw.source_geometry['orientation']==90
  display=SourceDisplay(doc,88,dict(raw.source_geometry,layer='ocr'))
  assert list(display.rect)==r['reading_frame']
  # Same source-frame/candidate/fallback caller contract as the real page
  # pipeline; no split-only precursor that could hide stage ownership loss.
  with display.query_document(isolate=True)as reading:
   probe=extract.ScanPixelProbe(reading,88,mask=[l.bbox for l in rows.values()])
   trusted=assess.looks_like_prose(raw.text)
   candidate=transcript_regions.candidate(raw,r['provenance'],doc,context,pixel_probe=probe,layer_trusted=trusted)if raw.transcript_unverified else None
   result=candidate[0]if candidate else skeleton.page_skeleton(raw,context,pixel_probe=probe,layer_trusted=trusted)
  assert asdict(raw)==before and asdict(context)==context_before
  # Oracle render is a separate original document AFTER classification.
  with pymupdf.open(path)as independent:
   oracle=SourceDisplay(independent,88,dict(raw.source_geometry,layer='ocr'))
   pixel=r['original_pixel_evidence']
   pix=oracle.pixmap(scale=2,gray=True)
   assert hashlib.sha256(pix.samples).hexdigest()==pixel['decoded_sha256']
   yield raw,result,rows,r,oracle

def test_all_eight_physically_verified_note_rows_have_complete_note_owners(classified):
 _,result,rows,r,_=classified;wrong=[]
 for lid in r['expected_note_rows']:
  owner=[g for g in result.regions if any(rows[lid]is l for l in g.lines+g.caption_lines)]
  if len(owner)!=1 or not note(owner[0]):wrong.append((lid,[(g.kind,g.reason)for g in owner]))
 assert not wrong,wrong

def test_ordinary_body_figures_do_not_reprint_original_note_glyph_ink(classified):
 _,result,rows,r,oracle=classified;wrong=[]
 for g in result.regions:
  if g.kind!='figure'or note(g)or furniture(g):continue
  for lid in r['expected_note_rows']:
   overlap=pymupdf.Rect(g.bbox)&pymupdf.Rect(rows[lid].bbox)
   if overlap.is_empty:continue
   pix=oracle.pixmap(overlap,scale=3,gray=True)
   count=sum(v<160 for v in pix.samples)
   if count:wrong.append((lid,g.reason,count,list(overlap)))
 assert not wrong,wrong

def test_original_source_rows_conserved_once_and_raw_identity_unchanged(classified):
 raw,result,_,r,_=classified
 assert digest(asdict(raw))==r['raw_sha256']
 assert Counter(digest(asdict(l))for b in raw.text_blocks for l in b.lines)==Counter(digest(asdict(l))for g in result.regions for l in g.lines+g.caption_lines)

def test_original_upper_formula_and_body_rows_remain_authored(classified):
 _,result,rows,r,_=classified
 for lid in r['authored_formula_body_rows']:
  owner=[g for g in result.regions if any(rows[lid]is l for l in g.lines+g.caption_lines)]
  assert len(owner)==1 and not note(owner[0])and not furniture(owner[0]),(lid,[(g.kind,g.reason)for g in owner])
