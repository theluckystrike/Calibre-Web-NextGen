"""ROOT-owned source-pixel footer oracle, independent of converter decisions.

The one fixture set retains full literal source pages and real peer context.
Expected note territories came from physical original-PDF viewing. The writer
cannot change this oracle. No external paths, PDF cache or API is required.
"""
from dataclasses import asdict
from functools import lru_cache
import copy
import hashlib
import json
import io
from PIL import Image, ImageDraw, ImageChops
import pymupdf
from pathlib import Path
import pytest
from cps.services.reflow import extract, skeleton

pytestmark=pytest.mark.unit
FIXTURE=Path(__file__).parents[1]/'fixtures/reflow/physical_footer_families.json'

@lru_cache()
def data():return json.loads(FIXTURE.read_text())

def raw_page(values):
    d=copy.deepcopy(values);blocks=[]
    for b in d.pop('blocks'):
        lines=[]
        for l in b.pop('lines'):
            spans=[extract.Span(**dict(s,bbox=tuple(s['bbox']))) for s in l.pop('spans')]
            lines.append(extract.Line(**dict(l,spans=spans,bbox=tuple(l['bbox']))))
        blocks.append(extract.Block(**dict(b,lines=lines,bbox=tuple(b['bbox']))))
    images=[extract.Image(**dict(i,bbox=tuple(i['bbox']))) for i in d.pop('images')]
    return extract.RawPage(**dict(d,blocks=blocks,images=images))

