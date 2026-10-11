"""A source-proved head inside an OCR chart is removed without changing chart ink.

The witness is the rejected9b6 source30 carrier, not a fabricated happy path.
Uncertain prose, missing artwork/caption proof and native territory stay protected.
"""
import copy
import hashlib
import io
import json
from pathlib import Path
import pytest
from PIL import Image
from cps.services.reflow import assemble,build_epub,extract

pytestmark=pytest.mark.unit
FIX=Path(__file__).parents[1]/'fixtures/reflow/ocr_chart_furniture'


def witness():
    row=json.loads((FIX/'witness.json').read_text())
    inv=row['inventory']
    for line in inv['lines']:
        source=line['source']
        line['source']=extract.Line([extract.Span(**dict(s,bbox=tuple(s['bbox'])))for s in source['spans']],tuple(source['bbox']),spacing_uncertain=source['spacing_uncertain'],transcription_uncertain=source['transcription_uncertain'])
    return row,assemble.Book(source_inventory={30:inv})


def test_actual_chart_head_is_eligible_and_every_unowned_pixel_survives():
    row,book=witness();before=copy.deepcopy(book.source_inventory);figure=copy.deepcopy(row['figure'])
    owned,protected=build_epub._source_furniture_pixel_boxes(book,30,figure)
    assert owned,'Published source30 still visibly contains its canonical running head'
    assert len(owned)==6
    assert book.source_inventory==before and figure==row['figure']
    data=(FIX/row['pre_padding_image']).read_bytes()
    assert hashlib.sha256(data).hexdigest()==row['pre_padding_image_sha256']
    result,audit=build_epub._exclude_source_furniture_pixels(data,figure['bbox'],owned,protected)
    original=Image.open(io.BytesIO(data)).convert('RGB');after=Image.open(io.BytesIO(result)).convert('RGB')
    assert original.size==after.size and audit
    x0,y0,x1,y1=figure['bbox'];sx=original.width/(x1-x0);sy=original.height/(y1-y0)
    boxes=[((b[0]-x0-3)*sx,(b[1]-y0-3)*sy,(b[2]-x0+3)*sx,(b[3]-y0+3)*sy)for b in owned]
    old=list(original.getdata());new=list(after.getdata());removed=dark=0
    for i,(a,b)in enumerate(zip(old,new)):
        x,y=i%original.width,i//original.width
        inside=any(box[0]<=x<=box[2] and box[1]<=y<=box[3]for box in boxes)
        if not inside:assert a==b,(x,y,'unowned chart ink changed')
        elif min(a)<180:dark+=1;removed+=min(b)>235
    assert dark>100 and removed/dark>.9
    assert sum(min(p)<100 for i,p in enumerate(new)if i//original.width>original.height*.3)>1000


@pytest.mark.parametrize('damage',['no_chart_artwork','no_caption','missing_caption','moved_region','invalid_region','prose_carrier','native','full_page','unproved_furniture','authored_title'])
def test_uncertain_prose_and_unproved_source_never_authorize_erasure(damage):
    row,book=witness();inv=book.source_inventory[30];figure=row['figure'];carrier=inv['regions'][0]
    if damage=='no_chart_artwork':inv['regions']=[r for r in inv['regions']if r.get('reason')!='figure_lettering']
    elif damage=='no_caption':carrier['caption_line_ids']=[]
    elif damage=='missing_caption':carrier['caption_line_ids']=['missing']
    elif damage=='moved_region':carrier['bbox']=[0,0,10,10]
    elif damage=='invalid_region':carrier['geometry_status']='invalid'
    elif damage=='prose_carrier':figure['bbox']=[103.86,325.62,390.78,513.9]
    elif damage=='native':figure['source_geometry']={}
    elif damage=='full_page':figure['full_page']=True
    elif damage=='unproved_furniture':inv['regions'][1]['reason']='running_caps'
    elif damage=='authored_title':inv['regions'][1]['suggested_kind']='heading'
    owned,_=build_epub._source_furniture_pixel_boxes(book,30,figure)
    assert not owned,damage
