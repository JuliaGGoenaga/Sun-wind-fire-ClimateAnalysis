"""Composes the A3 sheets from layout JSON + climate data + texts."""
from __future__ import annotations

import math

from .charts import shading as sh
from .charts.common import SegmentedScale, vertical_legend
from .charts.heatmap import hourly_heatmap
from .charts.monthly import monthly_chart, monthly_small_multiples
from .charts.sunpath import OrthoCamera, stereographic_sunpath, sunpath_view
from .charts.wind import max_frequency, rose_counts, sector_icon, speed_legend, wind_rose, wind_table
from .climate import Climate
from .fonts import layout_block
from .primitives import Group, Image, Line, Page, Poly, Rect, Text, TextBlock
from .settings import LABELS, fmt_t, load_layout, logo_path, method_text


def _frame(L: dict, s: dict, title: str, page_key: str) -> list:
    c, h, f = L["colors"], L["header"], L["footer"]
    fs = L["fonts"]["header"]
    items = [
        Text(h["x0"], h["y"], title, fs, color=c["title"], role=f"{page_key}_title"),
        Text(h["x1"], h["y"], s["header_right"], fs, color=c["title"], anchor="end", role=f"{page_key}_header_right"),
        Line(h["x0"], h["rule_y"], h["x1"], h["rule_y"], stroke=c["rule"], width=0.15, dash=(2.2, 1.6)),
        Line(f["x0"], f["rule_y"], f["x1"], f["rule_y"], stroke=c["rule"], width=0.15, dash=(2.2, 1.6)),
    ]
    if s.get("footer_text"):
        items.append(Text(f["x0"], f["text_y"], s["footer_text"], 8.0, color=c["title"], role=f"{page_key}_footer"))
    lp = logo_path()
    if lp:
        lg = f["logo"]
        items.append(Image(lg["x"], lg["y"], lg["w"], lg["h"], lp))
    return items


def _text_block(box: dict, text: str, L: dict, s: dict, role: str) -> TextBlock:
    tb = TextBlock(box["x"], box["y"], box["w"], box["h"], text or "", L["fonts"]["body"],
                   leading=L["fonts"]["body_leading"], role=role)
    return layout_block(tb, s["font"], L["fonts"]["body_min"])


