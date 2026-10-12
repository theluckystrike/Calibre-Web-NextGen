"""Detached source heads must not enter body flow or eat authored openers.

These are actual rejected6e4 source45/61 rows, independently verified against
physical PDF pixels. The complete local raw context supplies prose/gutter and
recurrent folio evidence; classifier labels never supply the expectations.
"""
import copy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import pytest
from cps.services.reflow import extract, skeleton

pytestmark = pytest.mark.unit
FIXTURE = Path(__file__).parents[1] / 'fixtures/reflow/running_head_source_frame_context.json'
FIXTURE_SHA = '1f9b43f6cd503f43a228829911a1172d833d0d7556f1f2e26717b32d751d2557'
TARGETS = [(45, 'l26'), (61, 'l33')]


def witness():
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == FIXTURE_SHA
    data = json.loads(FIXTURE.read_text())
    raws = []
    for item in copy.deepcopy(data['raw_pages']):
        blocks = []
        for block in item.pop('blocks'):
            lines = [extract.Line(
                [extract.Span(**dict(span, bbox=tuple(span['bbox'])))
                 for span in line['spans']], tuple(line['bbox']),
                spacing_uncertain=line.get('spacing_uncertain', False),
                transcription_uncertain=line.get('transcription_uncertain', False))
                for line in block['lines']]
            blocks.append(extract.Block(block['number'], tuple(block['bbox']),
                                        lines, kind=block['kind']))
        images = [extract.Image(**dict(image, bbox=tuple(image['bbox'])))
                  for image in item.pop('images')]
        raws.append(extract.RawPage(**dict(item, blocks=blocks, images=images)))
    return data, raws


def target(data, raws, page, lid, *, preservation=False):
    key = 'preservation_rows' if preservation else 'target_rows'
    row = next(row for row in data[key] if row['page'] == page and row['id'] == lid)
    raw = next(raw for raw in raws if raw.pno == page)
    literal = ''.join(span['text'] for span in row['source']['spans'])
    matches = [line for block in raw.text_blocks for line in block.lines
               if line.bbox == tuple(row['source']['bbox']) and line.text == literal]
    assert len(matches) == 1
    return raw, matches[0]


def profile(raws):
    before = [asdict(raw) for raw in raws]
    style = skeleton.book_style(raws)
    assert [asdict(raw) for raw in raws] == before, 'Original source evidence changed'
    return style


@pytest.mark.parametrize('page,lid', TARGETS)
def test_actual_detached_head_has_furniture_ownership_before_uncertain_delivery(page, lid):
    data, raws = witness()
    raw, head = target(data, raws, page, lid)
    before = asdict(raw)
    style = profile(raws)
    assert skeleton._furniture_reason(head, raw, style), (
        page, lid, 'Physically proved running head must not enter body prose')
    page_skeleton = skeleton.page_skeleton(raw, style)
    furniture = [region for region in page_skeleton.regions
                 if region.kind == 'furniture' and head in region.lines]
    assert len(furniture) == 1
    assert not any(head in region.lines for region in page_skeleton.regions
                   if region.kind != 'furniture')
    assert asdict(raw) == before


@pytest.mark.parametrize('page,lid', [(44, 'l9'), (61, 'l0'), (61, 'l1'), (45, 'l27')])
def test_authored_openers_and_same_sentence_continuation_are_preserved(page, lid):
    data, raws = witness()
    raw, line = target(data, raws, page, lid, preservation=True)
    assert skeleton._furniture_reason(line, raw, profile(raws)) is None


def move(line, dx=0, dy=0):
    line.bbox = tuple(value + (dx if index % 2 == 0 else dy)
                      for index, value in enumerate(line.bbox))
    for span in line.spans:
        span.bbox = tuple(value + (dx if index % 2 == 0 else dy)
                          for index, value in enumerate(span.bbox))


@pytest.mark.parametrize('boundary', [
    'missing_peers', 'wrong_page', 'body_slot', 'gutter', 'word_height',
    'native', 'missing_source_frame', 'caption', 'reliable_lowercase',
    'body_wrap_overlap', 'table_label',
])
def test_same_title_words_do_not_authorize_unproved_content_loss(boundary):
    data, raws = witness()
    raw, head = target(data, raws, 45, 'l26')
    if boundary == 'missing_peers':
        raws = [raw]
    elif boundary == 'wrong_page':
        raw.pno += 100
    elif boundary == 'body_slot':
        move(head, dy=150)
    elif boundary == 'gutter':
        move(head, dx=-180)
    elif boundary == 'word_height':
        head.bbox = (*head.bbox[:3], head.bbox[1] + 30)
        for span in head.spans:
            span.size = 30
            span.bbox = (*span.bbox[:3], span.bbox[1] + 30)
    elif boundary == 'native':
        for page in raws:
            page.images = []
            page.text_layer_invisible = False
    elif boundary == 'missing_source_frame':
        raw.source_geometry = {}
    elif boundary == 'caption':
        head.spans[0].text = 'Figure 12: '
    elif boundary == 'reliable_lowercase':
        for span in head.spans:
            span.text = span.text.lower()
            span.uncertain = False
            span.transcription_uncertain = False
            span.encoding_unresolved = False
    elif boundary == 'body_wrap_overlap':
        move(head, dy=27)
    style = profile(raws)
    if boundary == 'table_label':
        style.scan_spread_head_boxes = skeleton._repeated_scan_spread_heads(
            raws, table_labels={raw.pno: [head.bbox]})
        style.scan_table_label_boxes.setdefault(raw.pno, []).append(head.bbox)
    assert skeleton._furniture_reason(head, raw, style) is None, boundary
