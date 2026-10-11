"""Actual damaged small-cap spread heads, with contrary body/table controls."""
from dataclasses import asdict, replace
import copy
import pytest
from cps.services.reflow import extract, skeleton
pytestmark=pytest.mark.unit
HEADS={62: {'bbox': [672.4799999999999, 20.4, 782.4, 24.72],
      'spacing_uncertain': False,
      'spans': [{'bbox': [672.4799999999999, 20.639999999999997, 697.4399999999999, 24.72],
                 'char_boxes': [],
                 'encoding_unresolved': False,
                 'flags': 0,
                 'font': 'ocr',
                 'origin_y': 24.72,
                 'punctuation_uncertain': False,
                 'size': 5.67,
                 'text': 'NATAL ',
                 'transcription_uncertain': False,
                 'uncertain': True},
                {'bbox': [705.12, 20.4, 757.2, 24.72],
                 'char_boxes': [],
                 'encoding_unresolved': False,
                 'flags': 0,
                 'font': 'ocr',
                 'origin_y': 24.72,
                 'punctuation_uncertain': False,
                 'size': 6.0,
                 'text': 'ASTROLOGY ',
                 'transcription_uncertain': False,
                 'uncertain': True},
                {'bbox': [773.28, 20.4, 782.4, 24.479999999999997],
                 'char_boxes': [],
                 'encoding_unresolved': False,
                 'flags': 0,
                 'font': 'ocr',
                 'origin_y': 24.479999999999997,
                 'punctuation_uncertain': False,
                 'size': 5.67,
                 'text': 'Il',
                 'transcription_uncertain': False,
                 'uncertain': True}],
      'transcription_uncertain': False},
 69: {'bbox': [52.559999999999995, 18.959999999999997, 780.24, 24.96],
      'spacing_uncertain': False,
      'spans': [{'bbox': [52.559999999999995, 18.959999999999997, 62.63999999999999, 24.72],
                 'char_boxes': [],
                 'encoding_unresolved': False,
                 'flags': 0,
                 'font': 'ocr',
                 'origin_y': 24.72,
                 'punctuation_uncertain': False,
                 'size': 8.0,
                 'text': 'aa ',
                 'transcription_uncertain': False,
                 'uncertain': True},
                {'bbox': [76.8, 18.959999999999997, 91.92, 23.04],
                 'char_boxes': [],
                 'encoding_unresolved': False,
                 'flags': 0,
                 'font': 'ocr',
                 'origin_y': 23.04,
                 'punctuation_uncertain': False,
                 'size': 5.67,
                 'text': 'PU ',
                 'transcription_uncertain': False,
                 'uncertain': True},
                {'bbox': [98.63999999999999, 18.959999999999997, 117.35999999999999, 23.04],
                 'char_boxes': [],
                 'encoding_unresolved': False,
                 'flags': 0,
                 'font': 'ocr',
                 'origin_y': 23.04,
                 'punctuation_uncertain': False,
                 'size': 5.67,
                 'text': 'REAT ',
                 'transcription_uncertain': False,
                 'uncertain': True},
                {'bbox': [125.27999999999999, 18.959999999999997, 176.88, 23.279999999999998],
                 'char_boxes': [],
                 'encoding_unresolved': False,
                 'flags': 0,
                 'font': 'ocr',
                 'origin_y': 23.279999999999998,
                 'punctuation_uncertain': False,
                 'size': 6.0,
                 'text': 'ASTROLOGY ',
                 'transcription_uncertain': False,
                 'uncertain': True},
                {'bbox': [651.3599999999999, 20.16, 696.4799999999999, 24.48],
                 'char_boxes': [],
                 'encoding_unresolved': False,
                 'flags': 0,
                 'font': 'ocr',
                 'origin_y': 24.48,
                 'punctuation_uncertain': False,
                 'size': 6.0,
                 'text': 'MUNDANE ',
                 'transcription_uncertain': False,
                 'uncertain': False},
                {'bbox': [702.9599999999999, 19.68, 753.8399999999999, 24.24],
                 'char_boxes': [],
                 'encoding_unresolved': False,
                 'flags': 0,
                 'font': 'ocr',
                 'origin_y': 24.24,
                 'punctuation_uncertain': False,
                 'size': 6.33,
                 'text': 'ASEPROLOGY ',
                 'transcription_uncertain': False,
                 'uncertain': True},
                {'bbox': [770.88, 19.68, 780.24, 24.96],
                 'char_boxes': [],
                 'encoding_unresolved': False,
                 'flags': 0,
                 'font': 'ocr',
                 'origin_y': 24.96,
                 'punctuation_uncertain': False,
                 'size': 7.33,
                 'text': '145',
                 'transcription_uncertain': False,
                 'uncertain': True}],
      'transcription_uncertain': False},
 90: {'bbox': [681.3599999999999, 22.56, 811.68, 29.759999999999998],
      'spacing_uncertain': False,
      'spans': [{'bbox': [681.3599999999999, 23.52, 684.7199999999999, 27.36],
                 'char_boxes': [],
                 'encoding_unresolved': False,
                 'flags': 0,
                 'font': 'ocr',
                 'origin_y': 27.36,
                 'punctuation_uncertain': False,
                 'size': 5.33,
                 'text': 'NA ',
                 'transcription_uncertain': False,
                 'uncertain': True},
                {'bbox': [690.7199999999999, 23.52, 716.8799999999999, 27.6],
                 'char_boxes': [],
                 'encoding_unresolved': False,
                 'flags': 0,
                 'font': 'ocr',
                 'origin_y': 27.6,
                 'punctuation_uncertain': False,
                 'size': 5.67,
                 'text': 'GUTDE ',
                 'transcription_uncertain': False,
                 'uncertain': True},
                {'bbox': [726.2399999999999, 22.56, 737.9999999999999, 29.759999999999998],
                 'char_boxes': [],
                 'encoding_unresolved': False,
                 'flags': 0,
                 'font': 'ocr',
                 'origin_y': 29.759999999999998,
                 'punctuation_uncertain': False,
                 'size': 10.0,
                 'text': 'POO ',
                 'transcription_uncertain': False,
                 'uncertain': True},
                {'bbox': [741.5999999999999, 23.759999999999998, 759.5999999999999, 27.839999999999996],
                 'char_boxes': [],
                 'encoding_unresolved': False,
                 'flags': 0,
                 'font': 'ocr',
                 'origin_y': 27.839999999999996,
                 'punctuation_uncertain': False,
                 'size': 5.67,
                 'text': 'PRA ',
                 'transcription_uncertain': False,
                 'uncertain': True},
                {'bbox': [766.3199999999999, 24.0, 784.3199999999999, 28.08],
                 'char_boxes': [],
                 'encoding_unresolved': False,
                 'flags': 0,
                 'font': 'ocr',
                 'origin_y': 28.08,
                 'punctuation_uncertain': False,
                 'size': 5.67,
                 'text': 'Tiek ',
                 'transcription_uncertain': False,
                 'uncertain': True},
                {'bbox': [800.64, 24.479999999999997, 811.68, 28.08],
                 'char_boxes': [],
                 'encoding_unresolved': False,
                 'flags': 0,
                 'font': 'ocr',
                 'origin_y': 28.08,
                 'punctuation_uncertain': False,
                 'size': 5.0,
                 'text': 'Pc',
                 'transcription_uncertain': False,
                 'uncertain': True}],
      'transcription_uncertain': False}}