def page_temperature(cl: Climate, s: dict, texts: dict, L: dict) -> Page:
    lab = LABELS[s["language"]]
    P, C = L["temperature"], L["colors"]
    tfs = L["fonts"]["chart_title"]
    items = _frame(L, s, s["temperature_title"], "temperature")
    items.append(_text_block(P["text"], texts.get("temperature_text", ""), L, s, "temperature_text"))

    # --- comfort (UTCI) heatmap
    cp = P["comfort"]
    pal = L["palettes"]["utci_11"]  # index 0 = extreme heat (+5)
    cols = [pal[5 - v] for v in cl.utci_condition]
    g = hourly_heatmap(cp["box"], cl.doy, cl.hour, cols, months=lab["months"], hour_labels=lab["hours"],
                       grid_color=C["grid_dark"], label_size=8.0, month_size=8.0)
    lg = cp["legend"]
    g.append(Text(lg["x"], lg["y"] - 2.5, lab["condition"], 7.5))
    for i, name in enumerate(lab["utci"]):
        y = lg["y"] + i * lg["row"]
        g.append(Rect(lg["x"], y, lg["w"], lg["row"] + 0.02, fill=pal[i]))
        g.append(Text(lg["x"] + lg["w"] + 1.2, y + lg["row"] * 0.62, name, 7.5))
    b = cp["box"]
    items.append(Text(cp["title_x"], cp["title_y"], lab["comfort_title"], tfs, role="comfort_title"))
    items.append(Group("comfort_chart", g, (b["x"] - 14, b["y"] - 6, lg["x"] + 30 - (b["x"] - 14), b["h"] + 12)))

    # --- monthly chart
    mp = P["monthly"]
    b = mp["box"]
    g = monthly_chart(b, cl.monthly_hourly, colors=C, labels=lab, temp_range=mp["temp_range"])
    items.append(Text(mp["title_x"], mp["title_y"], lab["monthly_title"], tfs, role="monthly_title"))
    items.append(Text(mp["title_x"], mp["subtitle_y"], lab["monthly_subtitle"], tfs, role="monthly_subtitle"))
    items.append(Group("monthly_chart", g, (b["x"] - 30, b["y"] - 5, b["w"] + 74, b["h"] + 10)))
    ml = mp["legend"]
    items.append(Group("monthly_legend", [
        Rect(ml["x"], ml["y"], ml["w"], ml["h"], fill=C["dbt_band"]),
        Rect(ml["x"], ml["y"] + ml["h"] + ml["gap"], ml["w"], ml["h"], fill=C["ghr_legend"]),
    ], (ml["x"] - 0.5, ml["y"] - 0.5, ml["w"] + 1, 2 * ml["h"] + ml["gap"] + 1)))
    items.append(Text(ml["label_x"], ml["y"] + ml["h"] * 0.9, lab["legend_dbt"], 9.5, role="legend_dbt"))
    items.append(Text(ml["label_x"], ml["y"] + ml["h"] * 1.9 + ml["gap"] + 0.3, lab["legend_ghr"], 9.5,
                      role="legend_ghr"))

    # --- cooling / heating filtered heatmaps
    tl = L["temperature_legend"]
    scale = SegmentedScale(L["palettes"]["temperature_ramp"], tl["min"], tl["max"], tl["segments"])
    for key, title, test in (
        ("cooling", lab["cooling_title"].format(t=fmt_t(s["cooling_threshold"])),
         lambda v: v > s["cooling_threshold"]),
        ("heating", lab["heating_title"].format(t=fmt_t(s["heating_threshold"])),
         lambda v: v < s["heating_threshold"]),
    ):
        hp = P[key]
        b = hp["box"]
        cols = [scale.color(v) if test(v) else None for v in cl.dbt]
        g = hourly_heatmap(b, cl.doy, cl.hour, cols, months=lab["months"], hour_labels=lab["hours3"],
                           grid_color=C["grid"], label_size=3.6, month_size=3.6, step_hours=6,
                           minor_hours=3, minor_color=C["grid_light"])
        hl = hp["legend"]
        g += vertical_legend(scale, hl["x"], hl["y"], hl["w"], hl["h"])
        items.append(Text(hp["title_x"], hp["title_y"], title, tfs, role=f"{key}_title"))
        items.append(Group(f"{key}_chart", g, (b["x"] - 9, b["y"] - 1.5, hl["x"] + 10 - (b["x"] - 9), b["h"] + 7)))
    return Page("temperature", items)


def page_sun(cl: Climate, s: dict, texts: dict, L: dict) -> Page:
    lab = LABELS[s["language"]]
    P, C = L["sun"], L["colors"]
    items = _frame(L, s, s["sun_title"], "sun")
    items.append(_text_block(P["text"], texts.get("sun_text", ""), L, s, "sun_text"))
    sp = cl.sunpath
    kd = cl.key_days()
    order = [("summer_solstice", kd["summer_solstice"]), ("equinox", kd["equinox"]),
             ("winter_solstice", kd["winter_solstice"])]

    v3, sd, cap = P["plan_views"], P["side"], P["captions"]
    cam_side = OrthoCamera(sd["camera"]["azimuth"], sd["camera"]["elevation"])
    R = v3["ring_radius"] / 1.035
    for i, (key, days) in enumerate(order):
        cx = v3["centers_x"][i]
        days_drawn = days[:1]  # both equinoxes are practically identical: draw one, label both
        g = stereographic_sunpath(sp, cx, v3["center_y"], R, [], altitude_circles=False,
                                  key_days=days_drawn, sun_color=C["sun"], sun_radius=1.85)
        items.append(Group(f"sunplan_{key}", g, (cx - 50, v3["center_y"] - 50, 100, 100)))
        gx = cx + sd["offset_x"]
        g = sunpath_view(sp, gx, sd["ground_y"], sd["radius"], cam_side, days_drawn, sun_color=C["sun"],
                         sun_radius=1.85, compass=False, ground=(sd["ground_half_width"],))
        items.append(Group(f"sunside_{key}", g, (gx - 46, sd["ground_y"] - 46, 92, 47)))
        if key == "equinox":
            sub = lab["equinox_dates"]
        else:
            m, d = days[0]
            sub = f"({d} {lab['month_names'][m - 1]})"
        items.append(Text(cap["x"][i], cap["y1"], lab[key], 9.0, anchor="middle", role=f"caption_{key}"))
        items.append(Text(cap["x"][i], cap["y2"], sub, 9.0, anchor="middle", role=f"caption_{key}_date"))

    st = P["stereo"]
    tl = L["temperature_legend"]
    scale = SegmentedScale(L["palettes"]["temperature_ramp"], tl["min"], tl["max"], tl["segments"])
    thr = s["sun_threshold"]
    for i, months in enumerate(cl.season_months()):
        cx = st["centers_x"][i]
        pts = [(cl.suns[k], scale.color(cl.dbt[k])) for k in range(cl.n)
               if cl.month[k] in months and cl.dbt[k] > thr and cl.suns[k].altitude > 0]
        g = stereographic_sunpath(sp, cx, st["center_y"], st["radius"], pts, point_radius=st["point_radius"])
        g += vertical_legend(scale, cx + st["legend_dx"], st["legend_y"], st["legend_w"], st["legend_h"],
                             label_size=3.0)
        items.append(Group(f"stereo_{i}", g, (cx - 45, st["center_y"] - 45, 92, 90)))
        label = lab["season_filter"].format(season=lab["seasons"][i], t=fmt_t(thr))
        items.append(Text(cx, st["caption_y"], label, 9.0, anchor="middle", role=f"stereo_caption_{i}"))
    return Page("sun", items)


