"""A source-shaped note/folio gap crossed by art cannot become a pixel cut.

The retained original562 source8 note and folio are physically reviewed. Only
one explicitly constructed vertical stroke is added to their original PDF gap;
all original source words, flags and boxes remain untouched. No blank one-point
channel exists between the measured note bottom and folio top.
"""
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import gzip,hashlib,json,math
import pymupdf
from PIL import Image,ImageDraw
import pytest
from cps.services.reflow import extract,skeleton
from tests.unit.test_reflow_physical_footer_canonical_delivery import raw_page,digest
from tests.unit.test_reflow_opaque_paired_furniture import style,furniture
from tests.unit.test_reflow_opaque_source_note_families import note

pytestmark=pytest.mark.unit
FIXTURE=Path(__file__).parents[1]/'fixtures/reflow/opaque_note_family_original_context.json.gz'

def test_constructed_crossing_ink_refuses_note_to_folio_partition_without_blank_channel():
 data=json.loads(gzip.decompress(FIXTURE.read_bytes()));record=data['cases']['562:8'];source=data['source_pdfs']['562']
 path=FIXTURE.parent/source['path'];assert hashlib.sha256(path.read_bytes()).hexdigest()==source['sha256']
 raw=raw_page(record['raw']);before=asdict(raw);assert digest(before)==record['raw_sha256']
 rows={p['id']:raw.blocks[p['block_index']].lines[p['line_index']]for p in record['all_source_rows']}
 note_bottom=max(rows[lid].bbox[3]for lid in record['expected_note_rows'])
 folio=record['physically_viewed_adjacent_folios'][0];folio_top=rows[folio['line_id']].bbox[1]
 assert folio_top-note_bottom>4
 context=style(record['style'])
 doc=pymupdf.open(path)
 try:
  original=doc[8].get_pixmap(matrix=pymupdf.Matrix(2,2),colorspace=pymupdf.csGRAY,alpha=False)
  assert hashlib.sha256(original.samples).hexdigest()==record['fullframe_sha256']
  # Measure the unmodified source first: the positive partition is established,
  # so rejection below cannot pass from an unrelated missing-note fixture.
  original_regions=skeleton.opaque_page_regions(raw,context,extract.ScanPixelProbe(doc,8,mask=[l.bbox for l in rows.values()]))
  assert any(note(r)for r in original_regions)and any(furniture(r)for r in original_regions)
  x=raw.width*.45
  bar=pymupdf.Rect(x-1,note_bottom+.1,x+1,folio_top-.1)
  doc[8].draw_rect(bar,color=(0,0,0),fill=(0,0,0),overlay=True)
  probe=extract.ScanPixelProbe(doc,8,mask=[l.bbox for l in rows.values()])
  for y in (note_bottom+.5,(note_bottom+folio_top)/2,folio_top-.5):
   assert probe.source_has_ink((0,y-.5,raw.width,y+.5)),y
  regions=skeleton.opaque_page_regions(raw,context,probe)
  assert asdict(raw)==before
  assert Counter(digest(asdict(l))for b in raw.text_blocks for l in b.lines)==Counter(digest(asdict(l))for r in regions for l in r.lines+r.caption_lines)
  # No note/furniture strip may take the new authored ink or bisect it. A safe
  # fallback retains the complete source page when no separating channel exists.
  forbidden=[r for r in regions if r.kind=='figure'and(note(r)or furniture(r))and not(pymupdf.Rect(r.bbox)&bar).is_empty]
  assert not forbidden,[(r.reason,r.bbox)for r in forbidden]
  pix=doc[8].get_pixmap(matrix=pymupdf.Matrix(2,2),colorspace=pymupdf.csGRAY,alpha=False)
  support=Image.new('L',(pix.width,pix.height),0);draw=ImageDraw.Draw(support)
  for region in regions:
   if region.kind=='figure':
    b=region.bbox;draw.rectangle((math.floor(2*b[0]),math.floor(2*b[1]),math.ceil(2*b[2])-1,math.ceil(2*b[3])-1),fill=255)
  assert sum(v<160 and not c for v,c in zip(pix.samples,support.tobytes()))==0
 finally:doc.close()
