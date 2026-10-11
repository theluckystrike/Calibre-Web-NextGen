"""Uncertain OCR may change delivery, never an established furniture role."""
from dataclasses import asdict

import pytest

from cps.services.reflow import assemble, build_epub, extract, skeleton

pytestmark = pytest.mark.unit


def source_page(*, reason='running_caps', proven=True, mixed=False):
    # Measured book561 source70: OCR reads printed folio136 as360. Keep the
    # literal layer and its independent small-cap running-head ownership.
    header_box = (37.2, 24.48, 162.72, 33.6)
    header = extract.Line([
        extract.Span('360 ', 10.67, 'ocr', 0, (37.2, 25.92, 48.24, 33.6), uncertain=True),
        extract.Span('THE ', 6.33, 'ocr', 0, (61.44, 26.4, 77.52, 30.96), uncertain=True),
        extract.Span('REAL ', 6.33, 'ocr', 0, (83.52, 25.92, 104.88, 30.48)),
        extract.Span('ASTROLOGY', 7.33, 'ocr', 0, (110.16, 24.48, 162.72, 29.76)),
    ], header_box)
    body_box = (45.6, 343.2, 382.8, 420)
    continuation_box = (45.6, 343.2, 381.12, 358.56)
    continuation = extract.Line([extract.Span(
        'the South Node cluster around it at a maximum distance of only four degrees.',
        11, 'ocr', 0, continuation_box)], continuation_box)
    uncertain_box = (47.28, 402.96, 382.8, 420)
    uncertain = extract.Line([extract.Span(
        'of the enemy. Mars, ruler of the natal seventh, bearing down on the Ascendant,',
        11, 'ocr', 0, uncertain_box, uncertain=True)], uncertain_box)
    head_block = extract.Block(0, header_box, [header])
    body_block = extract.Block(6, body_box, [continuation, uncertain])
    blocks = [extract.Block(0, (37.2, 24.48, 382.8, 420),
                            [header, continuation, uncertain])] if mixed else [head_block, body_block]
    raw = extract.RawPage(70, 841.68, 595.2, blocks,
                          images=[extract.Image((0, 0, 841.68, 595.2), 1)])
    raw.text_layer_invisible = True
    raw.source_geometry = {'space': 'reading', 'orientation': 90,
                           'source_rotation': 0,
                           'page_rect': [0, 0, 595.2, 841.68]}
    sk = skeleton.PageSkeleton(70, raw.width, raw.height, is_scan=True)
    if proven:
        sk.regions.append(skeleton.Region('furniture', lines=[header],
                                          bbox=header_box, reason=reason))
    kept = [(blocks[-1], [continuation, uncertain] if proven else
                        [header, continuation, uncertain])]
    return raw, sk, kept, header, continuation


def test_actual_small_cap_header_has_an_independent_furniture_reason():
    raw, _, _, header, continuation = source_page()
    style = skeleton.BookStyle(body_size=11)
    assert skeleton._furniture_reason(header, raw, style) == 'running_caps'
    assert skeleton._furniture_reason(continuation, raw, style) is None


@pytest.mark.parametrize('reason', [
    'running_caps', 'sequence_folio', 'repeated_scan_spread_head',
    'repeated_running_head', 'margin_folio',
])
def test_all_proven_furniture_survives_uncertain_ocr_without_a_body_crop(reason):
    raw, sk, kept, header, continuation = source_page(reason=reason)
    before = asdict(raw)
    kept, notes = skeleton._preserve_uncertain_ocr_regions(raw, kept, [], sk, None, [])
    assert not kept and not notes, 'uncertain body remains source pixels under the existing policy'
    assert asdict(raw) == before
    furniture = [r for r in sk.regions if r.kind == 'furniture']
    assert len(furniture) == 1 and furniture[0].lines == [header]
    reading = [r for r in sk.regions if r.kind != 'furniture']
    assert not any(header is line for region in reading for line in region.lines)
    assert any(continuation is line for region in reading for line in region.lines)
    assert not any(r.kind == 'figure' and r.bbox[1] < 100 for r in reading)
    book = assemble.assemble([sk], skeleton.BookStyle(body_size=11), [raw])
    assert book.conservation.ok, book.conservation.to_dict()
    assert len(book.furniture) == 1
    assert 'THE REAL ASTROLOGY' not in build_epub.page_fragment(book, 70)


def test_proven_header_in_a_mixed_raw_block_does_not_take_body_into_furniture():
    raw, sk, kept, header, continuation = source_page(mixed=True)
    kept, _ = skeleton._preserve_uncertain_ocr_regions(raw, kept, [], sk, None, [])
    assert not kept
    assert [r.lines for r in sk.regions if r.kind == 'furniture'] == [[header]]
    assert any(continuation is line for r in sk.regions if r.kind == 'artwork' for line in r.lines)
    assert not any(header is line for r in sk.regions if r.kind == 'artwork' for line in r.lines)


def test_unproven_capitalized_uncertain_text_is_not_suppressed_as_furniture():
    raw, sk, kept, header, _ = source_page(proven=False)
    skeleton._preserve_uncertain_ocr_regions(raw, kept, [], sk, None, [])
    assert not any(r.kind == 'furniture' for r in sk.regions)
    assert any(header is line for r in sk.regions if r.kind == 'artwork' for line in r.lines)


def test_a_reason_label_without_furniture_ownership_cannot_hide_source_text():
    raw, sk, kept, header, _ = source_page(proven=False)
    sk.regions.append(skeleton.Region('body', lines=[header], bbox=header.bbox,
                                      reason='running_caps'))
    skeleton._preserve_uncertain_ocr_regions(raw, kept, [], sk, None, [])
    assert any(header is line for r in sk.regions if r.kind == 'artwork' for line in r.lines)
