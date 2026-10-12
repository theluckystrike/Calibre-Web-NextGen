"""Independently viewed original source roles survive whole-stage delivery.

All source inputs cover the complete new-note disposition scope; role assertions
derive from original source views, never from the candidate converter's roles.
"""
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import gzip,hashlib,json
import pymupdf
import pytest
from cps.services.reflow import assess,extract,skeleton,transcript_regions
from cps.services.reflow.source_display import SourceDisplay
from tests.unit.test_reflow_physical_footer_canonical_delivery import raw_page,digest
from tests.unit.test_reflow_opaque_paired_furniture import style,furniture
from tests.unit.test_reflow_opaque_source_note_families import note
from tests.unit.reflow_contents_folio_source_context import supplement

pytestmark=pytest.mark.unit
FIXTURE=Path(__file__).parents[1]/'fixtures/reflow/new_note_disposition_original_context.json.gz'
# ROOT replaces this sentinel with the independently frozen physical ledger
# digest before installing this staged test and the final protected fixture.
PHYSICAL_PROOF_SHA256='7076ca8c6e9fb999c36d02113d7c18c02ecb502d95136f903b5514ff75d53212'
DATA=json.loads(gzip.decompress(FIXTURE.read_bytes()))if FIXTURE.exists()else None
KEYS=sorted(DATA['cases'])if DATA else []

@pytest.fixture(scope='module')
def classified():
 assert DATA is not None and DATA['independent_physical_roles_pending']is False
 assert DATA['physical_proof_sha256']==PHYSICAL_PROOF_SHA256
 assert len(KEYS)==65 and sum(len(r['new_target_rows'])for r in DATA['cases'].values())==413
 results={}
 for key in KEYS:
  bid,pno=map(int,key.split(':'));r=DATA['cases'][key];pdf=DATA['source_pdfs'][str(bid)];path=FIXTURE.parent/pdf['path']
  assert hashlib.sha256(path.read_bytes()).hexdigest()==pdf['sha256']
  raw=raw_page(r['raw']);before=asdict(raw);assert digest(before)==r['raw_sha256']
  rows={x['id']:raw.blocks[x['block_index']].lines[x['line_index']]for x in r['all_source_rows']}
  assert all(digest(asdict(rows[x['id']]))==x['source_sha256']for x in r['all_source_rows'])
  for target in r['physical_role_rows']:
   assert digest(asdict(rows[target['id']]))==target['source_sha256']
  context=supplement(style(r['style']),raw,pdf['original_sha256']);context_before=asdict(context)
  with pymupdf.open(path)as doc:
   assert list(doc[pno].rect)==r['frame']and doc[pno].rotation==r['rotation']
   display=SourceDisplay(doc,pno,dict(raw.source_geometry,layer='ocr'if raw.is_page_scan else'native'))
   with display.query_document(isolate=True)as reading:
    probe=extract.ScanPixelProbe(reading,pno,mask=[l.bbox for l in rows.values()])
    trusted=assess.looks_like_prose(raw.text)
    candidate=transcript_regions.candidate(raw,r['provenance'],doc,context,pixel_probe=probe,layer_trusted=trusted)if raw.transcript_unverified else None
    result=candidate[0]if candidate else skeleton.page_skeleton(raw,context,pixel_probe=probe,layer_trusted=trusted)
  assert asdict(raw)==before and asdict(context)==context_before
  with pymupdf.open(path)as oracle:
   pix=oracle[pno].get_pixmap(matrix=pymupdf.Matrix(2,2),colorspace=pymupdf.csGRAY,alpha=False)
   assert hashlib.sha256(pix.samples).hexdigest()==r['fullframe_sha256']
  results[key]=(raw,result,rows,r,path)
 return results

@pytest.mark.parametrize('key',KEYS)
def test_independent_original_authorship_and_note_roles(classified,key):
 _,result,rows,r,_=classified[key]
 for target in r['physical_role_rows']:
  lid=target['id'];role=target['role']
  owners=[g for g in result.regions if any(rows[lid]is l for l in g.lines+g.caption_lines)]
  assert len(owners)==1,(key,lid,'source must have one exact owner')
  owner=owners[0]
  if role=='printed_note_body':assert note(owner),(key,lid,role,owner.kind,owner.reason)
  elif role=='printed_furniture':assert furniture(owner),(key,lid,role,owner.kind,owner.reason)
  else:
   assert role.startswith('authored_'),(key,lid,'unknown physical role',role)
   assert not note(owner)and not furniture(owner),(key,lid,role,owner.kind,owner.reason)

@pytest.mark.parametrize('key',KEYS)
def test_original_note_ink_does_not_reappear_in_body_figures(classified,key):
 raw,result,rows,r,path=classified[key]
 with pymupdf.open(path)as oracle:
  display=SourceDisplay(oracle,raw.pno,dict(raw.source_geometry,layer='ocr'if raw.is_page_scan else'native'))
  for target in r['physical_role_rows']:
   if target['role']!='printed_note_body':continue
   lid=target['id']
   for g in result.regions:
    if g.kind not in('figure','artwork')or note(g)or furniture(g):continue
    overlap=pymupdf.Rect(g.bbox)&pymupdf.Rect(rows[lid].bbox)
    if overlap.is_empty:continue
    pix=display.pixmap(overlap,scale=3,gray=True)
    assert not any(v<160 for v in pix.samples),(key,lid,g.kind,g.reason,list(overlap))

@pytest.mark.parametrize('key',KEYS)
def test_all_original_rows_conserved_once(classified,key):
 raw,result,_,_,_=classified[key]
 assert Counter(digest(asdict(l))for b in raw.text_blocks for l in b.lines)==Counter(digest(asdict(l))for g in result.regions for l in g.lines+g.caption_lines)
