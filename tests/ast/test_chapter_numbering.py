"""Chapter-scoped numbering of figures, tables and equations.

Figures/tables/equations carry the number of the top-level heading they sit under and restart
at each new top-level heading ("Figure 2.1"); after ``\\appendix`` the chapter part is the
appendix letter ("Figure A.1"). Captions and references must agree.
"""

import base64
import json
import re
import subprocess
import sys

import pytest

from paradoc import OneDoc
from paradoc.numbering import (
    FILTER_PATH,
    appendix_letter,
    chapter_labels,
    label_chapters,
)
from paradoc.tasks.config import load_task_config

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
)

MAIN_1 = """# Introduction

See @fig:overview, @fig:detail, @tbl:materials, @eq:balance and @fig:extra_plot.

![Overview of the layout](images/a.png){#fig:overview}

# Analysis

![Detail of the joint](images/b.png){#fig:detail}

![Second detail](images/c.png){#fig:detail2}

| Material | Grade |
|----------|-------|
| Steel    | S355  |

Table: Material grades {#tbl:materials}

$$ F = m a $$ {#eq:balance}
"""

APP_1 = """# Extra results

![Extra plot](images/d.png){#fig:extra_plot}

| Case | Value |
|------|-------|
| 1    | 2     |

Table: Extra table {#tbl:extra}

# Further results

![Further plot](images/e.png){#fig:further}
"""


def _header(level, ident, attrs=None):
    return {"t": "Header", "c": [level, [ident, [], list(attrs or [])], [{"t": "Str", "c": ident}]]}


def _appendix_marker():
    return {"t": "RawBlock", "c": ["tex", "\\appendix"]}


def _labels(ast):
    out = {}
    for blk in ast["blocks"]:
        if blk.get("t") == "Header":
            kv = dict(blk["c"][1][2])
            out[blk["c"][1][0]] = kv.get("label")
    return out


@pytest.mark.parametrize("n,expected", [(1, "A"), (2, "B"), (26, "Z"), (27, "AA"), (28, "AB"), (52, "AZ")])
def test_appendix_letter(n, expected):
    assert appendix_letter(n) == expected


def test_label_chapters_main_and_appendix():
    ast = {
        "blocks": [
            _header(1, "intro"),
            _header(2, "intro-sub"),
            _header(1, "analysis"),
            _header(1, "results"),
            _appendix_marker(),
            _header(1, "app-one"),
            _header(2, "app-one-sub"),
            _header(1, "app-two"),
        ]
    }
    label_chapters(ast)
    assert _labels(ast) == {
        "intro": "1",
        "intro-sub": None,  # only top-level headings are chapters
        "analysis": "2",
        "results": "3",
        "app-one": "A",
        "app-one-sub": None,
        "app-two": "B",
    }


def test_label_chapters_keeps_explicit_label():
    ast = {"blocks": [_header(1, "a"), _header(1, "b", [["label", "X"]]), _header(1, "c")]}
    label_chapters(ast)
    assert _labels(ast) == {"a": "1", "b": "X", "c": "3"}


def test_chapter_labels_flags_appendix():
    blocks = [_header(1, "a"), _appendix_marker(), _header(1, "b")]
    assert [(label, app) for _, label, app in chapter_labels(blocks)] == [("1", False), ("A", True)]


def test_filter_script_roundtrip():
    """pandoc runs the filter as its own process: JSON in on stdin, JSON out on stdout."""
    ast = {
        "pandoc-api-version": [1, 23, 1],
        "meta": {},
        "blocks": [_header(1, "a"), _appendix_marker(), _header(1, "b")],
    }
    res = subprocess.run(
        [sys.executable, str(FILTER_PATH)], input=json.dumps(ast), capture_output=True, text=True, check=True
    )
    assert _labels(json.loads(res.stdout)) == {"a": "1", "b": "A"}


def _make_doc(tmp_path):
    src = tmp_path / "doc"
    for sub, md in (("00-main", MAIN_1), ("01-app", APP_1)):
        d = src / sub
        (d / "images").mkdir(parents=True)
        for name in "abcde":
            (d / "images" / f"{name}.png").write_bytes(PNG)
        (d / "content.md").write_text(md, encoding="utf-8")
    return src


