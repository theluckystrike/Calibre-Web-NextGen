"""Printed exercise and analysis-table content cannot acquire note ownership.

The complete original operators and retained recovery/style reproduce actual
source regressions. Independent source views establish the role expectations;
an ephemeris footnote on a fourth page remains a positive control.
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
FIXTURE=Path(__file__).parents[1]/'fixtures/reflow/authored_note_authority_original_context.json.gz'
KEYS=['569:507','570:527','570:531','569:297']

@pytest.fixture(scope='module')
def classified():
 data=json.loads(gzip.decompress(FIXTURE.read_bytes()))
 assert data['physical_proof_sha256']=='3c5c05847d46bd6e3135153157ee6f1473675165846bd5c2dcc5d5159e2d135e'
 results={}
 for key in KEYS:
  bid,pno=map(int,key.split(':'));r=data['cases'][key];pdf=data['source_pdfs'][str(bid)];path=FIXTURE.parent/pdf['path']
  assert hashlib.sha256(path.read_bytes()).hexdigest()==pdf['sha256']
  raw=raw_page(r['raw']);before=asdict(raw);assert digest(before)==r['raw_sha256']
  rows={x['id']:raw.blocks[x['block_index']].lines[x['line_index']]for x in r['all_source_rows']}
  assert all(digest(asdict(rows[x['id']]))==x['source_sha256']for x in r['all_source_rows'])
  context=style(r['style']);context_before=asdict(context)
  # The classification handle is cold; the oracle handle is independent and
  # opened only after classification, so no preview can change the admission.
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
  results[key]=(raw,result,rows,r)
 return results

@pytest.mark.parametrize('key',KEYS[:3])
def test_original_exercise_and_analysis_table_rows_remain_authored(classified,key):
 _,result,rows,r=classified[key]
 for lid in r['target_rows']:
  owners=[g for g in result.regions if any(rows[lid]is l for l in g.lines+g.caption_lines)]
  assert len(owners)==1 and not note(owners[0])and not furniture(owners[0]),(key,lid,[(g.kind,g.reason)for g in owners])

def test_original_ephemeris_instructions_are_a_complete_printed_footnote(classified):
 _,result,rows,r=classified['569:297']
 for lid in r['target_rows']:
  owners=[g for g in result.regions if any(rows[lid]is l for l in g.lines+g.caption_lines)]
  assert len(owners)==1 and note(owners[0]),(lid,[(g.kind,g.reason)for g in owners])

@pytest.mark.parametrize('key',KEYS)
def test_every_original_source_row_has_exactly_one_unchanged_owner(classified,key):
 raw,result,_,_=classified[key]
 assert Counter(digest(asdict(l))for b in raw.text_blocks for l in b.lines)==Counter(digest(asdict(l))for g in result.regions for l in g.lines+g.caption_lines)
