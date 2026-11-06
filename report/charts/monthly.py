"""Monthly-per-hour chart: dry bulb band (min-max) + mean line, GHR area on a 2nd axis."""
from __future__ import annotations

import math

from ..primitives import Line, Poly, Rect, Text


def _nice_step(v: float) -> float:
    if v <= 0:
        return 1.0
    e = 10 ** math.floor(math.log10(v))
    for m in (1, 2, 2.5, 5, 10):
        if v <= m * e:
            return m * e
    return 10 * e


def monthly_chart(box: dict, mh: dict, *, colors: dict, labels: dict, temp_range="auto") -> list:
    x0, y0, W, H = box["x"], box["y"], box["w"], box["h"]
    if temp_range == "auto":
        lo = math.floor(min(min(mh[m]["min"]) for m in mh) / 5.0) * 5
        hi = math.ceil(max(max(mh[m]["max"]) for m in mh) / 5.0) * 5
        lo = min(lo, hi - 30)  # keep a similar vertical scale to the reference
    else:
        lo, hi = temp_range
    ndiv = int(round((hi - lo) / 5))
    rmax = max(max(mh[m]["ghr"]) for m in mh)
    rstep = _nice_step(rmax / ndiv)
    rhi = rstep * ndiv

    ty = lambda t: y0 + H - (t - lo) / (hi - lo) * H  # noqa: E731
    ry = lambda r: y0 + H - r / rhi * H  # noqa: E731
    cw = W / 12.0
    hx = lambda m, h: x0 + (m - 1) * cw + (h + 0.5) / 24.0 * cw  # noqa: E731

    items = []
    # grid
    for i in range(ndiv + 1):
        y = y0 + H - i * H / ndiv
        items.append(Line(x0, y, x0 + W, y, stroke=colors["grid_dark"], width=0.08))
    for m in range(13):
        x = x0 + m * cw
        items.append(Line(x, y0, x, y0 + H, stroke=colors["grid_dark"], width=0.08))
        for h in (0, 6, 12, 18):
            if m < 12:
                items.append(Text(x + h / 24.0 * cw, y0 + H + 2.2, labels["hours"][h // 6], 2.4, anchor="middle"))
    items.append(Text(x0 + W, y0 + H + 2.2, labels["hours"][4], 2.4, anchor="middle"))

    for m in range(1, 13):
        d = mh[m]
        top = [(hx(m, h), ty(d["max"][h])) for h in range(24)]
        bot = [(hx(m, h), ty(d["min"][h])) for h in reversed(range(24))]
        items.append(Poly(top + bot, stroke=None, fill=colors["dbt_band"], closed=True))
    for m in range(1, 13):
        d = mh[m]
        base = ry(0)
        pts = [(hx(m, 0), base)] + [(hx(m, h), ry(d["ghr"][h])) for h in range(24)] + [(hx(m, 23), base)]
        items.append(Poly(pts, stroke=None, fill=colors["ghr"], closed=True))
    for m in range(1, 13):
        d = mh[m]
        items.append(Poly([(hx(m, h), ty(d["mean"][h])) for h in range(24)], stroke=colors["dbt_mean"], width=0.15))
    items.append(Rect(x0, y0, W, H, stroke=colors["grid_dark"], width=0.12))

    big = 11.0
    for i in range(ndiv + 1):
        y = y0 + H - i * H / ndiv + big * 0.353 * 0.35
        items.append(Text(x0 - 3.0, y, f"{lo + i * 5:.2f}", big, anchor="end"))
        items.append(Text(x0 + W + 3.0, y, f"{i * rstep:.2f}", big))
    items.append(Text(x0 - 22.0, y0 + H / 2, labels["axis_temp"], big, anchor="middle", rotate=90))
    items.append(Text(x0 + W + 34.5, y0 + H / 2, labels["axis_rad"], big, anchor="middle", rotate=90))
    return items


def monthly_small_multiples(grid: dict, mh: dict, *, colors: dict, months: list, hours: list) -> list:
    """12 small charts (one per month): hourly min-max band + mean, common y scale."""
    lo = math.floor(min(min(mh[m]["min"]) for m in mh) / 5.0) * 5
    hi = math.ceil(max(max(mh[m]["max"]) for m in mh) / 5.0) * 5
    ndiv = 10
    items = []
    for m in range(1, 13):
        c, r = (m - 1) % grid["cols"], (m - 1) // grid["cols"]
        x0 = grid["x"] + c * grid["dx"]
        y0 = grid["y"] + r * grid["dy"]
        W, H = grid["w"], grid["h"]
        ty = lambda t: y0 + H - (t - lo) / (hi - lo) * H  # noqa: E731
        hx = lambda h: x0 + h / 23.0 * W  # noqa: E731
        for i in range(ndiv + 1):
            y = y0 + H - i * H / ndiv
            items.append(Line(x0, y, x0 + W, y, stroke="#9a9a9a", width=0.05, dash=(0.2, 0.4)))
            items.append(Text(x0 - 1.0, y + 0.35, f"{lo + i * (hi - lo) / ndiv:.2f}", 2.4, anchor="end"))
        d = mh[m]
        top = [(hx(h), ty(d["max"][h])) for h in range(24)]
        bot = [(hx(h), ty(d["min"][h])) for h in reversed(range(24))]
        items.append(Poly(top + bot, stroke="#1f2f55", width=0.06, fill=colors["dbt_band"], closed=True))
        items.append(Poly([(hx(h), ty(d["mean"][h])) for h in range(24)], stroke="#1f2f55", width=0.08))
        items.append(Rect(x0, y0, W, H, stroke="#555555", width=0.08))
        for k, lab in enumerate(hours):
            items.append(Text(x0 + k * W / (len(hours) - 1), y0 + H + 1.6, lab, 1.6, anchor="middle"))
        items.append(Text(x0, y0 + H + 4.0, months[m - 1], 2.6))
    return items
