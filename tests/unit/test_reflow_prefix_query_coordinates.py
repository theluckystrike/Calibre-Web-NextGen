"""Source query crops can report a local pixmap origin after rotation recovery."""
from cps.services.reflow import extract,skeleton
from tests.unit.test_reflow_merged_note_prefix import witness,pixels
import pytest
pytestmark=pytest.mark.unit

class LocalPage:
    def __init__(self,page):self.page=page;self.rect=page.rect
    def get_pixmap(self,*args,**kwargs):
        pix=self.page.get_pixmap(*args,**kwargs)
        pix.set_origin(0,0)
        return pix
class LocalDoc:
    def __init__(self,doc):self.doc=doc
    def __getitem__(self,index):return LocalPage(self.doc[index])


def test_verified_source_prefix_coordinates_survive_local_crop_pixmap_origin():
    raw,style=witness();target=next(b for b in raw.blocks if b.number==15)
    with pixels(raw) as doc:
        proof=extract.ScanPixelProbe(LocalDoc(doc),0).source_raised_prefix(target.lines[0].spans[0].bbox)
    assert proof is not None
    assert 457.5<=proof['prefix_bbox'][0]<=459
    assert 548<=proof['prefix_bbox'][1]<=549
    assert proof['prefix_bbox'][3]<=proof['lexical_bbox'][3]-2


def test_footer_ownership_survives_rotated_query_facade_local_crop_origin():
    raw,style=witness();target=next(b for b in raw.blocks if b.number==15)
    with pixels(raw) as doc:
        body,notes=skeleton._split_off_notes(raw,style,skeleton.PageSkeleton(raw.pno,raw.width,raw.height),extract.ScanPixelProbe(LocalDoc(doc),0))
    assert all(any(l in n.lines for n in notes)for l in target.lines)
    assert not any(l in b.lines for b in body for l in target.lines)