def _stringify(node) -> str:
    """Flatten pandoc inlines/blocks to text."""
    if isinstance(node, list):
        return "".join(_stringify(n) for n in node)
    if isinstance(node, dict):
        t = node.get("t")
        if t == "Str":
            return node["c"]
        if t in ("Space", "SoftBreak", "LineBreak"):
            return " "
        if t == "Math":
            return node["c"][1]
        return _stringify(node.get("c"))
    return ""


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def _captions_and_refs(ast):
    captions = {}
    refs = {}
    for node in _walk(ast["blocks"]):
        t = node.get("t")
        if t == "Figure":
            attr, cap, _ = node["c"]
            captions[attr[0]] = _stringify(cap[1])
        elif t == "Table":
            attr, cap = node["c"][0], node["c"][1]
            if attr[0]:
                captions[attr[0]] = _stringify(cap[1])
        elif t == "Div" and node["c"][0][0].startswith("tbl:"):
            for inner in _walk(node["c"][1]):
                if inner.get("t") == "Table":
                    captions[node["c"][0][0]] = _stringify(inner["c"][1][1])
                    break
        elif t == "Link":
            target = node["c"][2][0]
            if target.startswith("#"):
                refs[target[1:]] = _stringify(node["c"][1])
    return captions, refs


def _number(text):
    m = re.search(r"((?:[A-Z]+|\d+)\.\d+|\d+)", text)
    return m.group(1) if m else None


def test_ast_captions_and_references_are_chapter_scoped(tmp_path):
    one = OneDoc(_make_doc(tmp_path), work_dir=tmp_path / "work")
    ast = one.get_ast().build_ast()
    captions, refs = _captions_and_refs(ast)

    expected = {
        "fig:overview": "1.1",
        "fig:detail": "2.1",
        "fig:detail2": "2.2",
        "tbl:materials": "2.1",
        "fig:extra_plot": "A.1",
        "tbl:extra": "A.1",
        "fig:further": "B.1",
    }
    for ident, num in expected.items():
        assert ident in captions, f"no caption found for {ident}: {sorted(captions)}"
        assert captions[ident].startswith(("Figure " + num, "Table " + num)), (ident, captions[ident])

    # Every reference shows the same number as its caption.
    for ident in ("fig:overview", "fig:detail", "tbl:materials", "fig:extra_plot"):
        assert _number(refs[ident]) == expected[ident], (ident, refs[ident])
    assert _number(refs["eq:balance"]) == "2.1"


def test_ast_running_numbers_when_disabled(tmp_path):
    one = OneDoc(_make_doc(tmp_path), work_dir=tmp_path / "work", chapter_numbering=False)
    ast = one.get_ast().build_ast()
    captions, refs = _captions_and_refs(ast)
    assert captions["fig:extra_plot"].startswith("Figure 4")
    assert _number(refs["fig:extra_plot"]) == "4"


def test_static_html_is_chapter_scoped(tmp_path):
    from paradoc.io.html.exporter import HTMLExporter

    one = OneDoc(_make_doc(tmp_path), work_dir=tmp_path / "work")
    one._prep_compilation()
    one._perform_variable_substitution()
    html = " ".join(HTMLExporter(one)._build_styled_html(include_navbar=False).split())
    assert "Figure 2.2: Second detail" in html
    assert "Figure A.1: Extra plot" in html
    assert "Figure B.1: Further plot" in html
    assert '<a href="#fig:extra_plot">Figure A.1</a>' in html
    assert '<a href="#tbl:materials">Table 2.1</a>' in html


def test_paradoc_toml_chapter_numbering(tmp_path):
    assert load_task_config(tmp_path / "missing.toml").chapter_numbering is True
    toml = tmp_path / "paradoc.toml"
    toml.write_text("[paradoc]\nchapter_numbering = false\n", encoding="utf-8")
    assert load_task_config(toml).chapter_numbering is False
