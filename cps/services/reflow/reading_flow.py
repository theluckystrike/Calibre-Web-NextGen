"""Keep generated disclosures and printed notes outside running source prose.

Opaque images have retained-source witnesses for boundary checks only. Those
witnesses never become a claimed transcription or visible replacement text.
"""
import re
from xml.etree import ElementTree as ET
from . import assemble, native_text

END = re.compile(r'[.!?][\"\u201d\u2019\)\]]*\s*$')


def image_witnesses(book):
    result = {}
    counters = {}
    for figure in book.figures:
        pno = figure['pno']; index = counters.get(pno, 0)
        counters[pno] = index+1
        box = figure['bbox']
        rows = [a for a in book.artwork if a['pno'] == pno and
                box[0] <= a['bbox'][0] and box[1] <= a['bbox'][1] and
                a['bbox'][2] <= box[2] and a['bbox'][3] <= box[3]]
        result['images/fig_p%04d_%d.jpg' % (pno, index)] = dict(
            page=pno, text=' '.join(a['text'] for a in rows),
            bbox=list(box), kind=figure.get('found', 'figure'))
    for pno, elements in book.pages.items():
        for element in elements:
            for run in element.runs:
                if run[0] == 'glyph':
                    result[native_text.image_name(run[2])] = dict(
                        page=pno, text=run[1], bbox=run[2]['bbox'],
                        kind='glyph', reason=run[2].get('reason', 'encoding'))
    return result


def projection(node, images):
    """Source-only endpoint witness, including opaque source text atoms."""
    tag = node.tag.rsplit('}', 1)[-1]
    classes = node.get('class', '').split()
    if 'source-glyph-presentation' in classes:
        # The visible ink expansion has a different resource identity. Its
        # sealed canonical sibling supplies the same source word witness.
        original = next((e for e in node.iter() if
                         'source-glyph-original' in e.get('class', '').split()), None)
        image = next((e for e in original.iter() if e.tag.rsplit('}', 1)[-1] == 'img'), None) if original is not None else None
        return (images.get(image.get('src'), {}).get('text', '') if image is not None else '')+(node.tail or '')
    if set(classes).intersection(('source-evidence-notice', 'source-reading-annotation',
                                  'source-glyph-original', 'pdf-return')):
        return node.tail or ''
    if tag == 'img':
        src = node.get('src', '')
        return images.get(src, {}).get('text', '')+(node.tail or '')
    if tag == 'sup' or 'noteref' in classes:
        return node.tail or ''
    return (node.text or '')+''.join(projection(c, images) for c in node)+(node.tail or '')


def finish(chapters, book):
    """Defer disclosures and notes to a completed paragraph.

    Run after admission and source joins, before link binding. Note IDs and
    source-page destinations survive, so existing links bind across chapters.
    """
    from .build_epub import _is_aside
    images = image_witnesses(book)
    pending = []; raster_notes = []; moved = 0; complete = False; note_count = 0
    for chapter in chapters:
        kept = []
        for block in chapter.blocks:
            root = ET.fromstring('<root xmlns:epub="http://www.idpf.org/2007/ops">'+block+'</root>')
            if not len(root):
                kept.append(block); continue
            node = root[0]
            classes = node.get('class', '').split()
            if node.tag.rsplit('}', 1)[-1] == 'aside' and any(
                    e.tag.rsplit('}', 1)[-1] == 'img' for e in node.iter()):
                # Uncertain printed notes retain their pixels in the notes
                # section, never as rasters in the main reading flow. IDs and
                # embedded Return actions remain available to link binding.
                raster_notes.append(block); moved += 1; note_count += 1
                continue
            if 'source-native-returns' in classes:
                # Destination actions stay near their complete passage. Moving
                # them to the note section would break the visible return flow.
                (kept if complete else pending).append(block); moved += 1; continue
            if _is_aside(block) or 'reflow-retained-furniture' in classes:
                (kept if complete else pending).append(block)
                moved += 1; note_count += 1; continue
            if 'source-evidence-notice' in classes:
                (kept if complete else pending).append(block); moved += 1; continue
            # Alternative-reading annotations are generated copy too. Preserve
            # their IDs and inspection links, but never insert them in a word.
            parents = {c: p for p in root.iter() for c in p}
            changed = False
            for child in list(root.iter()):
                if 'source-reading-annotation' not in child.get('class', '').split():
                    continue
                parent = parents[child]; index = list(parent).index(child)
                tail = child.tail or ''; child.tail = None
                parent.remove(child)
                if index:
                    previous = parent[index-1]; previous.tail = (previous.tail or '')+tail
                else:
                    parent.text = (parent.text or '')+tail
                notice = ET.Element('p', {'class': 'source-evidence-notice'})
                notice.append(child)
                pending.append(ET.tostring(notice, encoding='unicode')); moved += 1
                changed = True
            if changed:
                block = ''.join(ET.tostring(c, encoding='unicode') for c in root)
            kept.append(block)
            tag = node.tag.rsplit('}', 1)[-1]
            if tag in ('p', 'blockquote') and 'caption' not in classes:
                # OCR witnesses establish ownership, not the printed sentence
                # boundary. A crop can contain a terminal OCR full stop while
                # its visible last line continues into the next crop.
                opaque_prose = any('source-raster' in e.get('class', '').split()
                                   for e in node.iter())
                complete = not opaque_prose and bool(END.search(projection(node, images).strip()))
                if complete:
                    kept.extend(pending); pending = []
            elif tag != 'span':
                complete = False
        chapter.blocks = kept
    if (pending or raster_notes) and chapters:
        # A label/index can end without sentence punctuation. Its remaining
        # notes have an explicit notes section after the complete body lane,
        # with no invented heading words in the source stream.
        chapters[-1].blocks.append('<section class="source-notes" epub:type="endnotes" '
            'aria-label="Notes and source disclosures">'+''.join(raster_notes+pending)+'</section>')
    return dict(version='source-reading-flow-1', moved_blocks=moved,
                notes_checked=note_count, trailing_disclosures=len(pending),
                raster_notes_in_notes_section=len(raster_notes),
                image_witnesses=images)
