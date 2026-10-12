"""Constructed pixel counterfactuals on exact-original smaller native footers.

Only the originally empty body/footer gap is painted. Literal retained rows,
spelling, uncertainty and geometry are immutable; source pixels are the input
being deliberately varied. A sub-em gap by itself cannot certify note ink.
"""
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import copy,hashlib,json,math

import pymupdf
import pytest
from cps.services.reflow import extract,skeleton
from tests.unit.test_reflow_physical_footer_canonical_delivery import raw_page,digest
from tests.unit.test_reflow_opaque_paired_furniture import style
from tests.unit.test_reflow_opaque_source_disclosure_supplement import note,FIXTURE

pytestmark=pytest.mark.unit
SHAPES=['absent','shifted','thick','glyph_like','table_like','clipped_lower_stroke']


@pytest.mark.parametrize('page',[220,573])
@pytest.mark.parametrize('shape',SHAPES)
def test_original_sub_em_footer_requires_complete_unambiguous_source_divider(page,shape,tmp_path):
    data=json.loads(FIXTURE.read_text());rec=data['cases'][str(page)]
    path=FIXTURE.parent/data['source_pdf']['path']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==data['source_pdf']['sha256']
    raw=raw_page(rec['raw']);before=asdict(raw);context=style(data['book_style'])
    target=[raw.blocks[p['block_index']].lines[p['line_index']]for p in rec['physical_source_rows']if p['kind']=='printed_note_body']
    top=min(line.bbox[1]for line in target)
    # Independently retained original body lower edge; the physical notes are
    # excluded by identity, rather than by the converter's classification.
    eligible=[line for block in raw.text_blocks for line in block.lines if line not in target and line.bbox[3]<=top]
    bottom=max(line.bbox[3]for line in eligible)
    left=min(line.bbox[0]for line in eligible);right=max(line.bbox[2]for line in eligible)
    em=context.body_size
    assert .5*em<top-bottom<em
    original=pymupdf.open(path);doc=pymupdf.open(path);sheet=doc[page]
    x0=left; x1=left+75; y0=top-3
    changed=pymupdf.Rect(0,bottom+.5,raw.width,top+6 if shape=='clipped_lower_stroke'else top-.5)
    sheet.draw_rect(changed,color=None,fill=(1,1,1),overlay=True)
    black=(0,0,0)
    if shape=='shifted':sheet.draw_rect(pymupdf.Rect(x0+120,y0,x1+120,top-.5),color=None,fill=black)
    elif shape=='thick':sheet.draw_rect(pymupdf.Rect(x0,bottom+1,x1,top-.5),color=None,fill=black)
    elif shape=='glyph_like':
        for x in range(math.ceil(x0),math.floor(x1),6):sheet.draw_rect(pymupdf.Rect(x,bottom+1,x+2,top-1),color=None,fill=black)
    elif shape=='table_like':
        for y in (bottom+1,top-1):sheet.draw_line((x0,y),(x1,y),color=black,width=.7)
        for x in (x0,x0+25,x0+50,x1):sheet.draw_line((x,bottom+1),(x,top-1),color=black,width=.7)
    elif shape=='clipped_lower_stroke':sheet.draw_rect(pymupdf.Rect(x0,top-2,x1,top+6),color=None,fill=black)
    output=tmp_path/'counterfactual.pdf';doc.save(output);doc.close();doc=pymupdf.open(output)
    try:
        original_pix=original[page].get_pixmap(matrix=pymupdf.Matrix(2,2),colorspace=pymupdf.csGRAY,alpha=False)
        modified_pix=doc[page].get_pixmap(matrix=pymupdf.Matrix(2,2),colorspace=pymupdf.csGRAY,alpha=False)
        assert original_pix.width==modified_pix.width and original_pix.height==modified_pix.height
        # The actual mutation is localized; native frame and every outside
        # source pixel retain the original operator rendering exactly.
        extra=2;xlo=max(0,math.floor(changed.x0*2)-extra);xhi=min(original_pix.width,math.ceil(changed.x1*2)+extra)
        ylo=max(0,math.floor(changed.y0*2)-extra);yhi=min(original_pix.height,math.ceil(changed.y1*2)+extra)
        original_bytes, modified_bytes = original_pix.samples, modified_pix.samples
        assert any(a!=b for a,b in zip(original_bytes,modified_bytes))
        for y in range(original_pix.height):
            a=original_bytes[y*original_pix.width:(y+1)*original_pix.width];b=modified_bytes[y*original_pix.width:(y+1)*original_pix.width]
            assert a==b if y<ylo or y>=yhi else a[:xlo]==b[:xlo]and a[xhi:]==b[xhi:]
        probe=extract.ScanPixelProbe(doc,page,mask=[line.bbox for block in raw.text_blocks for line in block.lines])
        regions=skeleton.opaque_page_regions(raw,context,pixel_probe=probe)
        for line in target:
            owners=[r for r in regions if any(line is owned for owned in r.lines+r.caption_lines)]
            assert len(owners)==1 and not note(owners[0]),(page,shape,line.text,[(r.kind,r.reason)for r in owners])
        assert Counter(digest(asdict(line))for r in regions for line in r.lines+r.caption_lines)==Counter(digest(asdict(line))for block in raw.text_blocks for line in block.lines)
        assert asdict(raw)==before
    finally:original.close();doc.close()
