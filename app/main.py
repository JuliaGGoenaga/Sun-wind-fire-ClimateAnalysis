"""Web app: upload EPW -> texts (local LLM or manual) -> preview -> download PDF / PPTX / SVG.

Run:  uvicorn app.main:app --port 8000   (from the project root)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys

from fastapi import Body, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from report.build import load_climate, render, to_pdf, to_pptx, to_svg_zip, to_svgs  # noqa: E402
from report.fonts import available_fonts, default_font  # noqa: E402
from report.settings import DEFAULT_SETTINGS, FIXED_TEXT_KEYS, LABELS, SHEETS, load_layout, method_text, resolve  # noqa: E402
from report.text import llm  # noqa: E402
from report.text.prompts import (build_prompt, build_text_prompt, detect_language, fit_text, limits,  # noqa: E402
                                 parse_response, strict_suffix)

RUNS = os.path.join(ROOT, "runs")
os.makedirs(RUNS, exist_ok=True)

app = FastAPI(title="Climate report A3")


@app.middleware("http")
async def no_cache_ui(request, call_next):
    """Always serve the latest HTML/CSS/JS (avoids stale UI after an update)."""
    resp = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        resp.headers["Cache-Control"] = "no-cache, must-revalidate"
    return resp
app.mount("/static", StaticFiles(directory=os.path.join(ROOT, "app", "static")), name="static")


def _run_dir(rid: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{16}", rid):
        raise HTTPException(400, "bad id")
    d = os.path.join(RUNS, rid)
    if not os.path.exists(os.path.join(d, "input.epw")):
        raise HTTPException(404, "unknown report, upload the EPW again")
    return d


def _epw(rid: str) -> str:
    return os.path.join(_run_dir(rid), "input.epw")


@app.get("/")
def index():
    return FileResponse(os.path.join(ROOT, "app", "static", "index.html"))


@app.get("/api/fonts")
def fonts():
    return {"fonts": list(available_fonts().keys()), "default": default_font()}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    data = await file.read()
    if b"LOCATION" not in data[:200]:
        raise HTTPException(400, "This does not look like an EPW file")
    rid = hashlib.sha256(data).hexdigest()[:16]
    d = os.path.join(RUNS, rid)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "input.epw"), "wb") as f:
        f.write(data)
    cl = load_climate(os.path.join(d, "input.epw"))
    loc = cl.location
    return {"id": rid, "city": cl.city, "country": loc.country, "latitude": loc.latitude,
            "longitude": loc.longitude, "elevation": loc.elevation, "defaults": DEFAULT_SETTINGS}


@app.get("/api/{rid}/epw")
def epw_file(rid: str):
    """The uploaded EPW, so the SunExplore tab can use the same file."""
    return FileResponse(_epw(rid), media_type="text/plain", filename="climate.epw")


@app.post("/api/{rid}/prompt")
def prompt(rid: str, settings: dict = Body(default={})):
    path = _epw(rid)
    cl = load_climate(path)
    s = resolve(settings, cl.city)
    cl = load_climate(path, s["utci_sun_exposed"])
    return {"prompt": build_prompt(cl.facts(s), s["language"])}


@app.post("/api/sheets")
def sheets(settings: dict = Body(default={})):
    """Sheet list with default titles + the fixed method texts for the current settings."""
    s = resolve(settings, "{city}")
    lab = LABELS[s["language"]]
    L = load_layout()
    return {"sheets": [{"key": k, "title": lab[f"{k}_title"], "name": lab["sheet_names"][k]} for k in SHEETS],
            "method_texts": {k: method_text(k, s, L) for k in FIXED_TEXT_KEYS},
            "shading_devices": [dict(d, name=lab["facades"][str(d["facade_az"])]) for d in L["shading"]["masks"]["devices"]]}


@app.get("/api/limits")
def text_limits():
    return limits()


@app.post("/api/parse")
def parse(body: dict = Body(...)):
    """Normalise a pasted answer (JSON from another assistant) to paragraphs + word limits."""
    return parse_response(body.get("raw", ""))


@app.get("/api/llm/models")
def models(backend: str = "ollama", url: str | None = None, x_api_key: str | None = Header(default=None)):
    try:
        return {"ok": True, "models": llm.list_models(backend, url, x_api_key)}
    except llm.LLMUnavailable as e:
        return {"ok": False, "models": [], "error": str(e)}


@app.post("/api/{rid}/generate")
def generate(rid: str, body: dict = Body(...)):
    d = _run_dir(rid)
    settings = body.get("settings", {})
    path = os.path.join(d, "input.epw")
    cl = load_climate(path)
    s = resolve(settings, cl.city)
    cl = load_climate(path, s["utci_sun_exposed"])
    facts = cl.facts(s)
    lang = s["language"]
    keys = [k for k in body.get("keys") or ["temperature_text", "sun_text"] if k in ("temperature_text", "sun_text")]
    prompts = {k: build_text_prompt(facts, lang, k) for k in keys}
    key = hashlib.sha256(json.dumps([prompts, body.get("backend"), body.get("model")], sort_keys=True).encode()).hexdigest()[:16]
    cache = os.path.join(d, f"texts_{key}.json")
    if os.path.exists(cache):  # same EPW + settings + model -> same text
        return json.load(open(cache, encoding="utf-8"))
    lim = limits()
    texts = {}
    try:
        for k, p in prompts.items():  # one short call per text: much easier for small models
            raw = llm.generate(body.get("backend", "ollama"), body.get("model"), p, body.get("url"), language=lang,
                               api_key=body.get("api_key"))
            if detect_language(raw) != ("es" if lang == "es" else "en"):  # one stricter retry
                raw = llm.generate(body.get("backend", "ollama"), body.get("model"), p + strict_suffix(lang),
                                   body.get("url"), language=lang, api_key=body.get("api_key"))
            texts[k] = fit_text(raw, **lim[k])
    except (llm.LLMUnavailable, KeyError) as e:
        return JSONResponse({"error": str(e), "prompt": build_prompt(facts, lang)}, status_code=503)
    json.dump(texts, open(cache, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return texts


@app.post("/api/{rid}/preview")
def preview(rid: str, body: dict = Body(...)):
    _, s, pages = render(_epw(rid), body.get("settings"), body.get("texts"))
    return {"svgs": to_svgs(pages, s), "settings": s}


@app.post("/api/{rid}/download/{fmt}")
def download(rid: str, fmt: str, body: dict = Body(...)):
    _, s, pages = render(_epw(rid), body.get("settings"), body.get("texts"))
    stem = re.sub(r"[^A-Za-z0-9]+", "_", s["city"]).strip("_") or "climate"
    if fmt == "pdf":
        data, mime, name = to_pdf(pages, s), "application/pdf", f"{stem}_climate_analysis.pdf"
    elif fmt == "pptx":
        data = to_pptx(pages, s)
        mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        name = f"{stem}_climate_analysis.pptx"
    elif fmt == "svg":
        data, mime, name = to_svg_zip(pages, s, stem), "application/zip", f"{stem}_climate_analysis_svg.zip"
    else:
        raise HTTPException(400, "format must be pdf, pptx or svg")
    return Response(data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{name}"'})
