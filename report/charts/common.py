"""Shared chart helpers: colour ramps and legends."""
from __future__ import annotations

from ..primitives import Rect, Text


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def lerp_color(colors: list, t: float) -> str:
    t = min(max(t, 0.0), 1.0)
    pos = t * (len(colors) - 1)
    i = min(int(pos), len(colors) - 2)
    f = pos - i
    a, b = _hex(colors[i]), _hex(colors[i + 1])
    return "#%02x%02x%02x" % tuple(round(a[k] + (b[k] - a[k]) * f) for k in range(3))


class SegmentedScale:
    """Ladybug-style segmented legend: `segments` colour bins between vmin and vmax."""

    def __init__(self, ramp: list, vmin: float, vmax: float, segments: int):
        self.vmin, self.vmax, self.n = vmin, vmax, segments
        self.colors = [lerp_color(ramp, (i + 0.5) / segments) for i in range(segments)]

    def color(self, v: float) -> str:
        t = (v - self.vmin) / (self.vmax - self.vmin)
        return self.colors[min(max(int(t * self.n), 0), self.n - 1)]

    def labels(self) -> list:
        step = (self.vmax - self.vmin) / self.n
        return [self.vmin + i * step for i in range(self.n + 1)]


def vertical_legend(scale: SegmentedScale, x: float, y: float, w: float, h: float,
                    title: str = "C", label_size: float = 3.6) -> list:
    """Colour bar with highest value on top (as in the reference sheet)."""
    items = [Text(x, y - 1.2, title, label_size)]
    seg = h / scale.n
    for i, col in enumerate(reversed(scale.colors)):
        items.append(Rect(x, y + i * seg, w, seg + 0.02, fill=col))
    for i, v in enumerate(reversed(scale.labels())):
        items.append(Text(x + w + 0.3, y + i * seg + label_size * 0.12, f"{v:.2f}", label_size))
    return items
