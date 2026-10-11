"""Numeric scan tables cannot become narrative running-head template evidence."""
import pytest
from tests.unit.test_reflow_single_word_spread_heads import witness,inspect
pytestmark=pytest.mark.unit

def test_numeric_only_scan_rows_do_not_crash_or_establish_running_titles():
    raw=next(r for r in witness()if r.pno==79)
    for block in raw.text_blocks:
        for line in block.lines:
            for span in line.spans:
                span.text=' '.join('123'for word in span.text.split())+' '
    assert not inspect([raw]).get(79,[])
