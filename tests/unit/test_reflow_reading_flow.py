"""Generated copy and printed notes never separate running source words."""
from xml.etree import ElementTree as ET
import pytest
from cps.services.reflow import assemble, build_epub, reading_flow, extract, skeleton

pytestmark = pytest.mark.unit


def test_disclosures_wait_for_completed_prose_across_raster_and_chapter_boundaries():
    book = assemble.Book()
    book.figures = [dict(pno=0, bbox=(0, 0, 200, 20), found='ocr_uncertain_region')]
    book.artwork = [dict(pno=0, bbox=(0, 0, 200, 20), text='municate with everyone.')]
    chapters = [build_epub.Chapter(1, '', blocks=[
        '<p>We cannot com-</p>',
        '<p class="source-evidence-notice">Punctuation uncertain</p>',
        '<aside class="footnote" id="fn_3"><p>3 Printed note.</p></aside>']),
        build_epub.Chapter(2, '', blocks=[
            '<p><span class="source-raster"><img src="images/fig_p0000_0.jpg"/></span></p>',
            '<p>trine to Saturn at</p>',
            '<p class="source-evidence-notice">View original passage</p>',
            '<p>24° Sagittarius.</p>'])]
    audit = reading_flow.finish(chapters, book)
    assert chapters[0].blocks == ['<p>We cannot com-</p>']
    assert chapters[1].blocks[1].endswith('Punctuation uncertain</p>')
    assert chapters[1].blocks[-2:] == ['<p>24° Sagittarius.</p>',
        '<p class="source-evidence-notice">View original passage</p>']
    assert chapters[-1].title == 'Notes and source disclosures'
    assert 'id="fn_3"' in chapters[-1].blocks[1]
    assert audit['notes_section_blocks'] == 1


def test_inline_generated_annotation_preserves_word_adjacency_and_return_target():
    chapter = build_epub.Chapter(1, '', blocks=[
        '<p>con<span class="source-reading-annotation" id="reading-return-test">'
        'Reviewed reading <a href="original-p0000.xhtml">Inspect source</a></span>'
        'junction is complete.</p>'])
    reading_flow.finish([chapter], assemble.Book())
    root = ET.fromstring('<root>'+''.join(chapter.blocks)+'</root>')
    assert ''.join(root[0].itertext()) == 'conjunction is complete.'
    assert root[1].get('class') == 'source-evidence-notice'
    assert root[1].find('span').get('id') == 'reading-return-test'
    assert root[1].find('span/a').get('href') == 'original-p0000.xhtml'


def test_padded_uncertain_footer_image_is_a_note_without_transcribing_its_digit():
    body_box = (48, 516, 384, 539)
    body = extract.Line([extract.Span('the point at which the divine', 11, 'ocr', 0, body_box)], body_box)
    note_box = (56, 553, 288, 562)
    note = extract.Line([
        extract.Span('3 ', 5.33, 'ocr', 0, (56, 553, 60, 557)),
        extract.Span('Taken from Astrology Source CD Rom, 1993-6', 8.67, 'ocr', 0, (61, 553, 288, 562))], note_box)
    crop_box = (53, 550, 292, 566)
    raw = extract.RawPage(0, 840, 600, [extract.Block(0, body_box, [body]), extract.Block(1, note_box, [note])])
    skel = skeleton.PageSkeleton(0, 840, 600, regions=[
        skeleton.Region('body', lines=[body], bbox=body_box),
        skeleton.Region('figure', bbox=crop_box, reason='ocr_uncertain_region'),
        skeleton.Region('artwork', lines=[note], bbox=note_box, reason='ocr_uncertain_region')])
    book = assemble.assemble([skel], skeleton.BookStyle(body_size=11), [raw])
    assert book.source_inventory[0]['assets'][0]['covered_line_ids'] == []
    assert assemble.source_note_context_figures(book, 0) == {1}
    blocks = build_epub.split_blocks(build_epub.page_fragment(book, 0))
    assert any(b.startswith('<aside class="source-note-context">') for b in blocks)
    assert book.conservation.ok and not book.notes
    # The same numbered image within continuing body territory is not a note.
    later_box = (48, 570, 384, 590)
    later = extract.Line([extract.Span('Continuing prose beneath the image.', 11, 'ocr', 0, later_box)], later_box)
    raw.blocks.append(extract.Block(2, later_box, [later]))
    skel.regions.append(skeleton.Region('body', lines=[later], bbox=later_box))
    continuing = assemble.assemble([skel], skeleton.BookStyle(body_size=11), [raw])
    assert assemble.source_note_context_figures(continuing, 0) == set()
