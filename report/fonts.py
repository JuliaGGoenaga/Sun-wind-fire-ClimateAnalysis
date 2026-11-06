"""Font discovery and deterministic text measurement.

The same TrueType file is used to (1) measure and wrap text, (2) embed in the
PDF and (3) name the font in SVG/PPTX, so line breaks are identical everywhere.
"""
from __future__ import annotations

import functools
import glob
import json
import os
import platform

from .primitives import PT_TO_MM

try:  # not needed (nor installed) in the browser build: metrics come from report/font_metrics
    from fontTools.ttLib import TTFont
except ImportError:  # pragma: no cover
    TTFont = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FONT_DIRS = [
    os.path.join(ROOT, "fonts"),
    os.path.expanduser("~/Library/Fonts"),
    "/Library/Fonts",
    "/System/Library/Fonts/Supplemental",
    "/System/Library/Fonts",
    "C:/Windows/Fonts",
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    os.path.expanduser("~/.fonts"),
]

METRICS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "font_metrics")

PREFERRED = ["Arial", "Helvetica Neue", "Roboto", "Inter", "Open Sans", "DejaVu Sans", "Liberation Sans"]


@functools.lru_cache(maxsize=1)
def available_fonts() -> dict:
    """{family: path} for every *regular* TrueType (glyf) font found."""
    found = {}
    if TTFont is None:
        return found
    for d in FONT_DIRS:
        if not os.path.isdir(d):
            continue
        for path in sorted(glob.glob(os.path.join(d, "**", "*.ttf"), recursive=True)):
            try:
                f = TTFont(path, lazy=True, fontNumber=0)
                if "glyf" not in f:
                    continue
                names = f["name"]
                fam = names.getDebugName(16) or names.getDebugName(1)
                sub = (names.getDebugName(17) or names.getDebugName(2) or "").lower()
                f.close()
            except Exception:
                continue
            if not fam or sub not in ("regular", "book", "roman", "normal"):
                continue
            # project fonts/ win over system fonts
            found.setdefault(fam, path)
    return dict(sorted(found.items()))


@functools.lru_cache(maxsize=1)
def metric_families() -> dict:
    """{family: json path} for the bundled width tables (used when no TTF can be read)."""
    out = {}
    if os.path.isdir(METRICS_DIR):
        for path in sorted(glob.glob(os.path.join(METRICS_DIR, "*.json"))):
            out[os.path.basename(path)[:-5].replace("_", " ")] = path
    return out


def font_choices() -> list:
    """Fonts offered in the UI: real TTF files if there are any, else the bundled metrics."""
    return list(available_fonts().keys()) or list(metric_families().keys())


def default_font() -> str:
    fonts = font_choices()
    for name in PREFERRED:
        if name in fonts:
            return name
    return fonts[0] if fonts else "Helvetica"


class Metrics:
    def __init__(self, family: str):
        self.family = family
        self.path = available_fonts().get(family)
        self._adv = {}
        self.upm = 1000
        self.ascent = 0.905
        jpath = metric_families().get(family)
        if not self.path and jpath:
            with open(jpath, encoding="utf-8") as fh:
                data = json.load(fh)
            self.upm = data["upm"]
            self.ascent = data["ascent"] / self.upm
            self._adv = {int(k): v for k, v in data["adv"].items()}
        elif self.path:
            f = TTFont(self.path, lazy=True)
            self.upm = f["head"].unitsPerEm
            cmap = f.getBestCmap()
            hmtx = f["hmtx"].metrics
            self._adv = {cp: hmtx[g][0] for cp, g in cmap.items() if g in hmtx}
            self.ascent = f["hhea"].ascent / self.upm
            f.close()

    def width_mm(self, text: str, size_pt: float) -> float:
        if not self._adv:  # crude fallback
            return len(text) * 0.5 * size_pt * PT_TO_MM
        default = self._adv.get(ord("n"), self.upm // 2)
        units = sum(self._adv.get(ord(c), default) for c in text)
        return units / self.upm * size_pt * PT_TO_MM


@functools.lru_cache(maxsize=16)
def metrics(family: str) -> Metrics:
    return Metrics(family)


def wrap(text: str, width_mm: float, size_pt: float, family: str) -> list:
    m = metrics(family)
    lines = []
    for raw in text.split("\n"):
        words = raw.split(" ")
        cur = ""
        for w in words:
            cand = w if not cur else cur + " " + w
            if m.width_mm(cand, size_pt) <= width_mm or not cur:
                cur = cand
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def layout_block(block, family: str, min_size: float = 7.0):
    """Wrap a TextBlock into its box, shrinking the font if needed (deterministic)."""
    paragraphs = [p.strip() for p in block.text.replace("\r", "").split("\n\n") if p.strip()]
    size = block.size
    while True:
        lh = size * PT_TO_MM * block.leading
        lines, y = [], block.y + size * PT_TO_MM * 0.9
        for i, p in enumerate(paragraphs):
            if i:
                y += lh  # blank line between paragraphs, like the reference
            for ln in wrap(" ".join(p.split()), block.w, size, family):
                lines.append((y, ln))
                y += lh
        bottom = y - lh
        if bottom <= block.y + block.h or size <= min_size:
            break
        size = round(size - 0.25, 2)
    block.size = size
    block.lines = lines
    block.paragraphs = paragraphs
    return block


def system_name() -> str:
    return platform.system()
