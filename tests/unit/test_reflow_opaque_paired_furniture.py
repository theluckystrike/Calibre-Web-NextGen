"""Actual running heads/folios must not enter opaque or trusted body delivery.

Four original PDF operator pages and the complete retained source/style are
portable. Source views, rather than current converter roles, qualify furniture.
"""
from collections import Counter
from dataclasses import asdict, fields
from pathlib import Path
import copy
import hashlib
import json
import math
import gzip
from functools import lru_cache

import pymupdf
from PIL import Image, ImageDraw
import pytest

from cps.services.reflow import extract, skeleton, transcript_regions
from tests.unit.test_reflow_physical_footer_canonical_delivery import raw_page, digest

pytestmark = pytest.mark.unit
FIXTURE = Path(__file__).parents[1] / 'fixtures/reflow/opaque_paired_furniture_source_context.json'
PAGES = [593, 607, 609, 611]
TARGETS = [(p, line) for p in PAGES for line in ('l0', 'l1')]


def style(values):
    values = copy.deepcopy(values)
    for key, value in values.items():
        if isinstance(value, dict) and all(str(p).isdigit() for p in value):
            values[key] = {int(p): v for p, v in value.items()}
    for key in ('folio_boxes', 'local_running_boxes'):
        values[key] = {p: tuple(box) for p, box in values[key].items()}
    for key in ('repeated_head_boxes', 'portrait_head_boxes', 'scan_spread_head_boxes',
                'scan_table_label_boxes', 'scan_note_lane_boxes'):
        values[key] = {p: [tuple(box) for box in boxes] for p, boxes in values[key].items()}
    accepted = {f.name for f in fields(skeleton.BookStyle)}
    return skeleton.BookStyle(**{k: v for k, v in values.items() if k in accepted})


@lru_cache(maxsize=1)
def learned_peer_heads():
    peer_file = FIXTURE.parent / 'opaque_paired_original_peer_context.json.gz'
    data = json.loads(gzip.decompress(peer_file.read_bytes()))
    originals = {int(p): raw_page(raw) for p, raw in data['raw_pages'].items()}
    extra = json.loads(gzip.decompress((FIXTURE.parent / 'opaque_paired_reliable_peer_supplement.json.gz').read_bytes()))
    assert {p: digest(raw) for p, raw in extra['raw_pages'].items()} == extra['raw_sha256']
    for p, raw in extra['raw_pages'].items():
        if int(p) in originals:
            assert digest(asdict(originals[int(p)])) == digest(raw)
        originals[int(p)] = raw_page(raw)
        data['raw_sha256'][p] = extra['raw_sha256'][p]
    before = {p: asdict(raw) for p, raw in originals.items()}
    assert {str(p): digest(raw) for p, raw in before.items()} == data['raw_sha256']
    learned = skeleton.book_style(list(originals.values()))
    assert {p: asdict(raw) for p, raw in originals.items()} == before
    return learned, before, data['source_pdf_sha256']


def peer_style(values, target_raw):
    """Measure original source peers; retain the original full-book other fields."""
    learned, originals, source_sha = learned_peer_heads()
    assert asdict(target_raw) == originals[target_raw.pno]
    assert source_sha == json.loads(FIXTURE.read_text())['source_pdf']['original_sha256']
    context = style(values)
    # Only original-source head authority is supplemented. All target PDF crops,
    # note profiles, role expectations and zero-loss ink assertions stay intact.
    context.repeated_head_boxes = copy.deepcopy(learned.repeated_head_boxes)
    if hasattr(context, 'paired_margin_head_boxes'):
        context.paired_margin_head_boxes = copy.deepcopy(learned.paired_margin_head_boxes)
    return context


def furniture(region):
    return region.kind == 'furniture' or region.reason == 'source_furniture_context'


