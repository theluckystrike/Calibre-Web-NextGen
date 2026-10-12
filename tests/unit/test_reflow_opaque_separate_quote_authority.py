"""A separately extracted ordinary opening quote is still authored prose.

This constructed source-shaped case reuses the independently sourced authored
paragraph and identical rendered pixels from the existing three safety controls.
Only the retained span partition changes; no printed pixels or words change.
"""
from dataclasses import asdict
import copy,hashlib
import pymupdf
import pytest
from cps.services.reflow import extract,skeleton
from tests.unit.test_reflow_opaque_footer_authority_counterexamples import inputs

pytestmark=pytest.mark.unit


def test_same_type_separate_opening_quote_does_not_authorize_source_footnote():
 document,raw,style,lines,authored=inputs('same_type_apostrophe_quote')
 try:
  original_pixels=document[0].get_pixmap(matrix=pymupdf.Matrix(2,2),colorspace=pymupdf.csGRAY,alpha=False).samples
  opening=authored[0];original=opening.spans[0];assert original.text.startswith("'")
  boundary=original.bbox[0]+pymupdf.get_text_length("'",fontname='tiro',fontsize=original.size)
  quote=extract.Span("'",original.size,original.font,original.flags,(original.bbox[0],original.bbox[1],boundary,original.bbox[3]),origin_y=original.origin_y)
  lexical=extract.Span(original.text[1:],original.size,original.font,original.flags,(boundary,original.bbox[1],original.bbox[2],original.bbox[3]),origin_y=original.origin_y)
  opening.spans=[quote,lexical]
  assert opening.text==original.text
  assert quote.size==lexical.size==style.body_size
  assert quote.origin_y==lexical.origin_y
  assert quote.bbox[1:4:2]==lexical.bbox[1:4:2]
  assert document[0].get_pixmap(matrix=pymupdf.Matrix(2,2),colorspace=pymupdf.csGRAY,alpha=False).samples==original_pixels
  before=copy.deepcopy(asdict(raw));probe=extract.ScanPixelProbe(document,0)
  bottom=max(line.bbox[3]for block in raw.text_blocks[:1]for line in block.lines)
  ink=probe.source_ink_bounds((28,bottom+.5,490,580))
  assert ink and ink[2]-ink[0]>=129 and ink[3]-ink[1]<4
  separator=probe.thin_separator((ink[0]-1,ink[1]-10,ink[2]+1,575),max_thickness=2.4)
  assert separator and separator['occupied_fraction']>=.8
  result=skeleton._opaque_complete_note_territory(raw,style,lines,probe)
  assert result is None,'Ordinary independently measured same-font opening quote authorized a source-note territory'
  assert asdict(raw)==before
 finally:document.close()
