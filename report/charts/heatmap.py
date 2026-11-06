"""Hourly (365 x 24) heatmaps, ladybug HourlyPlot style."""
from __future__ import annotations

from ..climate import MONTH_DAYS, MONTH_START
from ..primitives import Group, Line, Rect, Text


def hourly_heatmap(box: dict, doy: list, hour: list, colors: list, *, months: list, hour_labels: list,
                   grid_color: str, label_size: float, month_size: float, step_hours: int = 6,
                   minor_hours: int = 0, minor_color: str = "#9a9a9a") -> list:
    """colors[i] is a hex colour or None (cell left blank)."""
    x0, y0, W, H = box["x"], box["y"], box["w"], box["h"]
    cw, ch = W / 365.0, H / 24.0
    grid = [[None] * 24 for _ in range(365)]
    for i, c in enumerate(colors):
        grid[doy[i]][hour[i]] = c

    cells = []
    # merge vertical runs of equal colour in each day column -> fewer shapes
    for d in range(365):
        col = grid[d]
        h = 0
        while h < 24:
            c = col[h]
            k = h
            while k + 1 < 24 and col[k + 1] == c:
                k += 1
            if c:
                top = y0 + H - (k + 1) * ch
                cells.append(Rect(x0 + d * cw, top, cw + 0.03, (k - h + 1) * ch + 0.03, fill=c))
            h = k + 1
    # only the cells are pixel-snapped; grid lines stay hairline-thin
    items = [Group("", cells, (x0, y0, W, H), raster=False, crisp=True)]

    if minor_hours:
        for hh in range(minor_hours, 24, minor_hours):
            if hh % step_hours:
                y = y0 + H - hh * ch
                items.append(Line(x0, y, x0 + W, y, stroke=minor_color, width=0.06, dash=(0.3, 0.4)))
    for hh in range(step_hours, 24, step_hours):
        y = y0 + H - hh * ch
        items.append(Line(x0, y, x0 + W, y, stroke=grid_color, width=0.07))
    for m in range(1, 12):
        x = x0 + MONTH_START[m] * cw
        items.append(Line(x, y0, x, y0 + H, stroke=grid_color, width=0.07))
    items.append(Rect(x0, y0, W, H, stroke=grid_color, width=0.12))

    n = len(hour_labels) - 1
    for i, lab in enumerate(hour_labels):
        y = y0 + H - i * H / n + label_size * 0.12
        items.append(Text(x0 - 2.0, y, lab, label_size, anchor="end"))
    for m in range(12):
        x = x0 + (MONTH_START[m] + MONTH_DAYS[m] / 2) * cw
        items.append(Text(x, y0 + H + month_size * 0.353 + 1.6, months[m], month_size, anchor="middle"))
    return items