def _scale_auto(values, ramp, segments=10, nd=1):
    lo, hi = min(values), max(values)
    f = 10 ** nd
    lo, hi = math.floor(lo * f) / f, math.ceil(hi * f) / f
    if hi <= lo:
        hi = lo + 1
    return SegmentedScale(ramp, lo, hi, segments)


def page_ventilation(cl: Climate, s: dict, texts: dict, L: dict) -> Page:
    lab = LABELS[s["language"]]
    P, C = L["ventilation"], L["colors"]
    tfs = L["fonts"]["chart_title"]
    ramp = L["palettes"]["temperature_ramp"]
    items = _frame(L, s, s["ventilation_title"], "ventilation")
    items.append(_text_block(P["text"], texts.get("ventilation_text") or method_text("ventilation_text", s, L), L, s, "ventilation_text"))

    nv = P["nv"]
    lo, hi = s["nv_min"], s["nv_max"]
    scale = SegmentedScale(ramp, lo, hi, 10)
    cols = [scale.color(v) if lo <= v <= hi else None for v in cl.dbt]
    b = nv["box"]
    g = hourly_heatmap(b, cl.doy, cl.hour, cols, months=lab["months"], hour_labels=lab["hours3"],
                       grid_color=C["grid_light"], label_size=7.0, month_size=8.0, step_hours=6,
                       minor_hours=3, minor_color="#cfcfcf")
    lg = nv["legend"]
    g += vertical_legend(scale, lg["x"], lg["y"], lg["w"], lg["h"], label_size=6.5)
    items.append(Text(nv["title_x"], nv["title_y"], lab["nv_title"], tfs, role="nv_title"))
    items.append(Group("nv_chart", g, (b["x"] - 14, b["y"] - 6, lg["x"] + 14 - (b["x"] - 14), b["h"] + 12)))

    hp = P["humidity"]
    items.append(Text(hp["title_x"], hp["title_y"], lab["humidity_title"], tfs, role="humidity_title"))
    series = [(cl.psychro["hr_gkg"], 1), (cl.psychro["enthalpy"], 1), (cl.rh, 0)]
    for k, ((vals, nd), box) in enumerate(zip(series, hp["boxes"])):
        sc = _scale_auto(vals, ramp, 10, nd)
        g = hourly_heatmap(box, cl.doy, cl.hour, [sc.color(v) for v in vals], months=lab["months"],
                           hour_labels=lab["hours"], grid_color="#5a5a5a", label_size=3.6, month_size=3.6)
        x = box["x"] + box["w"] + hp["legend_dx"]
        g += vertical_legend(sc, x, box["y"] + 1.5, hp["legend_w"], box["h"] - 1.5, title="", label_size=3.2)
        items.append(Group(f"humidity_{k}", g, (box["x"] - 9, box["y"] - 2, box["w"] + 25, box["h"] + 7)))
        items.append(Text(box["x"] - 5.4, box["y"] + box["h"] + hp["label_dy"], lab["humidity_labels"][k], 9.0,
                          role=f"humidity_label_{k}"))

    mb = P["monthly_box"]
    frame = [Rect(mb["x"], mb["y"], mb["w"], mb["h"], stroke=C["title"], width=0.15, dash=(1.6, 1.2))]
    g = frame + monthly_small_multiples(mb["grid"], cl.monthly_hourly, colors=C, months=lab["month_upper"],
                                        hours=lab["hours"])
    items.append(Group("dbt_months", g, (mb["x"] - 1, mb["y"] - 1, mb["w"] + 2, mb["h"] + 2)))
    items.append(Text(mb["x"] + mb["title_dx"], mb["y"] + mb["title_dy"], lab["dbt_title"], tfs, role="dbt_title"))
    return Page("ventilation", items)


