"""Printed citations 82RIGHT/83LEFT observed as body rasters in EPUB.js.

Full unmodified source geometry, including the body above and neighbouring
column, tests ownership without interpreting damaged OCR markers as numbers.
"""
from dataclasses import asdict
import json
from pathlib import Path
import pytest
from cps.services.reflow import extract, skeleton

pytestmark = pytest.mark.unit


def witness(page):
    data = json.loads((Path(__file__).parents[1] / f'fixtures/reflow/numbered_scan_footer_{page}.json').read_text())
    d = data['raw']; blocks = []
    for b in d.pop('blocks'):
        lines = [extract.Line([extract.Span(**dict(s, bbox=tuple(s['bbox']))) for s in l['spans']], tuple(l['bbox']), spacing_uncertain=l.get('spacing_uncertain', False), transcription_uncertain=l.get('transcription_uncertain', False)) for l in b['lines']]
        blocks.append(extract.Block(b['number'], tuple(b['bbox']), lines, kind=b['kind']))
    images = [extract.Image(**dict(i, bbox=tuple(i['bbox']))) for i in d.pop('images')]
    raw = extract.RawPage(**dict(d, blocks=blocks, images=images))
    values = data['style']
    for key in ['folio_boxes', 'local_running_boxes', 'repeated_head_boxes', 'portrait_head_boxes', 'scan_spread_head_boxes', 'scan_table_label_boxes', 'scan_note_lane_boxes']:
        values[key] = {int(p): [tuple(box) for box in boxes] for p, boxes in values[key].items()}
    return raw, skeleton.BookStyle(**values)


def target(raw):
    return next(b for b in raw.blocks if b.number == (15 if raw.pno == 82 else 5))


def split(raw, style):
    before = asdict(raw)
    body, notes = skeleton._split_off_notes(raw, style, skeleton.PageSkeleton(raw.pno, raw.width, raw.height))
    assert asdict(raw) == before
    old = [id(l) for b in raw.blocks for l in b.lines]
    new = [id(l) for b in body for l in b.lines] + [id(l) for n in notes for l in n.lines]
    assert sorted(old) == sorted(new)
    return body, notes


@pytest.mark.parametrize('page', [82, 83])
def test_actual_numbered_close_footer_is_owned_whole_not_body_raster(page):
    raw, style = witness(page); block = target(raw)
    body, notes = split(raw, style)
    matches = [n for n in notes if any(l in n.lines for l in block.lines)]
    assert len(matches) == 1, 'Both printed citation rows must leave body flow'
    note = matches[0]
    assert all(l in note.lines for l in block.lines)
    assert note.number is None and note.uncertain
    assert not any(l in b.lines for b in body for l in block.lines)
    assert all(note.bbox[i] <= block.bbox[i] for i in (0, 1))
    assert all(note.bbox[i] >= block.bbox[i] for i in (2, 3))
    if page == 83:
        assert any(l.text.rstrip().endswith('need to invoke') for b in body for l in b.lines)
        assert any(l.text.startswith('plinctary spirits. Che Scriptures') for b in body for l in b.lines)


@pytest.mark.parametrize('page', [82, 83])
@pytest.mark.parametrize('boundary', ['attached', 'baseline_marker', 'large_marker', 'alphabetic_marker', 'degree_marker', 'body_type', 'no_hanging', 'no_tail', 'caption', 'table', 'native'])
def test_tight_footer_requires_source_shape_not_just_a_small_gap(page, boundary):
    raw, style = witness(page); block = target(raw); marker = block.lines[0].spans[0]
    if boundary == 'attached':
        for l in block.lines:
            l.bbox = tuple(v-3 if i in (1, 3) else v for i, v in enumerate(l.bbox))
            for s in l.spans:
                s.bbox = tuple(v-3 if i in (1, 3) else v for i, v in enumerate(s.bbox)); s.origin_y -= 3
        block.bbox = tuple(v-3 if i in (1, 3) else v for i, v in enumerate(block.bbox))
    elif boundary == 'baseline_marker': marker.bbox = tuple(v+5 if i in (1, 3) else v for i, v in enumerate(marker.bbox))
    elif boundary == 'large_marker': marker.size = 11
    elif boundary == 'alphabetic_marker': marker.text = 'a '
    elif boundary == 'degree_marker': marker.text = '° '
    elif boundary == 'body_type':
        for l in block.lines:
            for s in l.spans[1:]: s.size = 11
        # The numerical tail is also prose-size in this counterexample.
        for s in block.lines[-1].spans: s.size = 11
    elif boundary == 'no_hanging':
        l = block.lines[-1]; dx = block.lines[0].spans[1].bbox[0] - l.bbox[0]
        l.bbox = tuple(v+dx if i in (0, 2) else v for i, v in enumerate(l.bbox))
        for s in l.spans: s.bbox = tuple(v+dx if i in (0, 2) else v for i, v in enumerate(s.bbox))
    elif boundary == 'no_tail': block.lines = block.lines[:1]; block.bbox = block.lines[0].bbox
    elif boundary == 'caption': marker.text = 'Chart 7 '
    elif boundary == 'table': style.scan_table_label_boxes[raw.pno] = [block.bbox]
    elif boundary == 'native':
        for l in block.lines:
            for s in l.spans: s.font = 'Times'
    body, notes = split(raw, style)
    assert not any(l in n.lines for n in notes for l in block.lines)
    assert all(any(l in b.lines for b in body) for l in block.lines)


