"""Printed note crops must use their established source coordinate frame.

ROOT-owned fixtures independently project distinctive PDF quadrants. The wrong
frame can have the right dimensions; exact decoded source pixels are the oracle.
Native glyphs on the same page retain their native coordinate convention.
"""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path

from PIL import Image
import pymupdf
import pytest

from cps.services.reflow import assemble, native_text

pytestmark = pytest.mark.unit
FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures/reflow/layout_note_source_frames'
CASES = json.loads((FIXTURES / 'manifest.json').read_text())['cases']


def _api():
    """Optional ROOT-only historical RED probe; normal CI exercises live API."""
    archived = os.environ.get('ROOT_LAYOUT_GLYPH_NATIVE_MODULE')
    if not archived:
        return native_text
    spec = importlib.util.spec_from_file_location('cps.services.reflow.native_text_frame_red', archived)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('case', CASES, ids=[c['name'] for c in CASES])
def test_packaged_note_pixels_respect_reading_frame_without_changing_native_glyphs(case):
    api = _api()
    pdf = FIXTURES / case['pdf']
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == case['pdf_sha256']
    pno = case['page']
    book = assemble.Book(pages={pno: []}, source_inventory={pno: {
        'page': pno, 'source_geometry': case['source_geometry']}})
    targets = {}
    for target in case['targets']:
        if target['kind'] in ('layout_note', 'native_note'):
            note = assemble.Note(None, 'Frozen printed note', pno,
                                 bbox=tuple(target['bbox']),
                                 source_layout=target['kind'] == 'layout_note',
                                 glyph_fallback=target['kind'] == 'native_note')
            book.notes.append(note)
            record = api.note_descriptor(note)
        else:
            record = api.descriptor(pno, target['bbox'], target['size'], target['font'])
            book.pages[pno].append(assemble.Element('p', runs=[['glyph', 'X', record]], pno=pno))
        targets[api.image_name(record)] = target

    class Package:
        def __init__(self):
            self.images = {}
        def image(self, name, data):
            assert name not in self.images
            self.images[name] = data

    package = Package()
    with pymupdf.open(pdf) as doc:
        api.package_glyphs(book, {pno: 'Bound source page'}, doc, package)
    assert set(package.images) == set(targets)
    for name, target in targets.items():
        expected_path = FIXTURES / target['expected_pixels_path']
        assert hashlib.sha256(expected_path.read_bytes()).hexdigest() == target['expected_pixels_sha256']
        expected = Image.open(expected_path).convert('RGB')
        actual = Image.open(io.BytesIO(package.images[name])).convert('RGB')
        assert actual.size == expected.size, (case['name'], target['kind'], actual.size, expected.size)
        assert actual.tobytes() == expected.tobytes(), (case['name'], target['kind'], 'wrong source territory or orientation')
