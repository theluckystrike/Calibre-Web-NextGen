"""Detect detached, broad scan bars; retain the original pixels between trims.

A thin table rule or lettering does not qualify. Full source pages remain
untouched; this projection is only for reading crops with a white gutter.
"""
import io


def scan_borders(image):
    """Return solid border bands separated from content by a white gutter."""
    gray = image.convert('L')
    width, height = gray.size
    if min(width, height) < 120:
        return []
    # A dark printed cover/photo border is content, not a scan-edge defect.
    # Require the white-paper carrier typical of the damaged scan crops.
    histogram = gray.histogram()
    if sum(histogram[245:]) < width*height*.45:
        return []
    result = []
    for axis, rotated in [('x', gray), ('y', gray.transpose(2))]:
        w, h = rotated.size
        mask = rotated.point(lambda value: 255 if value < 60 else 0)
        dark = [mask.crop((x, 0, x+1, h)).histogram()[255] / h for x in range(w)]
        runs = []
        start = None
        for x, value in enumerate(dark + [0]):
            if value >= .80 and start is None:
                start = x
            elif value < .80 and start is not None:
                runs.append((start, x)); start = None
        for left, right in runs:
            # Four-pixel separators in enlarged note/table crops are printed
            # source rules. A detached scan bar must have substantial depth.
            if right-left < max(8, w*.01) or right-left > w*.18:
                continue
            while left > 0 and dark[left-1] > .02:
                left -= 1
            while right < w and dark[right] > .02:
                right += 1
            side = 'low' if right <= w*.25 else 'high' if left >= w*.75 else None
            if side is None:
                continue
            # There must be blank paper toward the content, and no competing
            # ink territory on the outside. This refuses dark artwork edges.
            interior = range(right, min(w, right+int(w*.12))) if side == 'low' else range(left-1, max(-1, left-int(w*.12)), -1)
            gutter = []
            for x in interior:
                if dark[x] <= .004:
                    gutter.append(x)
                    if len(gutter) >= max(4, int(w*.01)):
                        break
                else:
                    gutter = []
            outside = dark[:left] if side == 'low' else dark[right:]
            if len(gutter) < max(4, int(w*.01)) or any(v > .15 for v in outside):
                continue
            cut = max(gutter)+1 if side == 'low' else min(gutter)
            result.append(dict(axis=axis, side=side, band=[left, right], cut=cut,
                               solid_fraction=.80, size=[width, height]))
    return result


def trim_scan_borders(data):
    """Lossless retained rectangle, or the unchanged input when no proof exists."""
    from PIL import Image
    image = Image.open(io.BytesIO(data))
    bands = scan_borders(image)
    if not bands:
        return data, []
    box = [0, 0, image.width, image.height]
    for band in bands:
        axis = 0 if band['axis'] == 'x' else 1
        if band['side'] == 'low':
            box[axis] = max(box[axis], band['cut'])
        else:
            box[axis+2] = min(box[axis+2], band['cut'])
    if box[2] <= box[0] or box[3] <= box[1]:
        return data, []
    output = io.BytesIO()
    image.crop(box).save(output, format='PNG')
    return output.getvalue(), [dict(b, retained_pixel_bbox=box) for b in bands]
