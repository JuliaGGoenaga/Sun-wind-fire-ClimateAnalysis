"""Sun-path drawings built from ladybug Sunpath geometry.

* stereographic_sunpath: plan view, ladybug 'Stereographic' projection, with
  hourly points filtered by temperature.
* sunpath_view: the 3D sun-path dome seen through an orthographic camera
  (used for the elevated views and for the side 'alzado' views).
"""
from __future__ import annotations

import math

from ladybug_geometry.geometry2d import Point2D
from ladybug_geometry.geometry3d import Point3D

from ..primitives import Circle, Line, Poly, Text

DIRS16 = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
BLACK = "#000000"
GREY = "#8a8a8a"


def _verts(geo):
    if hasattr(geo, "to_polyline"):
        geo = geo.to_polyline(48)
    return list(geo.vertices) if hasattr(geo, "vertices") else [geo.p1, geo.p2]


# --------------------------------------------------------------- stereographic
def stereographic_sunpath(sp, cx: float, cy: float, R: float, points: list, *,
                          point_radius: float = 0.55, altitude_circles: bool = True,
                          key_days: list = (), sun_color: str = "#ffd400", sun_radius: float = 1.85) -> list:
    """points: [(Sun, hex colour)]. Ladybug 2D: +x east, +y north -> page y flipped."""
    P = lambda p: (cx + p.x, cy - p.y)  # noqa: E731
    o = Point2D(0, 0)
    items = []
    # altitude circles (dotted) + labels on the north axis
    for alt in (range(10, 90, 10) if altitude_circles else ()):
        r = R * math.tan(math.radians(90 - alt) / 2)
        items.append(Circle(cx, cy, r, stroke=GREY, width=0.07, dash=(0.15, 0.45)))
        items.append(Text(cx, cy - r - 0.4, str(alt), 2.2, color="#444444", anchor="middle"))
    items += _compass(cx, cy, R)
    for pl in sp.hourly_analemma_polyline2d("Stereographic", o, R, steps_per_month=6):
        items.append(Poly([P(v) for v in _verts(pl)], stroke=BLACK, width=0.09, dash=(0.6, 0.35)))
    arcs = sp.monthly_day_polyline2d("Stereographic", o, R, divisions=72)
    for i, pl in enumerate(arcs):
        dashed = i in (0, len(arcs) - 1)  # the two solstice arcs, as in the reference
        items.append(Poly([P(v) for v in _verts(pl)], stroke=BLACK, width=0.16 if dashed else 0.1,
                          dash=(0.5, 0.3) if dashed else None))
    for sun, col in points:
        x, y = P(sun.position_2d("Stereographic", o, R))
        items.append(Circle(x, y, point_radius, fill=col))
    # key days (solstices / equinox): thick arc + every daylight hour as a yellow sun
    for (m, d) in key_days:
        arc = sp.day_polyline2d(m, d, "Stereographic", o, R, divisions=72)
        if arc is not None:
            items.append(Poly([P(v) for v in _verts(arc)], stroke=BLACK, width=0.3))
    for (m, d) in key_days:
        for h in range(24):
            sun = sp.calculate_sun(m, d, h)
            if sun.altitude > 0:
                x, y = P(sun.position_2d("Stereographic", o, R))
                items.append(Circle(x, y, sun_radius, fill=sun_color))
    return items


def _compass(cx, cy, R) -> list:
    """Horizon circle doubles as the inner edge of the compass band (no separate inner circle)."""
    items = [Circle(cx, cy, R, stroke=BLACK, width=0.25),
             Circle(cx, cy, R * 1.035, stroke=BLACK, width=0.1)]
    for i, name in enumerate(DIRS16):
        a = math.radians(i * 22.5)
        sx, sy = math.sin(a), -math.cos(a)
        if i % 4 == 0:
            items.append(Line(cx + sx * R, cy + sy * R, cx + sx * R * 1.09, cy + sy * R * 1.09,
                              stroke=BLACK, width=0.12))
            r = R * 1.15
            items.append(Text(cx + sx * r, cy + sy * r + 1.0, name, 6.5, anchor="middle"))
        else:
            r = R * 1.075
            items.append(Text(cx + sx * r, cy + sy * r + 0.4, name, 2.4, anchor="middle"))
    return items


def _clip_below(pts: list, y_max: float) -> list:
    """Split a page-space polyline, keeping only the parts with y <= y_max (above the ground line)."""
    out, cur = [], []
    for i, (x, y) in enumerate(pts):
        inside = y <= y_max + 1e-9
        if i:
            px, py = pts[i - 1]
            pin = py <= y_max + 1e-9
            if inside != pin:  # crossing: add the intersection point
                t = (y_max - py) / (y - py)
                cur.append((px + (x - px) * t, y_max))
                if not inside:
                    out.append(cur)
                    cur = []
        if inside:
            cur.append((x, y))
    if cur:
        out.append(cur)
    return [c for c in out if len(c) > 1]


