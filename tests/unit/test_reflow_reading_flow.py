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
    assert 'id="fn_3"' in chapters[1].blocks[2]
    assert audit['notes_checked'] == 1


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


def test_raster_notes_live_in_notes_section_with_their_targets_and_returns():
    note='<aside class="footnote" id="fn_p0355_10"><p>10 <img src="images/note.jpg"/></p><a href="ch001.xhtml#reference">Return</a></aside>'
    chapters=[build_epub.Chapter(1,'',blocks=['<p id="reference">The complete source paragraph.</p>',note,'<p>Next source paragraph.</p>'])]
    audit=reading_flow.finish(chapters,assemble.Book())
    assert chapters[0].blocks[:2]==['<p id="reference">The complete source paragraph.</p>','<p>Next source paragraph.</p>']
    assert 'class="source-notes"' in chapters[0].blocks[-1]
    assert note in chapters[0].blocks[-1]
    assert audit['raster_notes_in_notes_section']==1


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


def test_adjacent_uncertain_footer_notes_allow_padding_overlap_and_damaged_raised_marker():
    body_box=(48,516,384,539)
    body=extract.Line([extract.Span('The unfinished source sentence continues',11,'ocr',0,body_box)],body_box)
    first_box=(56,553,288,562);second_box=(56,564.5,288,574)
    first=extract.Line([extract.Span('* ',4,'ocr',0,(56,553,60,557)),
        extract.Span('Printed source note without terminal punctuation',8,'ocr',0,(61,553,288,562))],first_box)
    second=extract.Line([extract.Span("' ",3,'ocr',0,(56,564.5,60,568)),
        extract.Span('Another printed source note.',8,'ocr',0,(61,564.5,288,574))],second_box)
    raw=extract.RawPage(0,840,600,[extract.Block(i,l.bbox,[l]) for i,l in enumerate([body,first,second])])
    regions=[skeleton.Region('body',lines=[body],bbox=body_box)]
    for line,box in [(first,(53,550,292,566)),(second,(53,562,292,578))]:
        regions.extend([skeleton.Region('figure',bbox=box,reason='ocr_uncertain_region'),
            skeleton.Region('artwork',lines=[line],bbox=line.bbox,reason='ocr_uncertain_region')])
    book=assemble.assemble([skeleton.PageSkeleton(0,840,600,regions=regions)],skeleton.BookStyle(body_size=11),[raw])
    assert assemble.source_note_context_figures(book,0)=={1,2}
    assert book.conservation.ok and not book.notes


def test_known_footer_notes_bound_damaged_intervening_note_without_adopting_its_marker():
    body_box=(48,516,384,539)
    body=extract.Line([extract.Span('The unfinished source sentence continues',11,'ocr',0,body_box)],body_box)
    boxes=[(56,552,288,561),(56,568,288,578),(56,600,288,609)]
    texts=[('9 ',4,'Known opening note.'),(', ',17,'Damaged intervening printed note.'),('17 ',4,'Known closing note.')]
    lines=[extract.Line([extract.Span(mark,size,'ocr',0,box),extract.Span(text,8,'ocr',0,box)],box)
        for box,(mark,size,text) in zip(boxes,texts)]
    raw=extract.RawPage(0,840,620,[extract.Block(i,l.bbox,[l]) for i,l in enumerate([body]+lines)])
    regions=[skeleton.Region('body',lines=[body],bbox=body_box)]
    for i,line in enumerate(lines):
        reason='ocr_uncertain_region' if i==1 else 'ocr_uncertain_note'
        regions.extend([skeleton.Region('figure',bbox=line.bbox,reason=reason),
            skeleton.Region('artwork',lines=[line],bbox=line.bbox,reason=reason)])
    book=assemble.assemble([skeleton.PageSkeleton(0,840,620,regions=regions)],skeleton.BookStyle(body_size=11),[raw])
    assert assemble.source_note_context_figures(book,0)=={1,2,3}
    assert book.conservation.ok and not book.notes
    # One known note does not prove a bounded cluster for the damaged marker.
    book.figures[-1]['found']='ocr_uncertain_region'
    assert 2 not in assemble.source_note_context_figures(book,0)
