"""Physical source-role review cannot make an uncertain marker reliable."""
import pytest
from tests.unit.test_reflow_native_note_marker_context_complete import actual_pages, owners

pytestmark = pytest.mark.unit


def test_original_transcription_uncertain_source_marker_does_not_gain_numeric_identity(actual_pages):
    _, rows, result, _, _ = actual_pages[99]
    marker = rows['l40']
    assert marker.spans[0].text == '4' and marker.spans[0].transcription_uncertain
    found = owners(result, marker)
    assert len(found) == 1
    assert found[0].number is None, 'Physical note-role proof does not certify a decoded note identity'
