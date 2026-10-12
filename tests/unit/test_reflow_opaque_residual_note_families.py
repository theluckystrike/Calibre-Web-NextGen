"""Eight original footer contexts supplement the unchanged source-family gates.

Independent physical review proves 23 note rows,229 authored neighboring rows,
and9 detached margin-furniture rows. All source words and original ink survive;
body/chart/caption prose may never be disposed of as footer furniture.
"""
from dataclasses import asdict
from pathlib import Path
import copy,gzip,hashlib,json
import pymupdf
import pytest
from cps.services.reflow import extract,skeleton,transcript_regions
from tests.unit import test_reflow_opaque_source_note_families as policy
from tests.unit.test_reflow_physical_footer_canonical_delivery import raw_page,digest
from tests.unit.test_reflow_opaque_paired_furniture import style

pytestmark=pytest.mark.unit
FIXTURE=Path(__file__).parents[1]/'fixtures/reflow/opaque_residual_note_family_original_context.json.gz'
KEYS=['567:169','567:315','567:453','569:158','569:491','570:40','570:70','570:469']

@pytest.fixture(scope='module')
def cases():
 data=json.loads(gzip.decompress(FIXTURE.read_bytes()));measured={}
 try:
  for key in KEYS:
   bid,page=map(int,key.split(':'));r=data['cases'][key];source=data['source_pdfs'][str(bid)]
   path=FIXTURE.parent/source['path'];assert hashlib.sha256(path.read_bytes()).hexdigest()==source['sha256']
   doc=pymupdf.open(path);raw=raw_page(r['raw']);before=asdict(raw);measured[key]=(raw,None,None,doc,r,{})
   assert digest(before)==r['raw_sha256'];assert list(doc[page].rect)==r['frame'] and doc[page].rotation==r['rotation']==0
   pix=doc[page].get_pixmap(matrix=pymupdf.Matrix(2,2),colorspace=pymupdf.csGRAY,alpha=False)
   assert hashlib.sha256(pix.samples).hexdigest()==r['fullframe_sha256']
   rows={}
   for proof in r['all_source_rows']:
    row=raw.blocks[proof['block_index']].lines[proof['line_index']]
    assert digest(asdict(row))==proof['source_sha256'];rows[proof['id']]=row
   context=style(r['style']);probe=extract.ScanPixelProbe(doc,page,mask=[row.bbox for row in rows.values()]);provenance=copy.deepcopy(r['provenance'])
   if 'source_pdf_sha256'in provenance.get('verification',{}):
    assert provenance['verification']['source_pdf_sha256']==source['original_sha256'];provenance['verification']['source_pdf_sha256']=source['sha256']
   candidate=transcript_regions.candidate(raw,provenance,doc,context,pixel_probe=probe,layer_trusted=True)if raw.transcript_unverified else None
   canonical=candidate[0]if candidate else skeleton.page_skeleton(raw,context,pixel_probe=probe,layer_trusted=not raw.transcript_unverified)
   opaque=skeleton.opaque_page_regions(raw,context,pixel_probe=probe);assert asdict(raw)==before
   measured[key]=(raw,canonical.regions,opaque,doc,r,rows)
  yield measured
 finally:
  for _,_,_,doc,_,_ in measured.values():doc.close()

@pytest.mark.parametrize('key',KEYS)
def test_all_physical_note_rows_owned_in_canonical_and_opaque_lanes(cases,key):
 policy.test_physical_source_note_rows_have_complete_canonical_and_opaque_note_owners(cases,key)

@pytest.mark.parametrize('key',KEYS)
def test_note_source_pixels_excluded_from_ordinary_body_strips(cases,key):
 policy.test_original_printed_note_ink_is_outside_main_opaque_source_strips(cases,key)

@pytest.mark.parametrize('key',KEYS)
def test_source_once_and_authored_caption_table_verse_body_retained(cases,key):
 policy.test_all_source_rows_once_and_physically_authored_neighbors_outside_notes_furniture(cases,key)

@pytest.mark.parametrize('key',KEYS)
def test_no_original_ink_missing_from_complete_source_strips(cases,key):
 policy.test_all_original_opaque_page_ink_remains_covered_without_resizing(cases,key)

# Source geometry and actual ink establish these authored scopes. A new note
# strip cannot swallow a wheel/ornament even if total source ink still survives.
SCOPES=[('567:169',0),('567:315',0),('567:453',0),('567:453',1),('567:453',2),('569:491',0),('570:40',0)]

@pytest.mark.parametrize('key,index',SCOPES)
def test_authored_original_wheel_and_ornament_ink_never_owned_by_note_or_furniture(cases,key,index):
 from PIL import Image,ImageDraw
 import math
 from tests.unit.test_reflow_opaque_paired_furniture import furniture
 raw,canonical,opaque,doc,record,_=cases[key]
 scope=record['independent_original_pixel_preservation_scopes'][index]
 pix=doc[raw.pno].get_pixmap(matrix=pymupdf.Matrix(2,2),colorspace=pymupdf.csGRAY,alpha=False)
 original=Image.frombytes('L',(pix.width,pix.height),pix.samples)
 b=scope['bbox'];roi=(math.floor(2*b[0]),math.floor(2*b[1]),math.ceil(2*b[2]),math.ceil(2*b[3]))
 source_ink=original.crop(roi);assert sum(v<160 for v in source_ink.tobytes())>100,(key,scope['role'])
 for regions in [canonical,opaque]:
  forbidden=Image.new('L',original.size,0);draw=ImageDraw.Draw(forbidden)
  for region in regions:
   if policy.note(region)or furniture(region):
    box=region.bbox
    draw.rectangle((math.floor(2*box[0]),math.floor(2*box[1]),math.ceil(2*box[2])-1,math.ceil(2*box[3])-1),fill=255)
  wrongly_owned=sum(v<160 and covered for v,covered in zip(source_ink.tobytes(),forbidden.crop(roi).tobytes()))
  assert wrongly_owned==0,(key,scope['role'],wrongly_owned)
