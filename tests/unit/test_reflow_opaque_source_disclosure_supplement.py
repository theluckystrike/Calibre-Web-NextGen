"""Physically proved native fallback headers and footnotes retain distinct lanes.

The three original PDF pages, retained raw source and full-book style are portable.
No numeral is corrected from the physical review. Publisher classification is not
an oracle for the independently observed source note/header territories.
"""
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import copy
import hashlib
import json
import math

import pymupdf
from PIL import Image, ImageDraw
import pytest

from cps.services.reflow import extract, skeleton, transcript_regions
from tests.unit.test_reflow_physical_footer_canonical_delivery import raw_page, digest
from tests.unit.test_reflow_opaque_paired_furniture import style, furniture, peer_style

pytestmark = pytest.mark.unit
FIXTURE = Path(__file__).parents[1]/'fixtures/reflow/opaque_source_disclosure_supplement_context.json'
PAGES = [220,565,573]
TARGETS = [(220,'l0'),(220,'l1'),(220,'l27'),(565,'l0'),(565,'l1'),(573,'l0'),(573,'l1'),(573,'l40'),(573,'l41')]


def note(region):
    return region.kind == 'note' or region.reason == 'ocr_uncertain_note'


@pytest.fixture(scope='module')
def cases():
    data=json.loads(FIXTURE.read_text());path=FIXTURE.parent/data['source_pdf']['path']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==data['source_pdf']['sha256']
    measured={}
    try:
        for page in PAGES:
            record=data['cases'][str(page)];raw=raw_page(record['raw']);before=asdict(raw)
            assert digest(before)==record['raw_sha256']
            doc=pymupdf.open(path);measured[page]=(raw,None,None,doc,record,{})
            assert list(doc[page].rect)==record['frame'] and doc[page].rotation==record['rotation']==0
            pix=doc[page].get_pixmap(matrix=pymupdf.Matrix(2,2),colorspace=pymupdf.csGRAY,alpha=False)
            assert hashlib.sha256(pix.samples).hexdigest()==record['fullframe_sha256']
            rows={}
            for proof in record['physical_source_rows']:
                row=raw.blocks[proof['block_index']].lines[proof['line_index']]
                assert digest(asdict(row))==proof['sha256']
                assert json.loads(json.dumps(asdict(row)))==proof['source']
                rows[proof['line_id']]=(row,proof)
            original=copy.deepcopy(record['original_provenance'])
            if 'source_pdf_sha256' in original.get('verification',{}):
                assert original['verification']['source_pdf_sha256']==data['source_pdf']['original_sha256']
                original['verification']['source_pdf_sha256']=data['source_pdf']['sha256']
            assert original==record['provenance']
            context=peer_style(data['book_style'],raw);probe=extract.ScanPixelProbe(doc,page,
                mask=[line.bbox for block in raw.text_blocks for line in block.lines])
            candidate=transcript_regions.candidate(raw,copy.deepcopy(record['provenance']),doc,context,
                pixel_probe=probe,layer_trusted=True) if raw.transcript_unverified else None
            canonical=candidate[0] if candidate else skeleton.page_skeleton(raw,context,
                pixel_probe=probe,layer_trusted=not raw.transcript_unverified)
            opaque=skeleton.opaque_page_regions(raw,context,pixel_probe=probe)
            assert asdict(raw)==before
            measured[page]=(raw,canonical.regions,opaque,doc,record,rows)
        yield measured
    finally:
        for _,_,_,doc,_,_ in measured.values():doc.close()


@pytest.mark.parametrize('page,line_id',TARGETS)
def test_exact_physical_source_role_has_one_complete_canonical_owner(cases,page,line_id):
    _,regions,_,_,_,rows=cases[page];row,proof=rows[line_id]
    owners=[r for r in regions if any(row is line for line in r.lines+r.caption_lines)]
    qualifies=note if proof['kind']=='printed_note_body' else furniture
    assert len(owners)==1 and qualifies(owners[0]),(page,line_id,[(r.kind,r.reason)for r in owners])
    assert tuple(proof['source']['bbox'])==row.bbox


@pytest.mark.parametrize('page,line_id',TARGETS)
def test_physical_note_or_header_ink_is_not_in_ordinary_opaque_body_images(cases,page,line_id):
    _,_,regions,doc,_,rows=cases[page];row,proof=rows[line_id];bad=[]
    for r in regions:
        if r.kind!='figure' or furniture(r) or note(r):continue
        intersection=pymupdf.Rect(r.bbox)&pymupdf.Rect(row.bbox)
        if intersection.is_empty:continue
        pix=doc[page].get_pixmap(clip=intersection,matrix=pymupdf.Matrix(2,2),colorspace=pymupdf.csGRAY,alpha=False)
        ink=sum(value<160 for value in pix.samples)
        if ink>2:bad.append((r.reason,ink,list(intersection)))
    assert not bad,(page,line_id,bad)


@pytest.mark.parametrize('page',PAGES)
def test_source_identity_all_rows_once_and_every_other_row_outside_disclosure_lanes(cases,page):
    raw,canonical,opaque,_,record,rows=cases[page]
    expected=Counter(digest(asdict(line))for block in raw.text_blocks for line in block.lines)
    special={id(row)for row,_ in rows.values()}
    for regions in (canonical,opaque):
        assert Counter(digest(asdict(line))for r in regions for line in r.lines+r.caption_lines)==expected
        for block in raw.text_blocks:
            for line in block.lines:
                if id(line)in special:continue
                owners=[r for r in regions if any(line is item for item in r.lines+r.caption_lines)]
                assert len(owners)==1 and not furniture(owners[0]) and not note(owners[0]),(page,line.text)
    assert json.loads(json.dumps(asdict(raw)))==record['raw']


@pytest.mark.parametrize('page',PAGES)
def test_zero_original_dark_pixels_lost_outside_physically_proved_header_scopes(cases,page):
    _,_,regions,doc,record,rows=cases[page]
    pix=doc[page].get_pixmap(matrix=pymupdf.Matrix(2,2),colorspace=pymupdf.csGRAY,alpha=False)
    support=Image.new('L',(pix.width,pix.height),0);paint=ImageDraw.Draw(support)
    for r in regions:
        if r.kind=='figure' and not furniture(r):
            b=r.bbox;paint.rectangle((math.floor(b[0]*2),math.floor(b[1]*2),math.ceil(b[2]*2)-1,math.ceil(b[3]*2)-1),fill=255)
    outside=Image.new('L',support.size,255);paint=ImageDraw.Draw(outside)
    for row,proof in rows.values():
        if proof['kind']=='printed_furniture':
            b=row.bbox;paint.rectangle((math.floor(b[0]*2),math.floor(b[1]*2),math.ceil(b[2]*2)-1,math.ceil(b[3]*2)-1),fill=0)
    visible,eligible=support.tobytes(),outside.tobytes()
    missing=sum(v<160 and eligible[i]>0 and visible[i]==0 for i,v in enumerate(pix.samples))
    assert missing==0,(page,missing)
    assert hashlib.sha256(pix.samples).hexdigest()==record['fullframe_sha256']