def fixture(page):
    source=copy.deepcopy(HEADS[page])
    header=extract.Line([extract.Span(**s) for s in source['spans']],tuple(source['bbox']))
    header.transcription_uncertain=source.get('transcription_uncertain',False)
    lines=[header]
    for x in (52.56,448.08):
        for j in range(6):
            y=45+j*17.04;box=(x,y,x+336,y+17.04)
            text=f'Ordinary source prose continues through this physical panel row {j}'
            lines.append(extract.Line([extract.Span(text,12,'OCR',0,box)],box))
    raw=extract.RawPage(page,841.68,595.2,[extract.Block(0,(0,0,841.68,150),lines)],images=[extract.Image((0,0,841.68,595.2),1.0)])
    raw.text_layer_invisible=True
    return raw,header,skeleton.BookStyle(body_size=12)


@pytest.mark.parametrize('page',[62,69,90])
def test_actual_damaged_small_cap_heads_have_an_inspection_role(page):
    raw,header,style=fixture(page);before=asdict(raw)
    assert skeleton._furniture_reason(header,raw,style)=='damaged_scan_running_head'
    assert asdict(raw)==before


@pytest.mark.parametrize('damage',['reliable_lowercase','reliable_token_in_uncertain_line','large_body_type','centered_title','attached_body','table_veto','degree_label','lone_numeral','midpage','crossing_span','one_half_body'])
def test_damaged_cap_proof_does_not_remove_body_or_table_context(damage):
    raw,header,style=fixture(69 if damage in ('crossing_span','one_half_body') else 90)
    if damage=='reliable_lowercase':
        header.spans[-1]=replace(header.spans[-1],text='meaning',uncertain=False,transcription_uncertain=False)
    elif damage=='reliable_token_in_uncertain_line':
        header.transcription_uncertain=True
        header.spans[-1]=replace(header.spans[-1],text='a',uncertain=False,transcription_uncertain=False)
    elif damage=='large_body_type':header.spans=[replace(s,size=15) for s in header.spans]
    elif damage=='centered_title':
        header.bbox=(560,22.56,690.32,29.76)
        header.spans=[replace(s,bbox=(s.bbox[0]-121.36,s.bbox[1],s.bbox[2]-121.36,s.bbox[3])) for s in header.spans]
    elif damage=='attached_body':
        row=raw.blocks[0].lines[-6];row.bbox=(448.08,31,784.08,48.04)
    elif damage=='table_veto':style.scan_table_label_boxes={raw.pno:[header.bbox]}
    elif damage=='degree_label':
        header.spans=[replace(header.spans[0],text='ARIES 30° degrees')]
    elif damage=='lone_numeral':header.spans=[replace(header.spans[0],text='1')]
    elif damage=='midpage':
        header.bbox=tuple(v+150 if i%2 else v for i,v in enumerate(header.bbox))
        header.spans=[replace(s,bbox=tuple(v+150 if i%2 else v for i,v in enumerate(s.bbox)))for s in header.spans]
    elif damage=='crossing_span':
        box=(170,20,660,25);header.spans.append(extract.Span('SOURCE WORDS CROSS THIS GAP',6,'OCR',0,box))
    elif damage=='one_half_body':
        header.spans[-3]=replace(header.spans[-3],text='Ordinary body prose continues',uncertain=False)
    assert skeleton._furniture_reason(header,raw,style) is None,damage