def inputs(case):
    source=data()['books'][str(case['book'])]
    context=[raw_page(p) for p in source['raw_pages']]
    raw=next(p for p in context if p.pno==case['page'])
    # General source peer learning sees genuine whole pages, not hand-authored
    # learned role objects. The expected roles remain the independent oracle.
    learned=skeleton.book_style(context,outline=source['legacy_book_style']['outline'])
    values=copy.deepcopy(source['legacy_book_style'])
    for key in ('folio_boxes','local_running_boxes','repeated_head_boxes','portrait_head_boxes','scan_spread_head_boxes','scan_table_label_boxes','scan_note_lane_boxes'):
        values[key]={int(p):[tuple(b) for b in boxes] for p,boxes in values[key].items()}
    style=skeleton.BookStyle(**values)
    if hasattr(style,'scan_note_footer_profiles'):
        style.scan_note_footer_profiles=learned.scan_note_footer_profiles
    rows=[raw.blocks[r['block_index']].lines[r['line_index']] for r in case.get('target_rows',[])]
    for expected,row in zip(case.get('target_rows',[]),rows):
        encoded=json.dumps(asdict(row),sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
        assert hashlib.sha256(encoded).hexdigest()==expected['source_row_sha256']
    return raw,style,rows

def source_pixel_page(raw,case,variant=None):
    """Recreate the original upright page solely from pinned unmasked pixels."""
    record=data()['books'][str(case['book'])].get('source_pixels',{}).get(str(raw.pno))
    if record is None:return None
    path=FIXTURE.parent/record['path'];pixels=path.read_bytes()
    assert hashlib.sha256(pixels).hexdigest()==record['sha256']
    assert raw.source_geometry==record['source_geometry'] and record['unmasked']
    image=Image.open(io.BytesIO(pixels)).convert('RGB')
    assert image.size==(record['pixel_width'],record['pixel_height'])
    placement=record.get('source_image_reading_bbox',[0,0,raw.width,raw.height])
    if variant:
        # Modify only the physically observed rule; surrounding original glyphs
        # stay intact. These are boundary counterfactuals, not source positives.
        bounds={25:(451,418,589,426),28:(103,500,241,509)}[raw.pno]
        sx,sy=image.width/(placement[2]-placement[0]),image.height/(placement[3]-placement[1])
        box=tuple(round((v-placement[i%2])*(sx if i%2==0 else sy)) for i,v in enumerate(bounds))
        tile=image.crop(box);ImageDraw.Draw(image).rectangle((box[0],box[1],box[2]-1,box[3]-1),fill='white')
        if variant=='shifted':image.paste(tile,(box[0]+round(style_body_size(case)*8*sx),box[1]))
        elif variant=='thick':
            # Retain real stroke shape and expand it vertically beyond .2em.
            canvas=Image.new('RGB',image.size,'white')
            for dy in range(-round(sy*3),round(sy*3)+1):
                shifted=Image.new('RGB',image.size,'white');shifted.paste(tile,(box[0],box[1]+dy));canvas=ImageChops.darker(canvas,shifted)
            image=ImageChops.darker(image,canvas)
        else:assert variant=='absent'
        buf=io.BytesIO();image.save(buf,format='PNG');pixels=buf.getvalue()
    doc=pymupdf.open();page=doc.new_page(width=raw.width,height=raw.height)
    page.insert_image(pymupdf.Rect(placement),stream=pixels)
    return doc

def style_body_size(case):return data()['books'][str(case['book'])]['legacy_book_style']['body_size']

def split(raw,style,case=None,pixel_variant=None):
    before=asdict(raw);original=[id(l) for b in raw.blocks for l in b.lines]
    doc=source_pixel_page(raw,case,pixel_variant) if case else None
    try:
        probe=extract.ScanPixelProbe(doc,0) if doc else None
        body,notes=skeleton._split_off_notes(raw,style,skeleton.PageSkeleton(raw.pno,raw.width,raw.height),probe)
    finally:
        if doc:doc.close()
    assert asdict(raw)==before,'Source literal/geometry must remain unchanged'
    delivered=[id(l) for b in body for l in b.lines]+[id(l) for n in notes for l in n.lines]
    assert sorted(original)==sorted(delivered),'Every source row is owned exactly once'
    return body,notes

@pytest.mark.parametrize('case',[c for c in data()['cases'] if c['physically_verified_note']],ids=lambda c:c['name'])
def test_physically_printed_footer_families_are_owned_whole(case):
    raw,style,rows=inputs(case);body,notes=split(raw,style,case)
    assert all(any(row is line for n in notes for line in n.lines) for row in rows),'All independently viewed printed note rows must leave body flow'
    assert not any(row is line for b in body for line in b.lines for row in rows)

@pytest.mark.parametrize('case',[c for c in data()['cases'] if not c['physically_verified_note']],ids=lambda c:c['name'])
def test_actual_authored_body_chart_table_pages_are_not_notes(case):
    raw,style,_=inputs(case);_,notes=split(raw,style,case)
    assert not notes,case['reason']

@pytest.mark.parametrize('boundary',['native','body_type','caption','table','later_body','baseline_without_peers'])
def test_generic_footer_family_keeps_source_boundaries(boundary):
    case=next(c for c in data()['cases'] if c['name']=='printed-note-561-25')
    raw,style,rows=inputs(case)
    # Restrict the mutation to note4; note5 remains an untouched neighbour.
    target=rows[0];block=next(b for b in raw.blocks if any(l is target for l in b.lines))
    if boundary=='native':
        for b in raw.blocks:
            for l in b.lines:
                for s in l.spans:s.font='Times'
        raw.images=[]
    elif boundary=='body_type':
        for s in target.spans:s.size=style.body_size;s.bbox=(s.bbox[0],s.bbox[3]-style.body_size,s.bbox[2],s.bbox[3])
    elif boundary=='caption':target.spans[0].text='Chart 4 '
    elif boundary=='table':style.scan_table_label_boxes[raw.pno]=[block.bbox]
    elif boundary=='later_body':
        line=copy.deepcopy(target)
        for s in line.spans:s.text='ordinary body continuation ';s.size=style.body_size;s.bbox=(s.bbox[0],570,s.bbox[2],578);s.origin_y=578
        line.bbox=(target.bbox[0],570,target.bbox[2],578)
        raw.blocks.append(extract.Block(999,line.bbox,[line]))
    elif boundary=='baseline_without_peers':
        style.scan_note_lane_boxes={}
        if hasattr(style,'scan_note_footer_profiles'):style.scan_note_footer_profiles=[]
        marker=target.spans[0];base=max(s.bbox[3] for s in target.spans[1:]);marker.bbox=(marker.bbox[0],base-4,marker.bbox[2],base);marker.origin_y=base
    body,notes=split(raw,style)
    assert not any(target is l for n in notes for l in n.lines),boundary
    assert any(target is l for b in body for l in b.lines)

def test_raised_reference_at_terminal_body_type_is_not_a_printed_footer():
    case=next(c for c in data()['cases'] if c['name']=='printed-note-561-25')
    raw,style,_=inputs(case)
    target=raw.blocks[10].lines[4]  # Actual body: '...to the nature of'.
    owner=raw.blocks[10]
    assert target.text.rstrip().endswith('to the nature of')
    owner.lines.remove(target)
    x0,y0,x1,y1=target.bbox
    # A clearly raised small reference alone cannot turn the unchanged
    # prose-sized source glyphs into a bibliography/quoted-footer territory.
    target.spans.insert(0,extract.Span('4 ',3.67,'ocr',0,(x0-5,y0-3,x0-3,y0-0.36),origin_y=y0-0.36))
    target.bbox=(x0-5,y0-3,x1,y1)
    raw.blocks.append(extract.Block(998,target.bbox,[target]))
    body,notes=split(raw,style)
    assert not any(target is l for n in notes for l in n.lines)
    assert any(target is l for b in body for l in b.lines)


@pytest.mark.parametrize('page',[25,28])
@pytest.mark.parametrize('boundary',['absent','shifted','thick','caption','table','body_type','later_body'])
def test_actual_short_source_rules_keep_ink_and_semantic_boundaries(page,boundary):
    case=next(c for c in data()['cases'] if c['book']==566 and c['page']==page)
    raw,style,rows=inputs(case);target=rows[0]
    block=next(b for b in raw.blocks if any(l is target for l in b.lines))
    variant=boundary if boundary in {'absent','shifted','thick'} else None
    if boundary=='caption':target.spans[0].text='Chart 7 '
    elif boundary=='table':style.scan_table_label_boxes[raw.pno]=[block.bbox]
    elif boundary=='body_type':
        for line in block.lines:
            for span in line.spans:
                span.size=style.body_size;span.bbox=(span.bbox[0],span.bbox[3]-style.body_size,span.bbox[2],span.bbox[3])
    elif boundary=='later_body':
        line=copy.deepcopy(target);y=max(l.bbox[3] for b in raw.blocks for l in b.lines)+5
        for span in line.spans:span.text='ordinary later body prose ';span.size=style.body_size;span.bbox=(span.bbox[0],y,span.bbox[2],y+style.body_size);span.origin_y=y+style.body_size
        line.bbox=(target.bbox[0],y,target.bbox[2],y+style.body_size)
        raw.blocks.append(extract.Block(999,line.bbox,[line]))
    body,notes=split(raw,style,case,variant)
    assert not any(target is l for note in notes for l in note.lines),boundary
    assert any(target is l for b in body for l in b.lines)


@pytest.mark.parametrize('boundary',['body_type','caption','nonterminal','table','no_raised','unproved_anchor'])
def test_crossblock_font_outlier_note_keeps_real_source_boundaries(boundary):
    case=next(c for c in data()['cases'] if c['name']=='printed-note-566-26-crossblock-fontoutlier')
    raw,style,rows=inputs(case);target=rows[0]
    block=next(b for b in raw.blocks if target in b.lines)
    if boundary=='body_type':
        for span in target.spans[1:]:
            span.size=style.body_size;span.bbox=(span.bbox[0],span.bbox[3]-style.body_size,span.bbox[2],span.bbox[3])
    elif boundary=='caption':target.spans[0].text='Chart 18 '
    elif boundary=='table':style.scan_table_label_boxes[raw.pno]=[block.bbox]
    elif boundary=='nonterminal':
        line=copy.deepcopy(target);y=max(l.bbox[3] for b in raw.blocks for l in b.lines)+5
        for span in line.spans:span.text='ordinary later body prose ';span.size=style.body_size;span.bbox=(span.bbox[0],y,span.bbox[2],y+style.body_size);span.origin_y=y+style.body_size
        line.bbox=(target.bbox[0],y,target.bbox[2],y+style.body_size);raw.blocks.append(extract.Block(999,line.bbox,[line]))
    elif boundary=='no_raised':
        marker=target.spans[0];base=max(span.bbox[3] for span in target.spans[1:])
        marker.bbox=(marker.bbox[0],base-3.12,marker.bbox[2],base);marker.origin_y=base
    elif boundary=='unproved_anchor':
        for line in rows[1:]:
            for span in line.spans:span.font='Times'
        if hasattr(style,'scan_note_footer_profiles'):style.scan_note_footer_profiles=[]
        style.scan_note_lane_boxes={}
    body,notes=split(raw,style)
    assert not any(target is l for n in notes for l in n.lines),boundary
    assert any(target is l for b in body for l in b.lines)


def test_actual_body_reference_before_separate_small_note_is_not_reclaimed():
    case=next(c for c in data()['cases'] if c['name']=='printed-note-566-26-crossblock-fontoutlier')
    raw,style,rows=inputs(case)
    owner=raw.blocks[5];target=owner.lines[-1]
    assert target.text.startswith('to the overall style of energy')
    x0,y0,x1,y1=target.bbox
    target.spans.insert(0,extract.Span('18 ',4.33,'ocr',0,(x0-5,y0-3,x0-1,y0-.2),origin_y=y0-.2))
    target.bbox=(x0-5,y0-3,x1,y1)
    # The real small note remains separately owned. A raised reference does
    # not supply the absent large clearance above this genuine body row.
    body,notes=split(raw,style)
    assert not any(target is l for n in notes for l in n.lines)
    assert any(target is l for b in body for l in b.lines)
