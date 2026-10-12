"""A reliable lowercase word vetoes a same-band title/folio admission.

Keep the original frozen seventeen controls intact. This counterfactual keeps
the actual source45/61 geometry and independent peers, changing only the first
word to reliable lowercase. It is not a claim of an actual book false positive.
"""
import pytest
from pathlib import Path
import runpy
from cps.services.reflow import skeleton

_controls = runpy.run_path(str(Path(__file__).with_name(
    'test_reflow_running_head_source_frame.py')))
witness, target, profile = (_controls[name] for name in ('witness', 'target', 'profile'))

pytestmark = pytest.mark.unit


@pytest.mark.parametrize('page,lid', [(45, 'l26'), (61, 'l33')])
def test_one_reliable_lowercase_word_prevents_furniture_admission(page, lid):
    data, raws = witness()
    raw, head = target(data, raws, page, lid)
    first = head.spans[0]
    first.text = first.text.lower()
    first.uncertain = False
    first.transcription_uncertain = False
    first.encoding_unresolved = False
    assert skeleton._furniture_reason(head, raw, profile(raws)) is None
