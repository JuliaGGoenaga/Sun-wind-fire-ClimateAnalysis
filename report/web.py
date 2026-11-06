"""Entry points for the browser build (Pyodide, see web/ and docs/).

Same logic as the FastAPI endpoints in app/main.py, but with no server and no
reportlab / PyMuPDF / python-pptx: Python returns the SVG pages and a JSON
"PPTX spec"; the browser turns them into PDF (jsPDF + svg2pdf) and PPTX
(PptxGenJS). Every function takes and returns JSON strings.
"""
from __future__ import annotations

import json

from .climate import Climate
from .fonts import default_font, font_choices, metrics
from .pages import build_pages
from .primitives import PT_TO_MM, Group, Image, Line, Text, TextBlock, r2
from .settings import (DEFAULT_SETTINGS, FIXED_TEXT_KEYS, LABELS, SHEETS, load_layout, method_text,
                       resolve)
from .text.prompts import (build_prompt, build_text_prompt, detect_language, fit_text, limits,
                           parse_response, strict_suffix, system_prompt)
from .writers.svg import SvgWriter

EPW_PATH = "/tmp/input.epw"
_CACHE: dict = {}


def _climate(sun_exposed: bool = True) -> Climate:
    key = bool(sun_exposed)
    if key not in _CACHE:
        _CACHE[key] = Climate(EPW_PATH, key)
    return _CACHE[key]


def _resolved(settings: dict):
    probe = _climate(True)
    s = resolve(settings, probe.city)
    return _climate(s["utci_sun_exposed"]), s


# ------------------------------------------------------------------ API
def fonts() -> str:
    return json.dumps({"fonts": font_choices(), "default": default_font()})


def text_limits() -> str:
    return json.dumps(limits())


def sheets(settings_json: str) -> str:
    s = resolve(json.loads(settings_json or "{}"), "{city}")
    lab = LABELS[s["language"]]
    L = load_layout()
    return json.dumps({
        "sheets": [{"key": k, "title": lab[f"{k}_title"], "name": lab["sheet_names"][k]} for k in SHEETS],
        "method_texts": {k: method_text(k, s, L) for k in FIXED_TEXT_KEYS},
        "shading_devices": [dict(d, name=lab["facades"][str(d["facade_az"])]) for d in L["shading"]["masks"]["devices"]],
    })


def load_epw() -> str:
    """The EPW was written to EPW_PATH by the worker; parse it and drop old results."""
    _CACHE.clear()
    cl = _climate(True)
    loc = cl.location
    return json.dumps({"id": "local", "city": cl.city, "country": loc.country, "latitude": loc.latitude,
                       "longitude": loc.longitude, "elevation": loc.elevation, "defaults": DEFAULT_SETTINGS})


def preview(body_json: str) -> str:
    body = json.loads(body_json)
    cl, s = _resolved(body.get("settings") or {})
    pages = build_pages(cl, s, body.get("texts") or {})
    w = SvgWriter(s["font"])
    return json.dumps({"svgs": [w.page(p) for p in pages], "settings": s})


def prompt(settings_json: str) -> str:
    cl, s = _resolved(json.loads(settings_json or "{}"))
    return json.dumps({"prompt": build_prompt(cl.facts(s), s["language"])})


def text_prompts(body_json: str) -> str:
    """Short prompts (one per text) for the LLM; the browser calls Ollama / LM Studio itself."""
    body = json.loads(body_json)
    cl, s = _resolved(body.get("settings") or {})
    facts = cl.facts(s)
    keys = [k for k in body.get("keys") or ["temperature_text", "sun_text"] if k in ("temperature_text", "sun_text")]
    return json.dumps({"language": s["language"],
                       "prompts": {k: build_text_prompt(facts, s["language"], k) for k in keys},
                       "strict_suffix": strict_suffix(s["language"]),
                       "system": system_prompt(s["language"])})


def check_language(raw: str, language: str) -> str:
    return json.dumps(detect_language(raw) == ("es" if language == "es" else "en"))


def fit(key: str, raw: str) -> str:
    return json.dumps(fit_text(raw, **limits()[key]))


def parse(raw: str) -> str:
    return json.dumps(parse_response(raw))


# --------------------------------------------------------- export specs
def _svg_crop(writer: SvgWriter, items: list, bbox: tuple) -> str:
    x, y, w, h = bbox
    out = []
    for it in items:
        writer.item(it, out)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{r2(w)}mm" height="{r2(h)}mm" '
            f'viewBox="{r2(x)} {r2(y)} {r2(w)} {r2(h)}" {writer._font_attr()}>'
            f'<rect x="{r2(x)}" y="{r2(y)}" width="{r2(w)}" height="{r2(h)}" fill="#ffffff"/>'
            + "".join(out) + "</svg>")


def pptx_spec(body_json: str) -> str:
    """Same layout rules as report/writers/pptx.py: charts -> one picture each (rendered by the
    browser from the cropped SVG), titles / header / footer / texts -> editable text boxes."""
    body = json.loads(body_json)
    cl, s = _resolved(body.get("settings") or {})
    pages = build_pages(cl, s, body.get("texts") or {})
    writer = SvgWriter(s["font"])
    m = metrics(s["font"])
    out = []
    for page in pages:
        items = []
        for it in page.items:
            if isinstance(it, (Group, Image)):
                bbox = it.bbox if isinstance(it, Group) else (it.x, it.y, it.w, it.h)
                sub = it.items if isinstance(it, Group) else [it]
                items.append({"type": "image", "name": getattr(it, "id", "logo") or "chart",
                              "x": bbox[0], "y": bbox[1], "w": bbox[2], "h": bbox[3],
                              "svg": _svg_crop(writer, sub, bbox)})
            elif isinstance(it, Line):
                items.append({"type": "line", "x1": it.x1, "y1": it.y1, "x2": it.x2, "y2": it.y2,
                              "color": it.stroke, "width": it.width, "dash": bool(it.dash)})
            elif isinstance(it, Text):
                smm = it.size * PT_TO_MM
                w = max(m.width_mm(it.text, it.size) * 1.15 + 2, 10)
                x = it.x - w / 2 if it.anchor == "middle" else it.x - w if it.anchor == "end" else it.x
                items.append({"type": "text", "x": x, "y": it.y - smm * m.ascent, "w": w, "h": smm * 1.3,
                              "paragraphs": [it.text], "size": it.size, "color": it.color,
                              "align": {"middle": "center", "end": "right"}.get(it.anchor, "left"),
                              "name": it.role or "text"})
            elif isinstance(it, TextBlock):
                items.append({"type": "text", "x": it.x, "y": it.y, "w": it.w + 1.0, "h": it.h,
                              "paragraphs": it.paragraphs, "size": it.size, "color": it.color, "align": "left",
                              "leading": it.leading, "name": it.role or "text"})
        out.append({"id": page.id, "width": page.width, "height": page.height, "items": items})
    return json.dumps({"font": s["font"], "city": s["city"], "pages": out})


def svg_pages(body_json: str) -> str:
    body = json.loads(body_json)
    cl, s = _resolved(body.get("settings") or {})
    pages = build_pages(cl, s, body.get("texts") or {})
    w = SvgWriter(s["font"])
    return json.dumps({"svgs": [w.page(p) for p in pages], "font": s["font"], "city": s["city"]})