@pytest.fixture(scope='module')
def actual_pages():
    data = json.loads(FIXTURE.read_text())
    path = FIXTURE.parent / data['source_pdf']['path']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == data['source_pdf']['sha256']
    measured = {}
    try:
        for page in PAGES:
            record = data['cases'][str(page)]
            raw = raw_page(record['raw'])
            assert digest(asdict(raw)) == record['raw_sha256']
            assert raw.source_geometry == record['source_geometry']
            doc = pymupdf.open(path)
            measured[page] = (raw, None, None, doc, record, {})
            assert list(doc[page].rect) == record['frame'] and doc[page].rotation == record['rotation']
            first = doc[page].get_pixmap(matrix=pymupdf.Matrix(2, 2), colorspace=pymupdf.csGRAY, alpha=False)
            assert hashlib.sha256(first.samples).hexdigest() == record['fullframe_sha256']
            rows = {}
            for witness in record['physical_source_rows']:
                row = raw.blocks[witness['block_index']].lines[witness['line_index']]
                assert digest(asdict(row)) == witness['sha256']
                assert json.loads(json.dumps(asdict(row))) == witness['source']
                rows[witness['line_id']] = row
            original = copy.deepcopy(record['original_provenance'])
            if 'source_pdf_sha256' in original.get('verification', {}):
                assert original['verification']['source_pdf_sha256'] == data['source_pdf']['original_sha256']
                original['verification']['source_pdf_sha256'] = data['source_pdf']['sha256']
            assert original == record['provenance']
            before = asdict(raw)
            context = peer_style(data['book_style'], raw)
            probe = extract.ScanPixelProbe(doc, page,
                mask=[row.bbox for block in raw.text_blocks for row in block.lines])
            candidate = transcript_regions.candidate(raw, copy.deepcopy(record['provenance']),
                doc, context, pixel_probe=probe, layer_trusted=True) if raw.transcript_unverified else None
            result = candidate[0] if candidate else skeleton.page_skeleton(raw, context,
                pixel_probe=probe, layer_trusted=not raw.transcript_unverified)
            opaque = skeleton.opaque_page_regions(raw, context, pixel_probe=probe)
            assert asdict(raw) == before, 'Do not repair recognition or source geometry in place'
            measured[page] = (raw, result.regions, opaque, doc, record, rows)
        yield measured
    finally:
        for _, _, _, doc, _, _ in measured.values():
            doc.close()


@pytest.mark.parametrize('page,line_id', TARGETS)
def test_actual_canonical_path_keeps_both_physical_head_components_outside_body(actual_pages, page, line_id):
    _, regions, _, _, _, rows = actual_pages[page]
    row = rows[line_id]
    owners = [r for r in regions if any(row is line for line in r.lines+r.caption_lines)]
    assert len(owners) == 1 and furniture(owners[0]), (page, line_id, [(r.kind, r.reason) for r in owners])


@pytest.mark.parametrize('page,line_id', TARGETS)
def test_original_header_or_folio_ink_never_belongs_to_an_opaque_body_strip(actual_pages, page, line_id):
    _, _, opaque, doc, _, rows = actual_pages[page]
    bad = []
    for region in opaque:
        if region.kind != 'figure' or furniture(region):
            continue
        common = pymupdf.Rect(region.bbox) & pymupdf.Rect(rows[line_id].bbox)
        if common.is_empty:
            continue
        pix = doc[page].get_pixmap(clip=common, matrix=pymupdf.Matrix(2, 2), colorspace=pymupdf.csGRAY, alpha=False)
        ink = sum(v < 160 for v in pix.samples)
        if ink > 2:
            bad.append((region.reason, ink, list(common)))
    assert not bad, (page, line_id, bad)


@pytest.mark.parametrize('page', PAGES)
def test_both_paths_retain_every_original_source_row_once(actual_pages, page):
    raw, canonical, opaque, _, _, _ = actual_pages[page]
    expected = Counter(digest(asdict(line)) for block in raw.text_blocks for line in block.lines)
    for regions in (canonical, opaque):
        actual = Counter(digest(asdict(line)) for region in regions for line in region.lines+region.caption_lines)
        assert actual == expected, {'missing': expected-actual, 'duplicated': actual-expected}


@pytest.mark.parametrize('page', PAGES)
def test_every_unproved_source_row_remains_outside_furniture_context(actual_pages, page):
    raw, canonical, opaque, _, _, rows = actual_pages[page]
    proved = {id(rows['l0']), id(rows['l1'])}
    for regions in (canonical, opaque):
        for block in raw.text_blocks:
            for line in block.lines:
                if id(line) in proved:
                    continue
                owners = [r for r in regions if any(line is item for item in r.lines+r.caption_lines)]
                assert len(owners) == 1 and not furniture(owners[0]), (page, line.text, [(r.kind, r.reason) for r in owners])