def _speed_scale(cl: Climate, L: dict) -> SegmentedScale:
    """Fixed legend (layout 'wind_legend', 0-15 m/s like ladybug's reference); faster winds fall in the top bin."""
    w = L.get("wind_legend", {"min": 0.0, "max": 15.0, "segments": 10})
    return SegmentedScale(L["palettes"]["temperature_ramp"], w["min"], w["max"], w["segments"])


QUARTERS = [[1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12]]


def page_wind(cl: Climate, s: dict, texts: dict, L: dict) -> Page:
    lab = LABELS[s["language"]]
    P, C = L["wind"], L["colors"]
    items = _frame(L, s, s["wind_title"], "wind")
    items.append(_text_block(P["text"], texts.get("wind_text") or method_text("wind_text", s, L), L, s, "wind_text"))
    scale = _speed_scale(cl, L)

    rp = P["roses"]
    counts = [rose_counts(cl.wd, cl.ws, cl.wind_hours(q), scale) for q in QUARTERS]
    fmax = max(max_frequency(c) for c in counts)
    for i, c in enumerate(counts):
        cx = rp["centers_x"][i]
        g, step = wind_rose(cx, rp["center_y"], rp["radius"], c, scale, fmax)
        g += speed_legend(scale, cx + rp["legend_dx"], rp["legend_y"], rp["legend_w"], rp["legend_h"], size=3.0)
        if i == 0:
            g.append(Text(cx - rp["radius"] - 9.0, rp["center_y"], lab["freq_lines"].format(n=step), 4.2,
                          anchor="middle", rotate=90))
        items.append(Group(f"rose_q{i}", g, (cx - 40, rp["center_y"] - 33, 82, 66)))
        items.append(Text(cx, rp["title_y"], lab["quarters"][i], 7.5, anchor="middle", role=f"rose_q{i}_title"))

    items.append(Group("wind_table", wind_table(P["table"], lab),
                       (P["table"]["x0"] - 1, P["table"]["y0"] - 1, P["table"]["x1"] - P["table"]["x0"] + 2,
                        P["table"]["y1"] - P["table"]["y0"] + 2)))

    sp = P["sectors"]
    dscale = SegmentedScale(L["palettes"]["temperature_ramp"], 0.0, 360.0, 10)
    sectors = [(315, 45), (45, 135), (135, 225), (225, 315)]
    calm_free = [i for i in range(cl.n) if cl.ws[i] >= 0.1]
    for k, (a0, a1) in enumerate(sectors):
        inside = (lambda d, a0=a0, a1=a1: (d >= a0 or d < a1) if a0 > a1 else (a0 <= d < a1))
        cols = [dscale.color(cl.wd[i]) if (cl.ws[i] >= 0.1 and inside(cl.wd[i])) else None for i in range(cl.n)]
        pct = round(100 * sum(1 for i in calm_free if inside(cl.wd[i])) / max(1, len(calm_free)))
        box = {"x": sp["box_x"], "y": sp["tops"][k], "w": sp["box_w"], "h": sp["h"]}
        g = hourly_heatmap(box, cl.doy, cl.hour, cols, months=lab["months"], hour_labels=lab["hours3"],
                           grid_color="#333333", label_size=2.6, month_size=2.8, step_hours=6, minor_hours=3)
        g += vertical_legend(dscale, sp["legend_x"], box["y"] + 1.2, 2.2, box["h"] - 1.2, title=lab["degrees"],
                             label_size=2.6)
        g += sector_icon(sp["icon_x"], box["y"] + box["h"] / 2, sp["icon_r"], a0, a1,
                         C["wind_sector"], C["wind_sector_fill"])
        g.append(Text(box["x"], box["y"] + box["h"] + 6.0,
                      lab["wind_dir_label"].format(name=lab["sector_names"][k], a=a0, b=a1, p=pct), 3.4))
        items.append(Group(f"wind_sector_{k}", g, (box["x"] - 8, box["y"] - 2, 160, box["h"] + 9.5), crisp=False))

    bp = P["big"]
    c_all = rose_counts(cl.wd, cl.ws, cl.wind_hours(), scale)
    g, step = wind_rose(bp["cx"], bp["cy"], bp["radius"], c_all, scale, max_frequency(c_all),
                        ring_labels=True, label_size=4.0)
    for t in g:  # bigger compass lettering on the main rose
        if isinstance(t, Text):
            t.size *= 2.0 if len(t.text) <= 3 and t.text.isalpha() else 1.0
    g += speed_legend(scale, bp["legend_x"], bp["legend_y"], bp["legend_w"], bp["legend_h"], size=8.0)
    items.append(Group("rose_annual", g, (bp["cx"] - 75, bp["cy"] - 75, 160, 150)))
    return Page("wind", items)


