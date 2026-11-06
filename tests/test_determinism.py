import glob
import hashlib
import json
import os

import pytest

from report.build import render, to_pdf, to_svgs

HERE = os.path.dirname(__file__)
_EPWS = sorted(glob.glob(os.path.join(HERE, "fixtures", "*.epw")))
if not _EPWS:  # EPW files are not in the repo: drop any .epw into tests/fixtures/ to run the tests
    pytest.skip("no EPW file in tests/fixtures/", allow_module_level=True)
EPW = next((p for p in _EPWS if "Dallas" in p), _EPWS[0])
TEXTS = json.load(open(os.path.join(HERE, "fixtures", "dallas_texts.json"), encoding="utf-8"))


def _hash(b):
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()


def test_svg_and_pdf_are_identical_between_runs():
    _, s, p1 = render(EPW, {}, TEXTS)
    _, _, p2 = render(EPW, {}, TEXTS)
    assert [_hash(x) for x in to_svgs(p1, s)] == [_hash(x) for x in to_svgs(p2, s)]
    assert _hash(to_pdf(p1, s)) == _hash(to_pdf(p2, s))


def test_a3_size():
    _, s, pages = render(EPW, {}, TEXTS)
    svg = to_svgs(pages, s)[0]
    assert 'width="420.0mm" height="297.0mm"' in svg or 'width="420mm" height="297mm"' in svg