@pytest.mark.parametrize('page,blocks', [(7,[5,6,7]),(48,[5,11]),(63,[6,14]),(66,[11]),(79,[8])])
def test_physically_reviewed_analogous_source_footers_leave_body_whole(page,blocks):
    raw,style=witness(page)
    rows=[l for b in raw.blocks if b.number in blocks for l in b.lines]
    body,notes=split(raw,style)
    assert all(any(l in n.lines for n in notes) for l in rows), 'Every printed source-footnote row belongs to the notes lane'
    assert not any(l in b.lines for b in body for l in rows)


@pytest.mark.parametrize('boundary', ['baseline_marker','large_marker','other_marker_start','other_text_start','body_height','caption','table','native'])
def test_body_sized_adjacent_row_requires_original_raised_footer_alignment(boundary):
    raw,style=witness(7); block=next(b for b in raw.blocks if b.number==6)
    opening=block.lines[0].spans[0]; following=block.lines[0].spans[1]
    if boundary=='baseline_marker': opening.bbox=tuple(v+5 if i in (1,3) else v for i,v in enumerate(opening.bbox))
    elif boundary=='large_marker': opening.size=11
    elif boundary=='other_marker_start': opening.bbox=tuple(v+6 if i in (0,2) else v for i,v in enumerate(opening.bbox))
    elif boundary=='other_text_start': following.bbox=tuple(v+6 if i in (0,2) else v for i,v in enumerate(following.bbox))
    elif boundary=='body_height':
        for s in block.lines[0].spans[1:]: s.bbox=(s.bbox[0],s.bbox[1],s.bbox[2],s.bbox[1]+11)
    elif boundary=='caption': opening.text='Chart 7 '
    elif boundary=='table': style.scan_table_label_boxes[raw.pno]=[block.bbox]
    elif boundary=='native':
        for s in block.lines[0].spans:s.font='Times'
    body,notes=split(raw,style)
    assert all(any(l in b.lines for b in body) for l in block.lines)
    assert not any(l in n.lines for n in notes for l in block.lines)


def other_book_witness():
    # Loader reads the exact full source page and style, never a constructed footer.
    data=json.loads((Path(__file__).parents[1]/'fixtures/reflow/numbered_scan_footer_566_48.json').read_text())
    d=data['raw']; blocks=[]
    for b in d.pop('blocks'):
        lines=[extract.Line([extract.Span(**dict(s,bbox=tuple(s['bbox'])))for s in l['spans']],tuple(l['bbox']),spacing_uncertain=l.get('spacing_uncertain',False),transcription_uncertain=l.get('transcription_uncertain',False))for l in b['lines']]
        blocks.append(extract.Block(b['number'],tuple(b['bbox']),lines,kind=b['kind']))
    images=[extract.Image(**dict(i,bbox=tuple(i['bbox'])))for i in d.pop('images')]
    raw=extract.RawPage(**dict(d,blocks=blocks,images=images));values=data['style']
    for key in ['folio_boxes','local_running_boxes','repeated_head_boxes','portrait_head_boxes','scan_spread_head_boxes','scan_table_label_boxes','scan_note_lane_boxes']:
        values[key]={int(p):[tuple(box)for box in boxes]for p,boxes in values[key].items()}
    return raw,skeleton.BookStyle(**values)


def test_second_book_complete_printed_numeric_footnotes_leave_body():
    raw,style=other_book_witness();block=next(b for b in raw.blocks if b.number==17)
    body,notes=split(raw,style)
    assert all(any(l in n.lines for n in notes)for l in block.lines)
    assert not any(l in b.lines for b in body for l in block.lines)


@pytest.mark.parametrize('boundary',['baseline_marker','almost_baseline_marker','large_marker','degree_marker','alphabetic_marker','no_hanging','body_type','caption','table','native'])
def test_second_book_numbered_footer_still_requires_raised_source_shape(boundary):
    raw,style=other_book_witness();block=next(b for b in raw.blocks if b.number==17);marker=block.lines[0].spans[0]
    if boundary=='baseline_marker':marker.bbox=tuple(v+3 if i in (1,3)else v for i,v in enumerate(marker.bbox))
    elif boundary=='almost_baseline_marker':marker.bbox=tuple(v+.5 if i in (1,3)else v for i,v in enumerate(marker.bbox))
    elif boundary=='large_marker':marker.size=style.body_size
    elif boundary=='degree_marker':marker.text='35° '
    elif boundary=='alphabetic_marker':marker.text='as '
    elif boundary=='no_hanging':
        l=block.lines[1];dx=block.lines[0].spans[1].bbox[0]-l.bbox[0]
        l.bbox=tuple(v+dx if i in (0,2)else v for i,v in enumerate(l.bbox))
        for s in l.spans:s.bbox=tuple(v+dx if i in (0,2)else v for i,v in enumerate(s.bbox))
    elif boundary=='body_type':
        for l in block.lines:
            for s in l.spans[1:]:s.size=style.body_size+1;s.bbox=(s.bbox[0],s.bbox[1],s.bbox[2],s.bbox[1]+style.body_size)
    elif boundary=='caption':marker.text='Chart 35 '
    elif boundary=='table':style.scan_table_label_boxes[raw.pno]=[block.bbox]
    elif boundary=='native':
        for l in block.lines:
            for s in l.spans:s.font='Times'
    body,notes=split(raw,style)
    assert not any(l in n.lines for n in notes for l in block.lines)
    assert all(any(l in b.lines for b in body)for l in block.lines)
