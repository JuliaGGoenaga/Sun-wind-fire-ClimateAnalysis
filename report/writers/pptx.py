"""PPTX writer: A3 slides. Each chart is ONE picture (300 dpi, rendered from the
vector PDF so it is identical); titles, header, footer and texts are native,
editable PowerPoint text boxes."""
from __future__ import annotations

import io

import pymupdf
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_CONNECTOR
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Mm, Pt

from ..fonts import metrics
from ..primitives import PT_TO_MM, Group, Image, Line, Text, TextBlock
from .pdf import PdfWriter

DPI = 300


def _rgb(h: str) -> RGBColor:
    return RGBColor.from_string(h.lstrip("#").upper())


class PptxWriter:
    def __init__(self, font_family: str):
        self.family = font_family

    def _textbox(self, slide, x, y, w, h, paragraphs, size, color, align, role):
        tb = slide.shapes.add_textbox(Mm(x), Mm(y), Mm(w), Mm(h))
        tb.name = role or "text"
        tf = tb.text_frame
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.word_wrap = len(paragraphs) > 1 or w > 60
        tf.vertical_anchor = MSO_ANCHOR.TOP
        first = True
        for ptxt in paragraphs:
            p = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            p.alignment = align
            r = p.add_run()
            r.text = ptxt
            r.font.name = self.family
            r.font.size = Pt(size)
            r.font.color.rgb = _rgb(color)
        return tb

    def write(self, pages: list) -> bytes:
        gfx_pdf = PdfWriter(self.family, skip_editable=True).write(pages)
        doc = pymupdf.open(stream=gfx_pdf, filetype="pdf")
        prs = Presentation()
        prs.slide_width = Mm(pages[0].width)
        prs.slide_height = Mm(pages[0].height)
        blank = prs.slide_layouts[6]
        k = 72 / 25.4
        asc = metrics(self.family).ascent
        for pi, page in enumerate(pages):
            slide = prs.slides.add_slide(blank)
            pdf_page = doc[pi]
            for it in page.items:
                if isinstance(it, Group) or isinstance(it, Image):
                    if isinstance(it, Image):
                        bx, by, bw, bh = it.x, it.y, it.w, it.h
                        name = "logo"
                    else:
                        bx, by, bw, bh = it.bbox
                        name = it.id
                    clip = pymupdf.Rect(bx * k, by * k, (bx + bw) * k, (by + bh) * k)
                    pix = pdf_page.get_pixmap(dpi=DPI, clip=clip, alpha=False)
                    pic = slide.shapes.add_picture(io.BytesIO(pix.tobytes("png")), Mm(bx), Mm(by), Mm(bw), Mm(bh))
                    pic.name = name
                elif isinstance(it, Line):
                    ln = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Mm(it.x1), Mm(it.y1), Mm(it.x2), Mm(it.y2))
                    ln.line.color.rgb = _rgb(it.stroke)
                    ln.line.width = Mm(it.width)
                    if it.dash:
                        ln.line.dash_style = MSO_LINE_DASH_STYLE.DASH
                elif isinstance(it, Text):
                    smm = it.size * PT_TO_MM
                    top = it.y - smm * asc
                    w = max(metrics(self.family).width_mm(it.text, it.size) * 1.15 + 2, 10)
                    if it.anchor == "middle":
                        x, al = it.x - w / 2, PP_ALIGN.CENTER
                    elif it.anchor == "end":
                        x, al = it.x - w, PP_ALIGN.RIGHT
                    else:
                        x, al = it.x, PP_ALIGN.LEFT
                    self._textbox(slide, x, top, w, smm * 1.3, [it.text], it.size, it.color, al, it.role)
                elif isinstance(it, TextBlock):
                    smm = it.size * PT_TO_MM
                    tb = self._textbox(slide, it.x, it.y, it.w + 1.0, it.h, it.paragraphs, it.size, it.color,
                                       PP_ALIGN.LEFT, it.role)
                    for p in tb.text_frame.paragraphs:
                        p.line_spacing = Pt(it.size * it.leading)
                        p.space_after = Pt(it.size * it.leading)
        out = io.BytesIO()
        prs.save(out)
        return out.getvalue()
