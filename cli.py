"""Command line: python cli.py file.epw --out out/ [--texts texts.json] [--settings settings.json]"""
import argparse
import json
import os
import re

from report.build import render, to_pdf, to_pptx, to_svgs


def main():
    ap = argparse.ArgumentParser(description="A3 climate report from an EPW file")
    ap.add_argument("epw")
    ap.add_argument("--out", default="out")
    ap.add_argument("--texts", help="JSON with temperature_text and sun_text")
    ap.add_argument("--settings", help="JSON with settings (font, language, header_right, footer_text...)")
    ap.add_argument("--formats", default="svg,pdf,pptx")
    a = ap.parse_args()
    texts = json.load(open(a.texts, encoding="utf-8")) if a.texts else {}
    settings = json.load(open(a.settings, encoding="utf-8")) if a.settings else {}
    cl, s, pages = render(a.epw, settings, texts)
    os.makedirs(a.out, exist_ok=True)
    stem = re.sub(r"[^A-Za-z0-9]+", "_", s["city"]).strip("_") or "climate"
    fmts = a.formats.split(",")
    if "svg" in fmts:
        for i, svg in enumerate(to_svgs(pages, s), 1):
            open(os.path.join(a.out, f"{stem}_{i}.svg"), "w", encoding="utf-8").write(svg)
    if "pdf" in fmts:
        open(os.path.join(a.out, f"{stem}.pdf"), "wb").write(to_pdf(pages, s))
    if "pptx" in fmts:
        open(os.path.join(a.out, f"{stem}.pptx"), "wb").write(to_pptx(pages, s))
    print(f"{s['city']}: written to {a.out}/")


if __name__ == "__main__":
    main()
