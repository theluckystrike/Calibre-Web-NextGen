"""Seven further physical note rows survive cold source qualification.

A full-page preview can change MuPDF's subsequent subclip font rendering. The
source qualifier must work before previews, candidate extraction or pixel-oracle
rendering. Separate original-operator documents supply the independent oracle.
"""
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import gzip,hashlib,json
import pymupdf
import pytest
from cps.services.reflow import extract,skeleton
from tests.unit.test_reflow_physical_footer_canonical_delivery import raw_page,digest
from tests.unit.test_reflow_opaque_paired_furniture import style,furniture
from tests.unit.test_reflow_opaque_source_note_families import note

pytestmark=pytest.mark.unit
FIXTURE=Path(__file__).parents[1]/'fixtures/reflow/opaque_cold_residual_notes_original_context.json.gz'
KEYS=['567:91','570:501']

@pytest.fixture(scope='module')
def cold_cases():
 data=json.loads(gzip.decompress(FIXTURE.read_bytes()));results={};docs=[]
 try:
  for key in KEYS:
   bid,pno=map(int,key.split(':'));r=data['cases'][key];s=data['source_pdfs'][str(bid)];path=FIXTURE.parent/s['path']
   assert hashlib.sha256(path.read_bytes()).hexdigest()==s['sha256']
   raw=raw_page(r['raw']);before=asdict(raw);assert digest(before)==r['raw_sha256']
   rows={x['id']:raw.blocks[x['block_index']].lines[x['line_index']]for x in r['all_source_rows']}
   for x in r['all_source_rows']:assert digest(asdict(rows[x['id']]))==x['source_sha256']
   # This handle has not rendered any pixels. No canonical-first warm-up.
   cold=pymupdf.open(path);docs.append(cold)
   assert list(cold[pno].rect)==r['frame'] and cold[pno].rotation==r['rotation']==0
   context=style(r['style']);context_before=asdict(context)
   probe=extract.ScanPixelProbe(cold,pno,mask=[line.bbox for line in rows.values()])
   opaque=skeleton.opaque_page_regions(raw,context,pixel_probe=probe)
   assert asdict(raw)==before and asdict(context)==context_before
   # Pixel evidence is decoded in an independent handle AFTER qualification.
   oracle=pymupdf.open(path);docs.append(oracle)
   pix=oracle[pno].get_pixmap(matrix=pymupdf.Matrix(2,2),colorspace=pymupdf.csGRAY,alpha=False)
   assert hashlib.sha256(pix.samples).hexdigest()==r['fullframe_sha256']
   results[key]=(raw,opaque,oracle,r,rows)
  yield results
 finally:
  for doc in docs:doc.close()

@pytest.mark.parametrize('key',KEYS)
def test_seven_original_cold_rows_all_physically_printed_rows_have_note_owner(cold_cases,key):
 _,regions,_,record,rows=cold_cases[key]
 for lid in record['expected_note_rows']:
  owners=[r for r in regions if any(rows[lid]is ln for ln in r.lines+r.caption_lines)]
  assert len(owners)==1 and note(owners[0]),(key,lid,[(r.kind,r.reason)for r in owners])

@pytest.mark.parametrize('key',KEYS)
def test_seven_original_cold_rows_note_pixels_not_in_main_body_crop(cold_cases,key):
 raw,regions,oracle,record,rows=cold_cases[key]
 for lid in record['expected_note_rows']:
  for region in regions:
   if note(region)or furniture(region)or region.kind not in ('figure','artwork'):continue
   intersection=pymupdf.Rect(region.bbox)&pymupdf.Rect(rows[lid].bbox)
   if intersection.is_empty:continue
   pix=oracle[raw.pno].get_pixmap(clip=intersection,matrix=pymupdf.Matrix(2,2),colorspace=pymupdf.csGRAY,alpha=False)
   assert not any(v<160 for v in pix.samples),(key,lid,region.bbox)

@pytest.mark.parametrize('key',KEYS)
def test_seven_original_cold_rows_original_rows_once_and_adjacent_authored_body_retained(cold_cases,key):
 raw,regions,_,record,rows=cold_cases[key]
 assert Counter(digest(asdict(l))for b in raw.text_blocks for l in b.lines)==Counter(digest(asdict(l))for r in regions for l in r.lines+r.caption_lines)
 for proof in record['adjacent_preservation_rows']:
  line=rows[proof['id']];assert digest(asdict(line))==digest(proof['source'])
  owners=[r for r in regions if any(line is l for l in r.lines+r.caption_lines)]
  assert len(owners)==1 and not note(owners[0])and not furniture(owners[0]),(key,proof['id'])

@pytest.mark.parametrize('key',KEYS)
def test_seven_original_cold_rows_every_original_dark_pixel_retained(cold_cases,key):
 import math
 from PIL import Image,ImageDraw
 raw,regions,oracle,_,_=cold_cases[key]
 pix=oracle[raw.pno].get_pixmap(matrix=pymupdf.Matrix(2,2),colorspace=pymupdf.csGRAY,alpha=False)
 support=Image.new('L',(pix.width,pix.height),0);draw=ImageDraw.Draw(support)
 for r in regions:
  if r.kind in ('figure','artwork'):
   b=r.bbox;draw.rectangle((math.floor(2*b[0]),math.floor(2*b[1]),math.ceil(2*b[2])-1,math.ceil(2*b[3])-1),fill=255)
 assert sum(v<160 and not covered for v,covered in zip(pix.samples,support.tobytes()))==0,key
