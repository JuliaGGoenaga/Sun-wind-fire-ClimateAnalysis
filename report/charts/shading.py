"""Solar protection: fixed shading masks, same method as SunExplore
(https://github.com/JuliaGGoenaga/SunExplore, app.js).

For a façade with outward normal azimuth `o` (window of reference 1.5 x 1.5 m):

* the half of the sky behind the façade is masked (azimuths o+90 .. o+270);
* horizontal overhang of length L: masks every sun whose elevation is above
  atan(H * cos(daz) / L) for daz in [-90, 90]. It is given here as the angle
  alpha measured from the vertical in section, tan(alpha) = L / H;
* vertical fin of depth d on one side: masks a full-height sector of width
  phi = atan(d / W) next to the façade plane, on that side (as seen from
  outside: "right" -> azimuths o-90 .. o-90+phi, "left" -> o+90-phi .. o+90).

The devices are FIXED (layout / web form); the EPW provides the sun hours above
the temperature threshold (all of them, coloured by temperature), and the sheet
reports which share of those hot hours each mask blocks.
"""
from __future__ import annotations

import math

from ..primitives import Circle, Line, Poly, Rect, Text

BLACK = "#000000"
GREY = "#b5b5b5"


def _daz(az: float, fa: float) -> float:
    return (az - fa + 180) % 360 - 180


def vsa(alt: float, daz: float) -> float:
    c = math.cos(math.radians(daz))
    if c <= 1e-9:
        return 90.0
    return math.degrees(math.atan(math.tan(math.radians(alt)) / c))


def key_points(cl) -> list:
    """[(Sun, EPW dry bulb temperature)] for the 21st of each month at every daylight hour."""
    return [(cl.suns[i], cl.dbt[i]) for i in range(cl.n)
            if cl.dts[i].day == 21 and cl.suns[i].altitude > 0]


def _fin_sector(o: float, phi: float, side: str) -> list:
    """[(az_start, az_end)] masked by the fin(s), azimuths clockwise from N."""
    out = []
    if phi <= 0:
        return out
    if side in ("right", "both"):
        out.append((o - 90, o - 90 + phi))
    if side in ("left", "both"):
        out.append((o + 90 - phi, o + 90))
    return out


def is_blocked(alt: float, az: float, dev: dict) -> bool:
    o = dev["facade_az"]
    d = _daz(az, o)
    if abs(d) >= 90:
        return True
    a = dev.get("overhang_deg") or 0
    if a > 0:
        min_elev = math.degrees(math.atan2(math.cos(math.radians(d)), math.tan(math.radians(a))))
        if alt >= min_elev:
            return True
    for a0, a1 in _fin_sector(o, dev.get("fin_deg") or 0, dev.get("fin_side", "right")):
        if (az - a0) % 360 <= (a1 - a0):
            return True
    return False


def evaluate(dev: dict, hot: list) -> dict:
    """Share of the hot sunlit hours hitting the façade that the fixed mask blocks."""
    o = dev["facade_az"]
    on_facade = [(s.altitude, s.azimuth) for s, t in hot if abs(_daz(s.azimuth, o)) < 90]
    blocked = sum(1 for alt, az in on_facade if is_blocked(alt, az, dev))
    out = dict(dev)
    out.update({"hot_hours": len(on_facade),
                "coverage_pct": round(100 * blocked / len(on_facade)) if on_facade else 100})
    return out


# ------------------------------------------------------------------ drawing
def _stereo(cx, cy, R, az, alt):
    r = R * math.tan(math.radians(90 - alt) / 2)
    a = math.radians(az)
    return (cx + r * math.sin(a), cy - r * math.cos(a))


def degree_compass(cx, cy, R, *, alt_labels=True, size=6.0) -> list:
    """Compass with azimuth labels every 30° (as in the reference shading sheet)."""
    items = []
    for alt in range(10, 90, 10):
        r = R * math.tan(math.radians(90 - alt) / 2)
        items.append(Circle(cx, cy, r, stroke=GREY, width=0.06))
        if alt_labels:
            items.append(Text(cx + 0.6, cy - r + 1.0, str(alt), size * 0.45, color="#444444"))
    items += [Circle(cx, cy, R, stroke="#555555", width=0.15),
              Circle(cx, cy, R * 1.035, stroke="#777777", width=0.08),
              Circle(cx, cy, R * 1.06, stroke="#777777", width=0.08)]
    items.append(Line(cx - R, cy, cx + R, cy, stroke=GREY, width=0.06))
    items.append(Line(cx, cy - R, cx, cy + R, stroke=GREY, width=0.06))
    for az in range(0, 360, 30):
        a = math.radians(az)
        x1, y1 = cx + R * 1.035 * math.sin(a), cy - R * 1.035 * math.cos(a)
        x2, y2 = cx + R * 1.06 * math.sin(a), cy - R * 1.06 * math.cos(a)
        items.append(Line(x1, y1, x2, y2, stroke="#777777", width=0.08))
        name = {0: "N", 90: "E", 180: "S", 270: "W"}.get(az, str(az))
        r = R * (1.16 if az % 90 == 0 else 1.13)
        items.append(Text(cx + r * math.sin(a), cy - r * math.cos(a) + size * 0.12, name, size * (0.9 if az % 90 else 1.0),
                          anchor="middle"))
    return items


