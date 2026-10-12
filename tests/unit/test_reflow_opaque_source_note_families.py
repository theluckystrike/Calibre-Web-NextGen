"""Original printed footer families remain distinct from authored source content.

Eleven original operator pages provide quote/asterisk/native citation/commentary
footers and actual table/exercise/body negatives. Physical source evidence fixes
roles; converter role guesses are never used as the test oracle.
"""
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import copy,gzip,hashlib,json,math
import pymupdf
from PIL import Image,ImageDraw
import pytest
from cps.services.reflow import extract,skeleton,transcript_regions
from tests.unit.test_reflow_physical_footer_canonical_delivery import raw_page,digest
from tests.unit.test_reflow_opaque_paired_furniture import style,furniture

pytestmark=pytest.mark.unit
FIXTURE=Path(__file__).parents[1]/'fixtures/reflow/opaque_note_family_original_context.json.gz'
KEYS=['562:8','562:10','564:375','569:59','569:93','569:275','569:478','570:50','570:556','570:465','570:476']

def note(region):return region.kind=='note' or region.reason=='ocr_uncertain_note'

@pytest.fixture(scope='module')
def cases():
    data=json.loads(gzip.decompress(FIXTURE.read_bytes()));measured={}
    try:
        for key in KEYS:
            bid,page=map(int,key.split(':'));record=data['cases'][key];source=data['source_pdfs'][str(bid)]
            path=FIXTURE.parent/source['path'];assert hashlib.sha256(path.read_bytes()).hexdigest()==source['sha256']
            doc=pymupdf.open(path);raw=raw_page(record['raw']);before=asdict(raw)
            measured[key]=(raw,None,None,doc,record,{})
            assert digest(before)==record['raw_sha256']
            assert list(doc[page].rect)==record['frame'] and doc[page].rotation==record['rotation']==0
            pix=doc[page].get_pixmap(matrix=pymupdf.Matrix(2,2),colorspace=pymupdf.csGRAY,alpha=False)
            assert hashlib.sha256(pix.samples).hexdigest()==record['fullframe_sha256']
            rows={}
            for proof in record['all_source_rows']:
                row=raw.blocks[proof['block_index']].lines[proof['line_index']]
                assert digest(asdict(row))==proof['source_sha256'];rows[proof['id']]=row
            context=style(record['style']);probe=extract.ScanPixelProbe(doc,page,mask=[r.bbox for r in rows.values()])
            provenance=copy.deepcopy(record['provenance'])
            if 'source_pdf_sha256' in provenance.get('verification',{}):
                assert provenance['verification']['source_pdf_sha256']==source['original_sha256']
                provenance['verification']['source_pdf_sha256']=source['sha256']
            candidate=transcript_regions.candidate(raw,provenance,doc,context,pixel_probe=probe,layer_trusted=True) if raw.transcript_unverified else None
            canonical=candidate[0] if candidate else skeleton.page_skeleton(raw,context,pixel_probe=probe,layer_trusted=not raw.transcript_unverified)
            opaque=skeleton.opaque_page_regions(raw,context,pixel_probe=probe)
            assert asdict(raw)==before
            measured[key]=(raw,canonical.regions,opaque,doc,record,rows)
        yield measured
    finally:
        for _,_,_,doc,_,_ in measured.values():doc.close()

@pytest.mark.parametrize('key',KEYS)
def test_physical_source_note_rows_have_complete_canonical_and_opaque_note_owners(cases,key):
    _,canonical,opaque,_,record,rows=cases[key]
    for regions in [canonical,opaque]:
        for lid in record['expected_note_rows']:
            owners=[r for r in regions if any(rows[lid]is ln for ln in r.lines+r.caption_lines)]
            assert len(owners)==1 and note(owners[0]),(key,lid,[(r.kind,r.reason)for r in owners])

@pytest.mark.parametrize('key',KEYS)
def test_original_printed_note_ink_is_outside_main_opaque_source_strips(cases,key):
    raw,_,opaque,doc,record,rows=cases[key]
    for lid in record['expected_note_rows']:
        for r in opaque:
            if r.kind!='figure' or note(r) or furniture(r):continue
            intersection=pymupdf.Rect(r.bbox)&pymupdf.Rect(rows[lid].bbox)
            if intersection.is_empty:continue
            pix=doc[raw.pno].get_pixmap(clip=intersection,matrix=pymupdf.Matrix(2,2),colorspace=pymupdf.csGRAY,alpha=False)
            assert not any(v<160 for v in pix.samples),(key,lid,r.bbox)

@pytest.mark.parametrize('key',KEYS)
def test_all_source_rows_once_and_physically_authored_neighbors_outside_notes_furniture(cases,key):
    raw,canonical,opaque,_,record,rows=cases[key]
    expected=Counter(digest(asdict(ln))for b in raw.text_blocks for ln in b.lines)
    for regions in [canonical,opaque]:
        assert Counter(digest(asdict(ln))for r in regions for ln in r.lines+r.caption_lines)==expected
        authored=record['adjacent_preservation_rows']
        if not record['expected_note_rows']:authored=[dict(id=lid,source=asdict(row))for lid,row in rows.items()]
        for proof in authored:
            row=rows[proof['id']];assert digest(asdict(row))==digest(proof['source'])
            owners=[r for r in regions if any(row is ln for ln in r.lines+r.caption_lines)]
            assert len(owners)==1 and not note(owners[0]),(key,proof['id'],[(r.kind,r.reason)for r in owners])
            observed_folios={r['line_id'] for r in record.get('physically_viewed_adjacent_folios',[])}
            if record['expected_note_rows'] and proof['id'] not in observed_folios:
                assert not furniture(owners[0]),(key,proof['id'])

@pytest.mark.parametrize('key',KEYS)
def test_all_original_opaque_page_ink_remains_covered_without_resizing(cases,key):
    raw,_,opaque,doc,_,_=cases[key]
    pix=doc[raw.pno].get_pixmap(matrix=pymupdf.Matrix(2,2),colorspace=pymupdf.csGRAY,alpha=False)
    source=Image.frombytes('L',(pix.width,pix.height),pix.samples);support=Image.new('L',source.size,0);draw=ImageDraw.Draw(support)
    for r in opaque:
        if r.kind=='figure':
            b=r.bbox;draw.rectangle((math.floor(2*b[0]),math.floor(2*b[1]),math.ceil(2*b[2])-1,math.ceil(2*b[3])-1),fill=255)
    missing=sum(v<160 and not covered for v,covered in zip(source.tobytes(),support.tobytes()))
    assert missing==0,(key,missing)
