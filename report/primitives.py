"""Backend-neutral drawing primitives.

Every chart is built from these objects (units: millimetres, origin top-left,
y pointing down). The SVG, PDF and PPTX writers only know how to draw these,
so the three outputs always share exactly the same geometry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

PT_TO_MM = 25.4 / 72.0


def r2(v: float) -> float:
    """Round coordinates so output is byte-identical between runs."""
    return round(float(v) + 0.0, 2) + 0.0


@dataclass
class Line:
    x1: float
    y1: float
    x2: float
    y2: float
    stroke: str = "#000000"
    width: float = 0.1
    dash: Optional[tuple] = None


@dataclass
class Poly:
    pts: list
    stroke: Optional[str] = "#000000"
    width: float = 0.1
    fill: Optional[str] = None
    dash: Optional[tuple] = None
    closed: bool = False


@dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float
    fill: Optional[str] = None
    stroke: Optional[str] = None
    width: float = 0.1
    dash: Optional[tuple] = None


@dataclass
class Circle:
    cx: float
    cy: float
    r: float
    fill: Optional[str] = None
    stroke: Optional[str] = None
    width: float = 0.1
    dash: Optional[tuple] = None


@dataclass
class Text:
    """Single line of text. (x, y) is the baseline anchor point. size in pt."""
    x: float
    y: float
    text: str
    size: float
    color: str = "#000000"
    anchor: str = "start"  # start | middle | end
    rotate: float = 0.0    # degrees, counter-clockwise
    role: Optional[str] = None  # non-empty => editable text in the PPTX


@dataclass
class TextBlock:
    """Multi-paragraph wrapped text. Lines are pre-computed (see fonts.layout_block)."""
    x: float
    y: float
    w: float
    h: float
    text: str
    size: float
    color: str = "#000000"
    leading: float = 1.16
    role: Optional[str] = None
    lines: list = field(default_factory=list)  # [(baseline_y_mm, str)]
    paragraphs: list = field(default_factory=list)


@dataclass
class Image:
    x: float
    y: float
    w: float
    h: float
    path: str


@dataclass
class Group:
    """A chart. In the PPTX it becomes a single high-resolution picture."""
    id: str
    items: list
    bbox: tuple  # (x, y, w, h)
    raster: bool = True
    crisp: bool = False  # heatmaps: disable anti-aliasing seams in SVG


@dataclass
class Page:
    id: str
    items: list
    width: float = 420.0
    height: float = 297.0
