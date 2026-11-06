"""Build the static (GitHub Pages) version of the web app into docs/.

    python tools/build_web.py

docs/ = the same UI as app/static (index.html, app.js, style.css, SunExplore tab)
      + web/backend.js and web/worker.js (Python runs in the browser with Pyodide)
      + py.zip with report/ (code + font metrics) and layout/a3_climate.json.
Publish: GitHub -> Settings -> Pages -> Deploy from a branch -> <branch> /docs.
"""
from __future__ import annotations

import os
import shutil
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
STATIC = os.path.join(ROOT, "app", "static")
FIXED_TIME = (2020, 1, 1, 0, 0, 0)  # reproducible zip


def build_index() -> str:
    with open(os.path.join(STATIC, "index.html"), encoding="utf-8") as f:
        html = f.read()
    html = html.replace('"/static/', '"./')
    html = html.replace('<script src="./app.js"></script>',
                        '<script src="./backend.js"></script>\n<script src="./app.js"></script>')
    assert './backend.js' in html, "app.js script tag not found"
    return html


def build_py_zip(path: str) -> int:
    n = 0
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for base in ("report", "layout"):
            for dirpath, dirnames, files in os.walk(os.path.join(ROOT, base)):
                dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
                for name in sorted(files):
                    if not name.endswith((".py", ".json")):
                        continue
                    full = os.path.join(dirpath, name)
                    rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
                    info = zipfile.ZipInfo(rel, date_time=FIXED_TIME)
                    info.compress_type = zipfile.ZIP_DEFLATED
                    with open(full, "rb") as fh:
                        z.writestr(info, fh.read())
                    n += 1
    return n


def main():
    if os.path.isdir(DOCS):
        shutil.rmtree(DOCS)
    os.makedirs(DOCS)
    for name in ("app.js", "style.css"):
        shutil.copy2(os.path.join(STATIC, name), DOCS)
    shutil.copytree(os.path.join(STATIC, "sunexplore"), os.path.join(DOCS, "sunexplore"))
    for name in ("backend.js", "worker.js"):
        shutil.copy2(os.path.join(ROOT, "web", name), DOCS)
    with open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8") as f:
        f.write(build_index())
    n = build_py_zip(os.path.join(DOCS, "py.zip"))
    open(os.path.join(DOCS, ".nojekyll"), "w").close()  # serve files as they are
    print(f"docs/ ready ({n} Python/JSON files in py.zip)")


if __name__ == "__main__":
    main()