@pytest.mark.parametrize('page', PAGES)
def test_opaque_source_strips_preserve_all_nonfurniture_prose_art_table_note_glyph_ink(actual_pages, page):
    _, _, opaque, doc, record, _ = actual_pages[page]
    pix = doc[page].get_pixmap(matrix=pymupdf.Matrix(2, 2), colorspace=pymupdf.csGRAY, alpha=False)
    source = Image.frombytes('L', (pix.width, pix.height), pix.samples)
    supported = Image.new('L', source.size, 0)
    draw = ImageDraw.Draw(supported)
    for region in opaque:
        if region.kind == 'figure' and not furniture(region):
            b = region.bbox
            draw.rectangle((math.floor(b[0]*2), math.floor(b[1]*2),
                            math.ceil(b[2]*2)-1, math.ceil(b[3]*2)-1), fill=255)
    eligible = Image.new('L', source.size, 255)
    mask = ImageDraw.Draw(eligible)
    for scope in record['furniture_bitmap_scopes']:
        x0, y0, x1, y1 = scope['pixelbox']
        mask.rectangle((x0, y0, x1-1, y1-1), fill=0)
    original, support, outside = source.tobytes(), supported.tobytes(), eligible.tobytes()
    ink = sum(v < 160 and outside[i] > 0 for i, v in enumerate(original))
    conserved = sum(v < 160 and outside[i] > 0 and support[i] > 0 for i, v in enumerate(original))
    assert ink > 100 and conserved == ink, (page, conserved, ink, 'missing dark pixels', ink-conserved)
    assert hashlib.sha256(pix.samples).hexdigest() == record['fullframe_sha256']
    for scope in record['furniture_bitmap_scopes']:
        crop = source.crop(scope['pixelbox'])
        assert list(crop.size) == scope['pixel_size']
        assert hashlib.sha256(crop.tobytes()).hexdigest() == scope['sha256']
        assert sum(v < 160 for v in crop.tobytes()) == scope['dark_pixels'] > 2


@pytest.mark.parametrize('page', PAGES)
def test_uncertain_folio_proof_keeps_original_uncertainty_and_cannot_decode_identity(actual_pages, page):
    raw, _, _, _, record, rows = actual_pages[page]
    original = next(r for r in record['physical_source_rows'] if r['line_id'] == 'l1')
    assert any(s.transcription_uncertain for s in rows['l1'].spans if s.text.strip())
    assert json.loads(json.dumps(asdict(rows['l1']))) == original['source']
    assert json.loads(json.dumps(asdict(raw))) == record['raw']


@pytest.mark.parametrize('boundary', ['standalone_digit', 'authored_title', 'table_label', 'wrong_baseline'])
def test_constructed_unproved_margin_components_are_not_removed_as_one_furniture_group(boundary):
    """Explicit constructed source controls; not independent physical evidence."""
    titlebox = (100, 30, 180, 42)
    digitbox = (350, 30, 368, 42) if boundary != 'wrong_baseline' else (350, 95, 368, 107)
    title = extract.Line([extract.Span('Source title', 12 if boundary == 'authored_title' else 9,
        'ocr', 0, titlebox)], titlebox)
    digit = extract.Line([extract.Span('123', 9, 'ocr', 0, digitbox,
        transcription_uncertain=True)], digitbox)
    bodybox = (40, 150, 400, 165)
    body = extract.Line([extract.Span('The original authored paragraph remains source content.',
        12, 'ocr', 0, bodybox)], bodybox)
    lines = [digit, body] if boundary == 'standalone_digit' else [title, digit, body]
    raw = extract.RawPage(0, 504, 720,
        [extract.Block(i, line.bbox, [line]) for i, line in enumerate(lines)])
    context = skeleton.BookStyle(body_size=12)
    if boundary == 'table_label':
        context.scan_table_label_boxes = {0: [titlebox]}
    before = asdict(raw)
    result = skeleton.opaque_page_regions(raw, context)
    owners = [r for r in result if any(digit is line for line in r.lines)]
    assert len(owners) == 1 and not furniture(owners[0])
    assert asdict(raw) == before
