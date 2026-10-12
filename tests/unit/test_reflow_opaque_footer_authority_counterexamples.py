"""Source-shaped authored content below decorative rules remains ordinary prose.

These constructed scan-page controls reuse independently viewed original author
paragraph/list text from the portable eight-page physical source fixture. Only
placement, type size, decorative rule and one added opening quote mark are
deliberately synthetic; no actual
book failure or physical footnote is invented by these counterexamples.
"""
from dataclasses import asdict
from pathlib import Path
import copy,gzip,json,hashlib
import pymupdf
import pytest
from cps.services.reflow import extract,skeleton

pytestmark=pytest.mark.unit
FIXTURE=Path(__file__).parents[1]/'fixtures/reflow/opaque_residual_note_family_original_context.json.gz'

def authored_source(key,lid):
 assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest()=='64179aba64dac2e9489726b0b977d4ef1a8d30838ef487f1bef58edac3215f52'
 data=json.loads(gzip.decompress(FIXTURE.read_bytes()));assert data['physical_proof_sha256']=='e5fb264441fc5a6045186d7afd218e2c368d8f039bef1e40f5c35f74ed03b5e0';case=data['cases'][key]
 row=next(r for r in case['adjacent_preservation_rows']if r['id']==lid)
 # Authored role is independent physical evidence, never an inherited note role.
 assert case['expected_note_rows'] and lid not in case['expected_note_rows']
 return ''.join(span['text']for span in row['source']['spans']).strip()


def inputs(case):
 body=[authored_source('567:169','l3'),authored_source('567:169','l4')]
 quote=[authored_source('567:169','l5'),authored_source('567:169','l6')]
 if case=='same_type_apostrophe_quote':quote[0]="'"+quote[0]
 tail_size=12 if case=='same_type_apostrophe_quote'else 9
 document=pymupdf.open();page=document.new_page(width=504,height=720)
 def line(text,x,y,size):
  # Measured source geometry is explicit, independent of renderer line extraction.
  width=pymupdf.get_text_length(text,fontname='tiro',fontsize=size)
  page.insert_text((x,y),text,fontname='tiro',fontsize=size)
  span=extract.Span(text,size,'Times-Roman',4,(x,y-size*1.053,x+width,y+size*.3),origin_y=y)
  return extract.Line([span],span.bbox)
 above=[line(body[0],40,450,12),line(body[1],40,480,12)]
 page.draw_line((40,560),(170,560),width=.5,color=(0,0,0))
 if case=='authored_numbered_list':
  below=[line(authored_source('569:158','l3'),40,594,9)]
  for y,marker,literal in [(615,'1.','l6'),(635,'2.','l8'),(655,'3.','l10')]:
   below.extend([line(marker,40,y,9),line(authored_source('569:158',literal),58,y,9)])
 else:below=[line(text,40,594+i*18,tail_size)for i,text in enumerate(quote)]
 # Actual scan-shaped constructor: is_page_scan is a derived read-only property.
 raw=extract.RawPage(0,504,720,[extract.Block(0,(40,438,480,482),above),extract.Block(1,(40,580,480,670),below)],images=[extract.Image((0,0,504,720),1.0)])
 assert raw.is_page_scan
 return document,raw,skeleton.BookStyle(body_size=12),above+below,below


@pytest.mark.parametrize('case',['unmarked_smaller_author_quote','same_type_apostrophe_quote','authored_numbered_list'])
def test_rule_and_type_or_ordinary_apostrophe_cannot_certify_authored_footer(case):
 document,raw,style,lines,authored=inputs(case);before=copy.deepcopy(asdict(raw))
 try:
  probe=extract.ScanPixelProbe(document,0)
  # An actual complete thin decorative rule must be present: this safety check
  # cannot pass merely because missing pixels short-circuit the recognizer.
  ink=probe.source_ink_bounds((28,max(line.bbox[3]for block in raw.text_blocks[:1]for line in block.lines)+.5,490,580))
  assert ink and ink[2]-ink[0]>=129 and ink[3]-ink[1]<4
  separator=probe.thin_separator((ink[0]-1,ink[1]-10,ink[2]+1,575),max_thickness=2.4)
  assert separator and separator['occupied_fraction']>=.8
  result=skeleton._opaque_complete_note_territory(raw,style,lines,probe)
  assert result is None,(case,'Authored quote/list was inferred to be a printed source footnote',[(line.text,line.bbox)for line in authored])
  assert asdict(raw)==before
 finally:document.close()
