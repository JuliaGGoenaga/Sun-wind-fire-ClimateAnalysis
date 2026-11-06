"""High-level entry point used by both the CLI and the web app."""
from __future__ import annotations

import io
import zipfile

from .climate import Climate
from .pages import build_pages
from .settings import resolve
from .writers.pdf import PdfWriter
from .writers.pptx import PptxWriter
from .writers.svg import SvgWriter

_CACHE: dict = {}


def load_climate(epw_path: str, sun_exposed: bool = True) -> Climate:
    key = (epw_path, sun_exposed)
    if key not in _CACHE:
        _CACHE.clear()  # keep memory bounded: one climate at a time
        _CACHE[key] = Climate(epw_path, sun_exposed)
    return _CACHE[key]


def render(epw_path: str, settings: dict | None, texts: dict | None):
    probe = load_climate(epw_path)
    s = resolve(settings, probe.city)
    cl = load_climate(epw_path, s["utci_sun_exposed"])
    pages = build_pages(cl, s, texts or {})
    return cl, s, pages


def to_svgs(pages, s) -> list:
    w = SvgWriter(s["font"])
    return [w.page(p) for p in pages]


def to_pdf(pages, s) -> bytes:
    return PdfWriter(s["font"]).write(pages)


def to_pptx(pages, s) -> bytes:
    return PptxWriter(s["font"]).write(pages)


def to_svg_zip(pages, s, stem: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for i, svg in enumerate(to_svgs(pages, s), 1):
            info = zipfile.ZipInfo(f"{stem}_{i}.svg", date_time=(2020, 1, 1, 0, 0, 0))
            z.writestr(info, svg)
    return buf.getvalue()
