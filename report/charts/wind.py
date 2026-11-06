"""Wind roses (ladybug WindRose style), wind-direction sector icons and the wind-chill table."""
from __future__ import annotations

import math

from ..primitives import Circle, Line, Poly, Rect, Text
from .sunpath import DIRS16, _compass

BLACK = "#000000"
GREY = "#9a9a9a"


def nice_step(v: float) -> float:
    if v <= 0:
        return 1.0
    e = 10 ** math.floor(math.log10(v))
    for m in (1, 2, 2.5, 5, 10):
        if v <= m * e:
            return m * e
    return 10 * e


def rose_counts(wd: list, ws: list, idx: list, scale, n_dirs: int = 36) -> list:
    """counts[direction_bin][speed_bin] (hours)."""
    width = 360.0 / n_dirs
    counts = [[0] * scale.n for _ in range(n_dirs)]
    for i in idx:
        d = int(((wd[i] + width / 2) % 360) // width)
        t = (ws[i] - scale.vmin) / (scale.vmax - scale.vmin)
        counts[d][min(max(int(t * scale.n), 0), scale.n - 1)] += 1
    return counts


def max_frequency(counts: list) -> int:
    return max((sum(c) for c in counts), default=0)


def _pt(cx, cy, r, az):
    a = math.radians(az)
    return (cx + r * math.sin(a), cy - r * math.cos(a))


def wind_rose(cx: float, cy: float, R: float, counts: list, scale, fmax: float, *,
              ring_labels: bool = False, label_size: float = 2.2) -> list:
    """Stacked petals (low speeds inside) on a compass of radius R. fmax = hours at the outer ring."""
    n_dirs = len(counts)
    width = 360.0 / n_dirs
    r0 = R * 0.035  # calm circle
    step = nice_step(fmax / 5.0) if fmax > 0 else 1
    fmax = max(step, math.ceil(fmax / step) * step) if fmax > 0 else 1
    rr = lambda f: r0 + (R * 0.97 - r0) * f / fmax  # noqa: E731
    items = []
    for k in range(1, int(round(fmax / step)) + 1):
        r = rr(k * step)
        items.append(Circle(cx, cy, r, stroke=GREY, width=0.07, dash=(0.25, 0.5)))
        if ring_labels:
            items.append(Text(cx, cy - r - 0.5, f"{int(k * step)}", label_size, color="#444444", anchor="middle"))
    for d in range(n_dirs):
        x, y = _pt(cx, cy, R, d * width)
        items.append(Line(cx, cy, x, y, stroke=GREY, width=0.06, dash=(0.25, 0.5)))
    items += _compass(cx, cy, R)
    for d, row in enumerate(counts):
        a0, a1 = d * width - width / 2, d * width + width / 2
        cum = 0
        for s, n in enumerate(row):
            if not n:
                continue
            rin, rout = rr(cum), rr(cum + n)
            cum += n
            arc_out = [_pt(cx, cy, rout, a0 + (a1 - a0) * t / 4) for t in range(5)]
            arc_in = [_pt(cx, cy, rin, a1 - (a1 - a0) * t / 4) for t in range(5)]
            items.append(Poly(arc_out + arc_in, stroke=BLACK, width=0.05, fill=scale.colors[s], closed=True))
    items.append(Circle(cx, cy, r0, fill=BLACK))
    return items, int(step)


def sector_icon(cx: float, cy: float, r: float, a0: float, a1: float, color: str, fill: str) -> list:
    """Small compass with the wind sector [a0, a1] (degrees, clockwise from N) highlighted."""
    span = (a1 - a0) % 360 or 360
    pts = [(cx, cy)] + [_pt(cx, cy, r, a0 + span * t / 24) for t in range(25)]
    items = [Poly(pts, stroke=None, fill=fill, closed=True), Circle(cx, cy, r, stroke=color, width=0.15)]
    for i in range(16):
        x, y = _pt(cx, cy, r, i * 22.5)
        items.append(Line(cx, cy, x, y, stroke=color, width=0.06))
    for name, az in (("N", 0), ("E", 90), ("S", 180), ("W", 270)):
        x, y = _pt(cx, cy, r + 1.3, az)
        items.append(Text(x, y + 0.5, name, 3.0, color=color, anchor="middle"))
    return items


WIND_CHILL = [("0,1 m/s", "0ºC"), ("0,3 m/s", "1ºC"), ("0,7 m/s", "2ºC"), ("1 m/s", "3ºC"), ("1,6 m/s", "4ºC"),
              ("2,2 m/s", "5ºC"), ("3 m/s", "6ºC"), ("4,5 m/s", "7ºC"), ("6,5 m/s", "8ºC")]


def wind_table(t: dict, lab: dict) -> list:
    """'Wind speed vs. feeling of temperature reduction' reference table."""
    x0, x1, y0, y1, c0 = t["x0"], t["x1"], t["y0"], t["y1"], t["col0"]
    mid = y0 + (y1 - y0) * 0.36
    items = [Line(x0, y0, x1, y0, width=0.15), Line(x0, mid, x1, mid, width=0.15), Line(x0, y1, x1, y1, width=0.15)]
    items.append(Text(x0 + 4, y0 + 5.3, lab["wind_speed"], 9.0))
    for i, ln in enumerate(lab["feeling"]):
        items.append(Text(x0 + 4, mid + 4.4 + i * 3.9, ln, 9.0))
    colw = (x1 - x0 - c0 - 30) / (len(WIND_CHILL) - 1)
    for i, (v, dt) in enumerate(WIND_CHILL):
        x = x0 + c0 + 30 + i * colw - colw / 2 + 4
        items.append(Text(x, y0 + 5.3, v, 9.0, anchor="middle"))
        items.append(Text(x, mid + 8.3, dt, 9.0, anchor="middle"))
    return items


def speed_legend(scale, x, y, w, h, title="m/s", size=3.4) -> list:
    items = [Text(x, y - 1.5, title, size + 0.6)]
    seg = h / scale.n
    for i, col in enumerate(reversed(scale.colors)):
        items.append(Rect(x, y + i * seg, w, seg + 0.02, fill=col, stroke=BLACK, width=0.04))
    labels = scale.labels()
    for i, v in enumerate(reversed(labels)):
        items.append(Text(x + w + 0.5, y + i * seg + size * 0.12, f"{v:.2f}", size))
    return items


__all__ = ["wind_rose", "rose_counts", "max_frequency", "sector_icon", "wind_table", "speed_legend", "DIRS16"]
