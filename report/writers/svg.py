"""SVG writer: A3 page, millimetre viewBox, fully vector and editable."""
from __future__ import annotations

import base64
import os
from xml.sax.saxutils import escape

from ..primitives import (PT_TO_MM, Circle, Group, Image, Line, Page, Poly, Rect, Text,
                          TextBlock, r2)


def _q(s: str) -> str:
    return escape(s, {'"': "&quot;"})


def _stroke(stroke, width, dash) -> str:
    if not stroke:
        return ' stroke="none"'
    out = f' stroke="{stroke}" stroke-width="{r2(width)}"'
    if dash:
        out += ' stroke-dasharray="' + " ".join(str(r2(d)) for d in dash) + '"'
    return out


def _fill(fill) -> str:
    return f' fill="{fill}"' if fill else ' fill="none"'


class SvgWriter:
    def __init__(self, font_family: str):
        self.font = font_family

    def _font_attr(self) -> str:
        return f'font-family="{_q(self.font)}, Arial, Helvetica, sans-serif"'

    def item(self, it, out: list):
        if isinstance(it, Group):
            extra = ' shape-rendering="crispEdges"' if it.crisp else ""
            gid = f' id="{_q(it.id)}"' if it.id else ""
            out.append(f'<g{gid}{extra}>')
            for sub in it.items:
                self.item(sub, out)
            out.append("</g>")
        elif isinstance(it, Line):
            out.append(f'<line x1="{r2(it.x1)}" y1="{r2(it.y1)}" x2="{r2(it.x2)}" y2="{r2(it.y2)}"'
                       f'{_stroke(it.stroke, it.width, it.dash)}/>')
        elif isinstance(it, Rect):
            out.append(f'<rect x="{r2(it.x)}" y="{r2(it.y)}" width="{r2(it.w)}" height="{r2(it.h)}"'
                       f'{_fill(it.fill)}{_stroke(it.stroke, it.width, it.dash)}/>')
        elif isinstance(it, Circle):
            out.append(f'<circle cx="{r2(it.cx)}" cy="{r2(it.cy)}" r="{r2(it.r)}"'
                       f'{_fill(it.fill)}{_stroke(it.stroke, it.width, it.dash)}/>')
        elif isinstance(it, Poly):
            pts = " ".join(f"{r2(x)},{r2(y)}" for x, y in it.pts)
            tag = "polygon" if it.closed else "polyline"
            out.append(f'<{tag} points="{pts}"{_fill(it.fill)}'
                       f'{_stroke(it.stroke, it.width, it.dash)} stroke-linejoin="round"/>')
        elif isinstance(it, Text):
            fs = r2(it.size * PT_TO_MM)
            tr = f' transform="rotate({r2(-it.rotate)} {r2(it.x)} {r2(it.y)})"' if it.rotate else ""
            rid = f' id="{_q(it.role)}"' if it.role else ""
            out.append(f'<text{rid} x="{r2(it.x)}" y="{r2(it.y)}" font-size="{fs}" fill="{it.color}"'
                       f' text-anchor="{it.anchor}"{tr}>{_q(it.text)}</text>')
        elif isinstance(it, TextBlock):
            fs = r2(it.size * PT_TO_MM)
            rid = f' id="{_q(it.role)}"' if it.role else ""
            out.append(f'<text{rid} font-size="{fs}" fill="{it.color}">')
            for y, ln in it.lines:
                out.append(f'<tspan x="{r2(it.x)}" y="{r2(y)}">{_q(ln)}</tspan>')
            out.append("</text>")
        elif isinstance(it, Image):
            out.append(self._image(it))
        else:
            raise TypeError(type(it))

    def _image(self, it: Image) -> str:
        ext = os.path.splitext(it.path)[1].lower()
        with open(it.path, "rb") as f:
            data = f.read()
        mime = "image/svg+xml" if ext == ".svg" else "image/png"
        b64 = base64.b64encode(data).decode("ascii")
        return (f'<image x="{r2(it.x)}" y="{r2(it.y)}" width="{r2(it.w)}" height="{r2(it.h)}"'
                f' preserveAspectRatio="xMaxYMid meet" href="data:{mime};base64,{b64}"/>')

    def page(self, page: Page) -> str:
        out = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{page.width}mm" height="{page.height}mm"'
            f' viewBox="0 0 {page.width} {page.height}" {self._font_attr()}>',
            f'<rect x="0" y="0" width="{page.width}" height="{page.height}" fill="#ffffff"/>',
        ]
        for it in page.items:
            self.item(it, out)
        out.append("</svg>")
        return "\n".join(out) + "\n"