def sunpath_lines(sp, cx, cy, R, color="#9a9a9a") -> list:
    from ladybug_geometry.geometry2d import Point2D
    from .sunpath import _verts
    o = Point2D(0, 0)
    P = lambda p: (cx + p.x, cy - p.y)  # noqa: E731
    items = [Poly([P(v) for v in _verts(pl)], stroke=color, width=0.09)
             for pl in sp.monthly_day_polyline2d("Stereographic", o, R, divisions=72)]
    items += [Poly([P(v) for v in _verts(pl)], stroke=color, width=0.06)
              for pl in sp.hourly_analemma_polyline2d("Stereographic", o, R, steps_per_month=6)]
    return items


def sun_points(points, cx, cy, R, scale, thr, r=1.0) -> list:
    from ladybug_geometry.geometry2d import Point2D
    items = []
    # cooler points first, hot points on top
    for sun, t in sorted(points, key=lambda p: (p[1] > thr, round(p[1], 3))):
        p = sun.position_2d("Stereographic", Point2D(0, 0), R)
        col = scale.color(t)
        if t <= thr:  # faded, like the reference
            col = _blend(col, "#ffffff", 0.55)
        items.append(Circle(cx + p.x, cy - p.y, r, fill=col))
    return items


def _blend(a, b, t):
    ha = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    hb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(ha, hb))


def mask(cx, cy, R, dev: dict, color: str = BLACK) -> list:
    """Mask polygons in stereographic projection (SunExplore geometry)."""
    o = dev["facade_az"]
    items = []

    def sector(a0, a1, steps=90):
        pts = [(cx, cy)] + [_stereo(cx, cy, R, a0 + (a1 - a0) * k / steps, 0) for k in range(steps + 1)]
        items.append(Poly(pts, stroke=color, width=0.05, fill=color, closed=True))

    sector(o + 90, o + 270, 180)                       # behind the façade
    a = dev.get("overhang_deg") or 0
    if a > 0:                                         # horizontal overhang
        pts = [(cx, cy)]
        for off in range(-90, 91):
            c = max(0.0, math.cos(math.radians(off)))
            min_elev = math.degrees(math.atan2(c, math.tan(math.radians(a))))
            pts.append(_stereo(cx, cy, R, o + off, min_elev))
        items.append(Poly(pts, stroke=color, width=0.05, fill=color, closed=True))
    for a0, a1 in _fin_sector(o, dev.get("fin_deg") or 0, dev.get("fin_side", "right")):
        sector(a0, a1, 30)                            # vertical fin
    return items


def _hatch_block(x, y, w, h) -> list:
    items = [Rect(x, y, w, h, fill="#ffffff", stroke=BLACK, width=0.12)]
    n = 6
    for k in range(1, n):
        yy = y + h * k / n
        items.append(Line(x, yy, x + w, yy, width=0.08))
    return items


def section_diagram(x, y, alpha, size=6.0) -> list:
    """Section: wall with window and an overhang that cuts suns above 90-alpha."""
    H = 22.0
    items = _hatch_block(x - 1.2, y, 2.4, 4.0) + _hatch_block(x - 1.2, y + H - 4.0, 2.4, 4.0)
    items.append(Line(x, y + 4.0, x, y + H - 4.0, width=0.12))
    if alpha:
        d = (H - 8.0) * math.tan(math.radians(alpha))
        tip = (x + d, y + 4.0)
        items += [Line(x, y + 4.0, tip[0], tip[1], width=0.25),
                  Line(x, y + H - 4.0, tip[0], tip[1], width=0.08)]
        r = 5.0
        arc = [(x + r * math.sin(math.radians(a)), y + H - 4.0 - r * math.cos(math.radians(a)))
               for a in range(0, int(alpha) + 1, 2)]
        if len(arc) > 1:
            items.append(Poly(arc, width=0.08))
        items.append(Text(x + 1.0 + r * 0.5, y + H - 4.0 - r - 0.8, f"{alpha:.1f}°", size * 0.5))
    return items


def plan_diagram(x, y, fin_deg, side="right", size=6.0) -> list:
    """Plan (outside is up): window between two jambs; fin on the chosen side with angle phi."""
    W = 30.0
    items = _hatch_block(x, y - 1.2, 4.0, 2.4) + _hatch_block(x + W - 4.0, y - 1.2, 4.0, 2.4)
    items.append(Line(x + 4.0, y, x + W - 4.0, y, width=0.12))
    if fin_deg:
        span = W - 8.0
        depth = min(span * math.tan(math.radians(fin_deg)), 18.0)
        sides = ["right", "left"] if side == "both" else [side]
        for sd in sides:
            # seen from outside: "right" jamb is on the right of the drawing
            fx, ox = (x + W - 4.0, x + 4.0) if sd == "right" else (x + 4.0, x + W - 4.0)
            items += [Line(fx, y, fx, y - depth, width=0.25), Line(fx, y - depth, ox, y, width=0.08)]
            items.append(Text((fx + ox) / 2, y - 1.0, f"{fin_deg:.1f}°", size * 0.5, anchor="middle"))
    return items


def horizontal_legend(scale, x, y, w, h, title, size=8.5) -> list:
    items = [Text(x, y - 1.6, title, size)]
    seg = w / scale.n
    for i, col in enumerate(scale.colors):
        items.append(Rect(x + i * seg, y, seg + 0.02, h, fill=col))
    for i, v in enumerate(scale.labels()):
        items.append(Text(x + i * seg, y + h + 3.4, f"{v:.2f}", size, anchor="start" if i == 0 else "middle"))
    return items
