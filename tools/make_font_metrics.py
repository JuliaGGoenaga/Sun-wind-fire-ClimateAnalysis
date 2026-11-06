"""Build small JSON tables with the advance width of each character for common fonts.

Only metrics are stored (no glyphs), so the browser version can wrap text exactly like
the desktop version while the text itself is drawn with the font installed on the
viewer's computer. Run on a machine that has the fonts:  python tools/make_font_metrics.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fontTools.ttLib import TTFont  # noqa: E402

from report.fonts import available_fonts  # noqa: E402

FAMILIES = ["Arial", "Verdana", "Georgia", "Tahoma", "Trebuchet MS", "Times New Roman", "Courier New"]
CHARS = list(range(32, 383)) + [0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2026, 0x20AC, 0x2192, 0x00B7]
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "report", "font_metrics")

fonts = available_fonts()
os.makedirs(OUT, exist_ok=True)
for fam in FAMILIES:
    path = fonts.get(fam)
    if not path:
        print("missing", fam)
        continue
    f = TTFont(path, lazy=True)
    cmap, hmtx = f.getBestCmap(), f["hmtx"].metrics
    adv = {str(c): hmtx[cmap[c]][0] for c in CHARS if c in cmap and cmap[c] in hmtx}
    data = {"family": fam, "upm": f["head"].unitsPerEm, "ascent": f["hhea"].ascent, "adv": adv}
    name = fam.replace(" ", "_") + ".json"
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
        json.dump(data, fh, separators=(",", ":"), sort_keys=True)
    print(fam, len(adv), "chars")