# ------------------------------------------------------------------ 3D views
class OrthoCamera:
    """Orthographic camera. azimuth: where the camera stands (deg clockwise from north)."""

    def __init__(self, azimuth: float, elevation: float, rotate180: bool = False):
        self.k = -1.0 if rotate180 else 1.0
        a, e = math.radians(azimuth), math.radians(elevation)
        # direction from target to camera
        d = (math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e))
        f = (-d[0], -d[1], -d[2])
        up = (0.0, 0.0, 1.0)
        r = (f[1] * up[2] - f[2] * up[1], f[2] * up[0] - f[0] * up[2], f[0] * up[1] - f[1] * up[0])
        n = math.sqrt(sum(c * c for c in r)) or 1.0
        self.r = tuple(c / n for c in r)
        self.u = (self.r[1] * f[2] - self.r[2] * f[1], self.r[2] * f[0] - self.r[0] * f[2],
                  self.r[0] * f[1] - self.r[1] * f[0])
        self.d = d

    def project(self, x, y, z):
        return (self.k * (x * self.r[0] + y * self.r[1] + z * self.r[2]),
                self.k * (x * self.u[0] + y * self.u[1] + z * self.u[2]))


def sunpath_view(sp, cx: float, cy: float, R: float, cam: OrthoCamera, key_days: list, *,
                 sun_color: str, sun_radius: float = 1.8, compass: bool = True, ground: tuple | None = None,
                 lw: float = 0.1) -> list:
    """3D dome of radius R seen by `cam`. (cx, cy) = page position of the dome origin.
    key_days: [(month, day)] whose hourly suns are drawn in `sun_color`.
    ground: (half_width,) draws a horizon line through the origin (side views)."""
    S = lambda x, y, z: (lambda p: (cx + p[0], cy - p[1]))(cam.project(x, y, z))  # noqa: E731
    o = Point3D(0, 0, 0)
    items = []
    if compass:
        for k, w in ((1.0, 0.18), (1.065, 0.1), (1.09, 0.1)):
            pts = [S(R * k * math.sin(math.radians(t)), R * k * math.cos(math.radians(t)), 0) for t in range(0, 361, 4)]
            items.append(Poly(pts, stroke=BLACK, width=w))
        for i, name in enumerate(DIRS16):
            a = math.radians(i * 22.5)
            if i % 4 == 0:
                x1, y1 = S(R * 1.065 * math.sin(a), R * 1.065 * math.cos(a), 0)
                x2, y2 = S(R * 1.14 * math.sin(a), R * 1.14 * math.cos(a), 0)
                items.append(Line(x1, y1, x2, y2, stroke=BLACK, width=0.12))
                tx, ty = S(R * 1.2 * math.sin(a), R * 1.2 * math.cos(a), 0)
                items.append(Text(tx, ty + 1.0, name, 6.5, anchor="middle"))
            else:
                tx, ty = S(R * 1.135 * math.sin(a), R * 1.135 * math.cos(a), 0)
                items.append(Text(tx, ty + 0.4, name, 2.4, anchor="middle"))
    y_ground = None
    if ground:
        gx0, y_ground = S(0, 0, 0)
        items.append(Line(gx0 - ground[0], y_ground, gx0 + ground[0], y_ground, stroke=BLACK, width=0.18))

    def poly(pts, **kw):
        parts = _clip_below(pts, y_ground) if y_ground is not None else [pts]
        for part in parts:
            items.append(Poly(part, **kw))

    for pl in sp.hourly_analemma_polyline3d(o, R, steps_per_month=6):
        poly([S(v.x, v.y, v.z) for v in _verts(pl)], stroke=BLACK, width=lw * 0.8, dash=(0.6, 0.35))
    arcs = sp.monthly_day_arc3d(o, R)
    for i, arc in enumerate(arcs):
        solstice = i in (0, len(arcs) - 1)
        poly([S(v.x, v.y, v.z) for v in _verts(arc)], stroke=BLACK,
             width=lw * 1.6 if solstice else lw, dash=(0.5, 0.3) if solstice and i == len(arcs) - 1 else None)
    for (m, d) in key_days:
        arc = sp.day_arc3d(m, d, o, R)
        if arc is not None:
            poly([S(v.x, v.y, v.z) for v in _verts(arc)], stroke=BLACK, width=lw * 2.2)
    # suns (back-to-front so nearer suns overlap farther ones)
    suns = []
    for (m, d) in key_days:
        for h in range(24):
            sun = sp.calculate_sun(m, d, h)
            if sun.altitude > 0:
                v = sun.sun_vector_reversed
                p = (v.x * R, v.y * R, v.z * R)
                depth = p[0] * cam.d[0] + p[1] * cam.d[1] + p[2] * cam.d[2]
                x, y = S(*p)
                if y_ground is None or y + sun_radius <= y_ground + 0.01:  # never cross the ground line
                    suns.append((round(depth, 6), (x, y)))
    for _, (x, y) in sorted(suns):
        items.append(Circle(x, y, sun_radius, fill=sun_color))
    return items
