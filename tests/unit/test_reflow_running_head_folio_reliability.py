"""Disputed numerical folios cannot teach a unique list-panel head template.

The original source61 title and all physical geometry stay unchanged. Only
folio uncertainty flags change across the actual independent peer context.
This is a counterfactual boundary, not an actual book false-positive claim.
"""
from pathlib import Path
import re
import runpy

import pytest
from cps.services.reflow import skeleton

_controls = runpy.run_path(str(Path(__file__).with_name(
    'test_reflow_running_head_source_frame.py')))
pytestmark = pytest.mark.unit


@pytest.mark.parametrize('flags', [
    ('uncertain',), ('transcription_uncertain',), ('encoding_unresolved',),
    ('uncertain', 'transcription_uncertain', 'encoding_unresolved'),
])
def test_unique_margin_head_requires_independently_reliable_numeric_folio_peers(flags):
    data, raws = _controls['witness']()
    raw, head = _controls['target'](data, raws, 61, 'l33')
    marked = 0
    for page in raws:
        for block in page.text_blocks:
            for line in block.lines:
                if line.bbox[3] > page.height * .12:
                    continue
                for span in line.spans:
                    if not re.fullmatch(r'\d{1,3}', span.text.strip()):
                        continue
                    for name in ('uncertain', 'transcription_uncertain', 'encoding_unresolved'):
                        setattr(span, name, name in flags)
                    marked += 1
    assert marked == 43
    assert skeleton._furniture_reason(head, raw, _controls['profile'](raws)) is None