def page_seasonal_wind(cl: Climate, s: dict, texts: dict, L: dict) -> Page:
    lab = LABELS[s["language"]]
    P = L["seasonal_wind"]
    items = _frame(L, s, s["seasonal_wind_title"], "seasonal_wind")
    items.append(_text_block(P["text"], texts.get("seasonal_wind_text") or method_text("seasonal_wind_text", s, L), L, s, "seasonal_wind_text"))
    scale = _speed_scale(cl, L)
    a, b = P["day_hours"]
    day = set(range(a, b))
    rows = [(None, None), (day, lab["day"].format(a=a, b=b)), (set(range(24)) - day, lab["night"].format(a=a, b=b))]
    rp = P["roses"]
    for r, (hours, sub) in enumerate(rows):
        cy = rp["rows_y"][r]
        counts = [rose_counts(cl.wd, cl.ws, cl.wind_hours(q, hours), scale) for q in QUARTERS]
        fmax = max(max_frequency(c) for c in counts)
        for i, c in enumerate(counts):
            cx = rp["centers_x"][i]
            g, step = wind_rose(cx, cy, rp["radius"], c, scale, fmax)
            g += speed_legend(scale, cx + rp["legend_dx"], cy + rp["legend_dy"], rp["legend_w"], rp["legend_h"], size=3.0)
            if i == 0:
                g.append(Text(cx - rp["radius"] - 9.0, cy, lab["freq_lines"].format(n=step), 4.2,
                              anchor="middle", rotate=90))
            items.append(Group(f"srose_{r}_{i}", g, (cx - 40, cy - 33, 82, 66)))
            ty = rp["titles_y"][r]
            items.append(Text(cx, ty[0], lab["quarters"][i], 7.5, anchor="middle", role=f"srose_{r}_{i}_title"))
            if sub:
                items.append(Text(cx, ty[1], sub, 7.5, anchor="middle", role=f"srose_{r}_{i}_sub"))
    return Page("seasonal_wind", items)


