"""Furniture exclusions remove owned glyphs, never the surrounding chart ink."""
import copy
import hashlib
import io
import json
from pathlib import Path
import pytest
from PIL import Image, ImageDraw
from cps.services.reflow import build_epub, assemble, extract

pytestmark = pytest.mark.unit
FIX = Path(__file__).parents[1] / 'fixtures/reflow/source_furniture_pixels'
ROWS = json.loads((FIX / 'manifest.json').read_text())


def png(image):
    stream=io.BytesIO(); image.save(stream,format='PNG'); return stream.getvalue()


def pixels(data):
    return Image.open(io.BytesIO(data)).convert('RGB')


@pytest.mark.parametrize('row', ROWS, ids=lambda r:str(r['page']))
def test_actual_carrier_head_erasure_preserves_every_unowned_pixel(row):
    original=(FIX/row['image']).read_bytes()
    assert hashlib.sha256(original).hexdigest()==row['image_sha256']
    data,audit=build_epub._exclude_source_furniture_pixels(original,row['bbox'],
        row['furniture_boxes'],row['protected_boxes'])
    before,after=pixels(original),pixels(data)
    assert before.size==after.size and audit
    x0,y0,x1,y1=row['bbox']; sx=before.width/(x1-x0);sy=before.height/(y1-y0)
    contexts=[((b[0]-x0-3)*sx,(b[1]-y0-3)*sy,(b[2]-x0+3)*sx,(b[3]-y0+3)*sy) for b in row['furniture_boxes']]
    old=list(before.getdata());new=list(after.getdata());changed=[];dark=0;removed=0
    for i,(a,b) in enumerate(zip(old,new)):
        x,y=i%before.width,i//before.width
        owned=any(c[0]<=x<=c[2] and c[1]<=y<=c[3] for c in contexts)
        if owned and min(a)<180:dark+=1;removed+=min(b)>235
        if a!=b:
            assert owned, (row['page'],x,y,'chart or center rule changed')
            changed.append(i)
    assert changed and removed>dark*.85, (row['page'],removed,dark)
    # On source46 the center rule runs from the very top through the crop.
    assert any(min(p)<100 for i,p in enumerate(old) if not any(c[0]<=i%before.width<=c[2] and c[1]<=i//before.width<=c[3] for c in contexts))


@pytest.mark.parametrize('damage',['none','connected','protected','empty','invalid'])
def test_component_ownership_and_protection(damage):
    image=Image.new('RGB',(200,100),'white');d=ImageDraw.Draw(image)
    d.rectangle((40,20,49,28),fill='black');d.rectangle((130,0,130,99),fill='black')
    if damage=='connected':d.line((49,24,130,24),fill='black')
    furniture=[] if damage=='empty' else [(40,20,50,29)]
    protected=[(44,22,47,27)] if damage=='protected' else []
    bbox=(0,0,0,100) if damage=='invalid' else (0,0,200,100)
    original=png(image)
    data,audit=build_epub._exclude_source_furniture_pixels(original,bbox,furniture,protected)
    result=pixels(data)
    if damage=='none':
        assert result.getpixel((44,24))==(255,255,255) and audit
    else:assert result.tobytes()==image.tobytes(),damage
    assert result.crop((100,0,200,100)).tobytes()==image.crop((100,0,200,100)).tobytes()


def test_pixel_projection_uses_source_offset_and_independent_xy_scale():
    image=Image.new('RGB',(240,90),'white');ImageDraw.Draw(image).rectangle((60,30,70,36),fill='black')
    data,audit=build_epub._exclude_source_furniture_pixels(png(image),(100,200,220,290),[(130,230,136,237)],[])
    assert pixels(data).getpixel((65,33))==(255,255,255) and audit


def inventory_book():
    head=extract.Line([extract.Span('44 TRADITIONAL ASTROLOGY',9,'ocr',0,(20,10,150,19),19)],(20,10,150,19))
    body=extract.Line([extract.Span('The chart caption must remain.',10,'ocr',0,(20,100,180,112),112)],(20,100,180,112))
    inventory={'source_geometry':{'space':'reading','page_rect':[0,0,400,600]},
        'raw_images':[{'page_background':True}],
        'regions':[{'suggested_kind':'furniture','reason':'repeated_scan_spread_head','geometry_status':'valid','line_ids':['l0'],'bbox':[20,10,150,19]}],
        'lines':[{'id':'l0','source':head},{'id':'l1','source':body}]}
    return assemble.Book(source_inventory={0:inventory}), {'pno':0,'found':'scan_figure_band','bbox':[10,5,200,200],'source_geometry':{'space':'reading'}}


def test_source_owned_head_eligibility_protects_caption_and_keeps_canonical_inventory():
    book,figure=inventory_book();before=copy.deepcopy(book.source_inventory);f_before=copy.deepcopy(figure)
    owned,protected=build_epub._source_furniture_pixel_boxes(book,0,figure)
    assert owned==[(20,10,150,19)] and (20,100,180,112) in protected
    assert book.source_inventory==before and figure==f_before


@pytest.mark.parametrize('damage',['native','table','full_page','glyph','caption','unknown_reason','invalid_region','missing_line','wrong_page','no_scan','interior','tiny_literal','required_region'])
def test_unproved_source_role_never_authorizes_pixel_removal(damage):
    book,figure=inventory_book();inv=book.source_inventory[0];region=inv['regions'][0]
    if damage=='native':figure['source_geometry']={}
    elif damage=='table':figure['found']='source_visual_table'
    elif damage=='full_page':figure['full_page']=True
    elif damage=='glyph':figure['found']='ocr_uncertain_region'
    elif damage=='caption':region['suggested_kind']='caption'
    elif damage=='unknown_reason':region['reason']='running_caps'
    elif damage=='invalid_region':region['geometry_status']='invalid'
    elif damage=='missing_line':region['line_ids']=['missing']
    elif damage=='wrong_page':book.source_inventory={1:inv}
    elif damage=='no_scan':inv['raw_images']=[]
    elif damage=='interior':region['bbox']=[20,180,150,189];inv['lines'][0]['source'].bbox=(20,180,150,189)
    elif damage=='tiny_literal':inv['lines'][0]['source'].spans[0].text='i'
    elif damage=='required_region':figure['found']='unrecovered_scan_layer'
    owned,_=build_epub._source_furniture_pixel_boxes(book,0,figure)
    assert not owned,damage
