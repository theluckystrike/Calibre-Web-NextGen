"""A true printed footnote survives cold complete-page classification.

The source oracle predates the repair: exact original operators, all raw rows,
and the independently verified lower-page footnote 1 remain immutable.
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

pytestmark=pytest.mark.unit
FIXTURE=Path(__file__).parents[1]/'fixtures/reflow/source57096_original_context.json.gz'

@pytest.fixture(scope='module')
def classified():
 record=json.loads(gzip.decompress(FIXTURE.read_bytes()));path=FIXTURE.parent/record['source_pdf']
 assert hashlib.sha256(path.read_bytes()).hexdigest()==record['source_pdf_sha256']
 witness=record['physical_note_role']
 assert witness['source_row_sha256']=='08b659baf6f2abd0ef9828076bf3eb71ac251004e6e0a3c1a597ba06a9f3f74c'
 assert witness['source_verified']and witness['kind']=='printed_note_body'
 raw=raw_page(record['raw']);before=asdict(raw);assert digest(before)==record['raw_sha256']
 rows={r['id']:raw.blocks[r['block_index']].lines[r['line_index']]for r in record['all_source_rows']}
 assert all(digest(asdict(rows[r['id']]))==r['source_sha256']for r in record['all_source_rows'])
 context=style(record['style']);context_before=asdict(context)
 with pymupdf.open(path)as doc:
  assert list(doc[96].rect)==record['frame']and doc[96].rotation==record['rotation']
  display=SourceDisplay(doc,96,dict(raw.source_geometry,layer='ocr'if raw.is_page_scan else'native'))
  with display.query_document(isolate=True)as reading:
   probe=extract.ScanPixelProbe(reading,96,mask=[l.bbox for l in rows.values()])
   trusted=assess.looks_like_prose(raw.text)
   candidate=transcript_regions.candidate(raw,record['provenance'],doc,context,pixel_probe=probe,layer_trusted=trusted)if raw.transcript_unverified else None
   result=candidate[0]if candidate else skeleton.page_skeleton(raw,context,pixel_probe=probe,layer_trusted=trusted)
 assert asdict(raw)==before and asdict(context)==context_before
 with pymupdf.open(path)as oracle:
  pix=oracle[96].get_pixmap(matrix=pymupdf.Matrix(2,2),colorspace=pymupdf.csGRAY,alpha=False)
  assert hashlib.sha256(pix.samples).hexdigest()==record['fullframe_sha256']
  yield raw,result,rows,record,oracle

def test_original_printed_footnote_has_one_note_owner(classified):
 _,result,rows,_,_=classified
 owners=[r for r in result.regions if any(rows['l30']is l for l in r.lines+r.caption_lines)]
 assert len(owners)==1 and note(owners[0]),[(r.kind,r.reason)for r in owners]

def test_footnote_ink_is_absent_from_body_flow_rasters(classified):
 _,result,rows,_,oracle=classified
 for r in result.regions:
  if r.kind not in('figure','artwork')or note(r)or furniture(r):continue
  overlap=pymupdf.Rect(r.bbox)&pymupdf.Rect(rows['l30'].bbox)
  if overlap.is_empty:continue
  pix=oracle[96].get_pixmap(clip=overlap,matrix=pymupdf.Matrix(3,3),colorspace=pymupdf.csGRAY,alpha=False)
  assert not any(v<160 for v in pix.samples),(r.kind,r.reason,list(overlap))

def test_every_original_source_row_survives_once(classified):
 raw,result,_,_,_=classified
 assert Counter(digest(asdict(l))for b in raw.text_blocks for l in b.lines)==Counter(digest(asdict(l))for r in result.regions for l in r.lines+r.caption_lines)
