"""Scan borders must be distinguishable from source content."""
import io
import pytest
from PIL import Image, ImageDraw
from cps.services.reflow import crop_edges
pytestmark = pytest.mark.unit


def test_scan_bar_trim_keeps_list_pixels_and_refuses_rules_or_connected_artwork():
    image = Image.new('RGB', (824, 362), 'white')
    draw = ImageDraw.Draw(image)
    for y in range(30, 340, 25):
        draw.rectangle((280, y, 440, y+9), fill='black')
    draw.rectangle((710, 8, 775, 354), fill='black')
    source = io.BytesIO(); image.save(source, format='PNG')
    assert len(crop_edges.scan_borders(image)) == 1
    data, trims = crop_edges.trim_scan_borders(source.getvalue())
    retained = Image.open(io.BytesIO(data))
    assert trims and not crop_edges.scan_borders(retained)
    assert retained.tobytes() == image.crop(trims[0]['retained_pixel_bbox']).tobytes()
    assert retained.crop((280, 30, 441, 340)).tobytes() == image.crop((280, 30, 441, 340)).tobytes()
    rule = Image.new('RGB', image.size, 'white')
    ImageDraw.Draw(rule).line((710, 0, 710, 361), fill='black', width=2)
    assert not crop_edges.scan_borders(rule)
    filled = Image.new('RGB', image.size, 'black')
    assert not crop_edges.scan_borders(filled)