def page_shading(cl: Climate, s: dict, texts: dict, L: dict) -> Page:
    lab = LABELS[s["language"]]
    P = L["shading"]
    items = _frame(L, s, s["shading_title"], "shading")
    items.append(_text_block(P["text"], texts.get("shading_text") or method_text("shading_text", s, L), L, s, "shading_text"))
    thr = s["sun_threshold"]
    rg = P["big"]["range"]
    scale = SegmentedScale(L["palettes"]["temperature_ramp"], rg["min"], rg["max"], rg["segments"])
    pts = sh.key_points(cl)                     # big chart: 21st of each month, real EPW temperature
    hot_all = [(cl.suns[i], cl.dbt[i]) for i in range(cl.n)   # SunExplore: every sunlit EPW hour with T >= threshold
               if cl.dbt[i] >= thr and cl.suns[i].altitude > 0]
    sp = cl.sunpath

    bp = P["big"]
    g = sh.degree_compass(bp["cx"], bp["cy"], bp["radius"], size=6.5)
    g += sh.sunpath_lines(sp, bp["cx"], bp["cy"], bp["radius"])
    g += sh.sun_points(pts, bp["cx"], bp["cy"], bp["radius"], scale, thr, r=P["point_radius"] * 1.15)
    items.append(Group("shading_sunpath", g, (bp["cx"] - 62, bp["cy"] - 62, 124, 124)))
    lg = bp["legend"]
    items.append(Group("shading_legend", sh.horizontal_legend(scale, lg["x"], lg["y"], lg["w"], lg["h"],
                                                              lab["dbt_legend"]),
                       (lg["x"] - 1, lg["y"] - 6, lg["w"] + 6, lg["h"] + 11)))

    mp = P["masks"]
    devices = []
    user_devs = s.get("shading_devices") or []
    hot_on = [p for p in hot_all]
    for k, (cx, cy) in enumerate(mp["centers"]):
        base = dict(mp["devices"][k])           # defaults: S, N, E, W (orientation editable)
        if k < len(user_devs) and isinstance(user_devs[k], dict):
            base.update({kk: v for kk, v in user_devs[k].items()
                         if kk in ("facade_az", "type", "overhang_deg", "fin_deg", "fin_side") and v not in (None, "")})
        for kk in ("facade_az", "overhang_deg", "fin_deg"):
            base[kk] = float(base.get(kk) or 0)
        kind = base.get("type", "both")          # none | overhang | fins | both
        if kind not in ("overhang", "both"):
            base["overhang_deg"] = 0.0
        if kind not in ("fins", "both"):
            base["fin_deg"] = 0.0
        dev = sh.evaluate(base, hot_on)
        devices.append(dev)
        fa = int(dev["facade_az"]) % 360
        R = mp["radius"]
        g = sh.sunpath_lines(sp, cx, cy, R, color="#b0b0b0")
        g += sh.sun_points(hot_on, cx, cy, R, scale, thr, r=P["point_radius"] * 0.55)
        g += sh.mask(cx, cy, R, dev)
        g += sh.degree_compass(cx, cy, R, alt_labels=False, size=5.0)
        items.append(Group(f"mask_{k}", g, (cx - 46, cy - 45, 92, 90)))
        dy0, dy1 = mp["diagram_dy"]
        d = sh.section_diagram(cx - 23, cy + dy0 - 6, dev["overhang_deg"]) + \
            sh.plan_diagram(cx - 4, cy + dy1, dev["fin_deg"], dev.get("fin_side", "right"))
        items.append(Group(f"devices_{k}", d, (cx - 26, cy + dy0 - 28, 64, 44)))
        name = lab["facades"].get(str(fa), f"{lab['facade_generic']} {fa}°")
        ov = f"{lab['overhang']}: " + (f"{dev['overhang_deg']:.0f}°" if dev["overhang_deg"] else lab["none"])
        side = lab["sides"].get(dev.get("fin_side", "right"), "")
        fn = f"{lab['fins']}: " + (f"{dev['fin_deg']:.0f}° ({side})" if dev["fin_deg"] else lab["none"])
        items.append(Text(cx + 30, cy - 33, name, 8.0, role=f"facade_{k}"))
        items.append(Text(cx + 30, cy - 29.5, ov, 6.5, role=f"facade_{k}_overhang"))
        items.append(Text(cx + 30, cy - 26.5, fn, 6.5, role=f"facade_{k}_fins"))
        if dev["hot_hours"]:
            items.append(Text(cx + 30, cy - 23.5, lab["coverage"].format(p=dev["coverage_pct"], n=dev["hot_hours"]),
                              6.0, color="#555555", role=f"facade_{k}_coverage"))
    cl.shading_devices = devices  # exposed for the LLM facts
    return Page("shading", items)


BUILDERS = {"temperature": page_temperature, "ventilation": page_ventilation, "sun": page_sun,
            "shading": page_shading, "wind": page_wind, "seasonal_wind": page_seasonal_wind}


def build_pages(cl: Climate, settings: dict, texts: dict, layout: dict | None = None) -> list:
    L = layout or load_layout()
    return [BUILDERS[k](cl, settings, texts, L) for k in settings["sheets"]]
