"""A completed figure description cannot close a suspended body quotation."""
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from cps.services.reflow import assemble, build_epub, reading_flow

pytestmark = pytest.mark.unit


def parsed(fragment):
    return ET.fromstring('<root xmlns:epub="http://www.idpf.org/2007/ops">' + fragment + '</root>')


def is_disclosure(fragment):
    node = parsed(fragment)[0]
    return (node.tag == 'aside' or
            bool(set(node.get('class', '').split()) & {
                'source-evidence-notice', 'source-check-notice',
                'reflow-retained-furniture', 'source-native-returns'}))


def test_actual_source_quotation_survives_descriptive_figure_detour_without_disclosures():
    fixture = json.loads((Path(__file__).parents[1] / 'fixtures/reflow/source_figure_disclosure_detour.json').read_text())
    blocks = fixture['blocks']
    assert 'planets—signifies' in ''.join(parsed(blocks[0]).itertext())
    assert 'futility and annulment' in ''.join(parsed(blocks[-1]).itertext())
    assert sum(b.startswith('<figure') for b in blocks) == 2
    retained = [b for b in blocks if not is_disclosure(b)]
    moved = [b for b in blocks if is_disclosure(b)]
    chapter = build_epub.Chapter(1, '', blocks=blocks.copy())
    reading_flow.finish([chapter], assemble.Book())
    assert chapter.blocks[:-1] == retained
    section = parsed(chapter.blocks[-1])[0]
    assert section.tag == 'section' and section.get('class') == 'source-notes'
    assert [ET.tostring(c, encoding='unicode') for c in section] == [
        ET.tostring(parsed(b)[0], encoding='unicode') for b in moved]
    assert not any(is_disclosure(b) for b in chapter.blocks[:-1])


@pytest.mark.parametrize('channel', [
    '<p class="source-evidence-notice" id="notice"><a href="original-p0000.xhtml#source">Inspect source</a></p>',
    '<p class="source-check-notice" id="notice"><a href="original-p0000.xhtml#source">Inspect source</a></p>',
    '<aside class="footnote" id="fn_3"><p>3 Printed note.</p><a href="#reference">Return</a></aside>',
    '<aside class="footnote" id="fn_3"><p>3 <img src="images/note.jpg"/></p><a href="#reference">Return</a></aside>',
    '<section class="reflow-retained-furniture" id="folio"><p>Printed running head.</p></section>',
    '<aside class="source-native-returns"><a id="action" href="#reference">Return</a></aside>',
])
@pytest.mark.parametrize('detour', [
    '<p class="caption">An independently complete source description.</p>',
    '<figure><img src="images/chart.jpg"/><figcaption>Printed chart caption.</figcaption></figure>',
])
def test_all_retained_channels_wait_until_body_finishes_even_after_completed_detours(channel, detour):
    opening = '<p id="reference">The author calls this double-</p>'
    ending = '<p><span id="source_return_0001"/>bodied.</p>'
    chapters = [build_epub.Chapter(1, '', blocks=[opening, detour, channel]),
                build_epub.Chapter(2, '', blocks=[ending])]
    reading_flow.finish(chapters, assemble.Book())
    assert chapters[0].blocks == [opening, detour]
    assert chapters[1].blocks[0] == ending
    assert len(chapters[1].blocks) == 2
    section = parsed(chapters[1].blocks[-1])[0]
    assert section.get('class') == 'source-notes'
    assert ET.tostring(section[0], encoding='unicode') == ET.tostring(parsed(channel)[0], encoding='unicode')


@pytest.mark.parametrize('source', [
    '<p>The source says source-evidence-notice in this sentence.</p>',
    '<p>Words<sup class="noteref"><a href="#fn_3">3</a></sup> continue.</p>',
    '<p>con<a class="source-glyph" href="original-p0000.xhtml"><img src="images/glyph.jpg"/></a>junction.</p>',
    '<figure><img src="images/chart.jpg"/><figcaption>Actual source caption.</figcaption></figure>',
    '<p class="caption">Actual printed description.</p>',
])
def test_source_text_images_captions_and_reference_marks_remain_in_body(source):
    chapter = build_epub.Chapter(1, '', blocks=[source])
    reading_flow.finish([chapter], assemble.Book())
    assert chapter.blocks == [source]


def test_inline_annotation_moves_with_identity_without_splitting_source_word():
    body = '<p id="reference">con<span class="source-reading-annotation" id="reading-return-test">Reviewed source <a href="original-p0000.xhtml#source">Inspect source</a></span>junction.</p>'
    following = '<p>The next complete source paragraph.</p>'
    chapter = build_epub.Chapter(1, '', blocks=[body, following])
    reading_flow.finish([chapter], assemble.Book())
    assert ''.join(parsed(chapter.blocks[0]).itertext()) == 'conjunction.'
    assert parsed(chapter.blocks[0])[0].get('id') == 'reference'
    assert chapter.blocks[1] == following
    section = parsed(chapter.blocks[-1])[0]
    assert section.get('class') == 'source-notes'
    annotation = section.find('p/span')
    assert annotation.get('id') == 'reading-return-test'
    assert annotation.find('a').get('href') == 'original-p0000.xhtml#source'


@pytest.mark.parametrize('invalid', [None, 'id', 'class', 'type'])
def test_bound_note_identity_survives_annotation_extraction_and_namespace_serialization(invalid):
    ident = 'layout-p0-' + 'a' * 64 + '-note-a0'
    classes = 'footnote'
    typ = 'footnote'
    if invalid == 'id':
        ident = 'ordinary-source-div'
    elif invalid == 'class':
        classes = 'source-panel'
    elif invalid == 'type':
        typ = 'sidebar'
    note = '<div id="%s" class="%s" epub:type="%s"><p>Printed source note <span class="source-reading-annotation" id="inspection">Inspect <a href="original-p0000.xhtml#source">source</a></span>continues.</p></div>' % (ident, classes, typ)
    body = '<p>The source body is complete.</p>'
    chapter = build_epub.Chapter(1, '', blocks=[body, note])
    reading_flow.finish([chapter], assemble.Book())
    assert chapter.blocks[0] == body
    section = parsed(chapter.blocks[-1])[0]
    assert section.get('class') == 'source-notes'
    if invalid is None:
        assert len(chapter.blocks) == 2
        retained = section.find('div')
    else:
        assert len(chapter.blocks) == 3
        retained = parsed(chapter.blocks[1])[0]
    assert retained.get('id') == ident
    assert ''.join(retained.itertext()) == 'Printed source note continues.'
    annotation = section.find('p/span')
    assert annotation.get('id') == 'inspection'
    assert annotation.find('a').get('href') == 'original-p0000.xhtml#source'
