"""Vector PDF writer (reportlab). Fonts are embedded from the same TTF used for metrics."""
from __future__ import annotations

import io
import os

from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from ..fonts import available_fonts
from ..primitives import Circle, Group, Image, Line, Page, Poly, Rect, Text, TextBlock


def _register(family: str) -> str:
    path = available_fonts().get(family)
    if not path:
        return "Helvetica"
    name = "F_" + "".join(c for c in family if c.isalnum())
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(name, path))
    return name


class PdfWriter:
    def __init__(self, font_family: str, skip_editable: bool = False):
        self.font = _register(font_family)
        self.skip_editable = skip_editable

    def _style(self, c, stroke, width, fill, dash):
        if stroke:
            c.setStrokeColor(HexColor(stroke))
            c.setLineWidth(width * mm)
        c.setDash([d * mm for d in dash] if dash else [])
        if fill:
            c.setFillColor(HexColor(fill))

    def item(self, c, it, H):
        X = lambda x: x * mm  # noqa: E731
        Y = lambda y: (H - y) * mm  # noqa: E731
        if isinstance(it, Group):
            for sub in it.items:
                self.item(c, sub, H)
        elif isinstance(it, Line):
            self._style(c, it.stroke, it.width, None, it.dash)
            c.line(X(it.x1), Y(it.y1), X(it.x2), Y(it.y2))
        elif isinstance(it, Rect):
            self._style(c, it.stroke, it.width, it.fill, it.dash)
            c.rect(X(it.x), Y(it.y + it.h), it.w * mm, it.h * mm,
                   stroke=1 if it.stroke else 0, fill=1 if it.fill else 0)
        elif isinstance(it, Circle):
            self._style(c, it.stroke, it.width, it.fill, it.dash)
            c.circle(X(it.cx), Y(it.cy), it.r * mm, stroke=1 if it.stroke else 0, fill=1 if it.fill else 0)
        elif isinstance(it, Poly):
            if len(it.pts) < 2:
                return
            self._style(c, it.stroke, it.width, it.fill, it.dash)
            c.setLineJoin(1)
            p = c.beginPath()
            p.moveTo(X(it.pts[0][0]), Y(it.pts[0][1]))
            for x, y in it.pts[1:]:
                p.lineTo(X(x), Y(y))
            if it.closed:
                p.close()
            c.drawPath(p, stroke=1 if it.stroke else 0, fill=1 if (it.fill and it.closed) else 0)
        elif isinstance(it, Text):
            if self.skip_editable and it.role:
                return
            c.setFillColor(HexColor(it.color))
            c.setFont(self.font, it.size)
            c.saveState()
            c.translate(X(it.x), Y(it.y))
            if it.rotate:
                c.rotate(it.rotate)
            {"start": c.drawString, "middle": c.drawCentredString, "end": c.drawRightString}[it.anchor](0, 0, it.text)
            c.restoreState()
        elif isinstance(it, TextBlock):
            if self.skip_editable and it.role:
                return
            c.setFillColor(HexColor(it.color))
            c.setFont(self.font, it.size)
            for y, ln in it.lines:
                c.drawString(X(it.x), Y(y), ln)
        elif isinstance(it, Image):
            if os.path.splitext(it.path)[1].lower() == ".svg":
                from svglib.svglib import svg2rlg  # optional dependency for a vector logo
                from reportlab.graphics import renderPDF
                d = svg2rlg(it.path)
                s = min(it.w * mm / d.width, it.h * mm / d.height)
                d.scale(s, s)
                renderPDF.draw(d, c, X(it.x + it.w) - d.width * s, Y(it.y + it.h))
            else:
                c.drawImage(it.path, X(it.x), Y(it.y + it.h), it.w * mm, it.h * mm,
                            mask="auto", preserveAspectRatio=True, anchor="e")

    def write(self, pages: list, target=None) -> bytes:
        buf = target or io.BytesIO()
        first = pages[0]
        c = canvas.Canvas(buf, pagesize=(first.width * mm, first.height * mm), invariant=1, pageCompression=1)
        c.setTitle("Climate analysis")
        for page in pages:
            for it in page.items:
                self.item(c, it, page.height)
            c.showPage()
        c.save()
        return buf.getvalue() if isinstance(buf, io.BytesIO) else b""
