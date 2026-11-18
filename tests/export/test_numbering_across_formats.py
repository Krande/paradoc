"""Headings, captions and references are numbered alike in every export format.

One small document -- two chapters, an appendix, nested headings, a figure and a table on each
side, references to them -- built as the web reader's AST, DOCX, ODT and PDF. Each must show:

* headings 1, 1.1, 1.1.1 in the main body and A, A.1, A.1.1 in the appendix ("Appendix A" on the
  top-level appendix heading);
* figure and table captions numbered per top-level heading: "Figure 1.1", "Table A.1", with an
  uncaptioned table taking no number (a LaTeX longtable steps the counter regardless);
* references reading the same number as the caption they point at.
"""

import base64
import re
import zipfile

import pytest

from paradoc import OneDoc
from paradoc.exceptions import LatexNotInstalled
from paradoc.numbering import heading_numbers, label_chapters, number_headings

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
)

MAIN = """# Introduction

See @fig:overview, @tbl:materials and @fig:extra_plot.

## Scope

### Limits

![Overview of the layout](images/a.png){#fig:overview}

# Analysis

| Uncaptioned | Table |
|-------------|-------|
| counts      | not   |

| Material | Grade |
|----------|-------|
| Steel    | S355  |

Table: Material grades {#tbl:materials}
"""

APP = """# Extra results

## Cases

### First case

![Extra plot](images/b.png){#fig:extra_plot}

| Case | Value |
|------|-------|
| 1    | 2     |

Table: Extra table {#tbl:extra}
"""

HEADINGS = [
    "1 Introduction",
    "1.1 Scope",
    "1.1.1 Limits",
    "2 Analysis",
    "Appendix A Extra results",
    "A.1 Cases",
    "A.1.1 First case",
]
CAPTIONS = [
    "Figure 1.1: Overview of the layout",
    "Table 2.1: Material grades",
    "Figure A.1: Extra plot",
    "Table A.1: Extra table",
]
REFERENCES = ["Figure 1.1", "Table 2.1", "Figure A.1"]


def _one(tmp_path) -> OneDoc:
    src = tmp_path / "doc"
    for sub, md, png in (("00-main", MAIN, "a.png"), ("01-app", APP, "b.png")):
        d = src / sub
        (d / "images").mkdir(parents=True)
        (d / "images" / png).write_bytes(PNG)
        (d / "content.md").write_text(md, encoding="utf-8")
    return OneDoc(src, work_dir=tmp_path / "work")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


# --- the filter's heading numbers ------------------------------------------------------------


def _header(level, ident, classes=()):
    return {"t": "Header", "c": [level, [ident, list(classes), []], [{"t": "Str", "c": ident}]]}


def test_heading_numbers_main_and_appendix():
    blocks = [
        _header(1, "a"),
        _header(2, "a1"),
        _header(3, "a11"),
        _header(2, "a2"),
        _header(1, "b"),
        _header(2, "skip", ["unnumbered"]),
        _header(2, "b1"),
        {"t": "RawBlock", "c": ["tex", "\\appendix"]},
        _header(1, "x"),
        _header(2, "x1"),
        _header(3, "x11"),
        _header(1, "y"),
        _header(2, "y1"),
    ]
    got = {b["c"][1][0]: (n, app) for b, n, app in heading_numbers(blocks)}
    assert got == {
        "a": ("1", False),
        "a1": ("1.1", False),
        "a11": ("1.1.1", False),
        "a2": ("1.2", False),
        "b": ("2", False),
        "b1": ("2.1", False),
        "x": ("A", True),
        "x1": ("A.1", True),
        "x11": ("A.1.1", True),
        "y": ("B", True),
        "y1": ("B.1", True),
    }


def test_number_headings_writes_numbers_into_the_text():
    ast = {
        "blocks": [_header(1, "a"), {"t": "RawBlock", "c": ["tex", "\\appendix"]}, _header(1, "x"), _header(2, "x1")]
    }
    number_headings(label_chapters(ast))
    texts = []
    for b in ast["blocks"]:
        if b["t"] == "Header":
            span = b["c"][2][0]
            assert span["t"] == "Span" and span["c"][0][1] == ["header-section-number"]
            texts.append(" ".join(i["c"] for i in span["c"][1] if i["t"] == "Str"))
    assert texts == ["1", "Appendix A", "A.1"]


# --- each format -----------------------------------------------------------------------------


def _ast_stringify(node) -> str:
    if isinstance(node, list):
        return "".join(_ast_stringify(n) for n in node)
    if isinstance(node, dict):
        t = node.get("t")
        if t == "Str":
            return node["c"]
        if t in ("Space", "SoftBreak", "LineBreak"):
            return " "
        return _ast_stringify(node.get("c"))
    return ""


def _web_heading_numbers(sections) -> list[str]:
    """The numbers the web reader shows: frontend/src/ast/headingNumbers.ts, in Python."""
    out, main, app = [], [0] * 6, [0] * 6
    for s in sections:
        counters = app if s["isAppendix"] else main
        lvl = s["level"]
        counters[lvl - 1] += 1
        counters[lvl:] = [0] * (6 - lvl)
        first = chr(64 + counters[0]) if s["isAppendix"] else str(counters[0])
        number = ".".join([first, *map(str, counters[1:lvl])])
        prefix = "Appendix " if s["isAppendix"] and lvl == 1 else ""
        out.append(f"{prefix}{number} {s['title']}")
    return out


def test_web_reader(tmp_path):
    from paradoc.io.ast.exporter import ASTExporter

    one = _one(tmp_path)
    exporter = one.get_ast()
    ast = exporter.build_ast()
    manifest, _ = exporter.slice_sections(ast)
    assert _web_heading_numbers(manifest["sections"]) == HEADINGS

    captions, refs = [], []

    def walk(n):
        if isinstance(n, dict):
            if n.get("t") == "Figure":
                captions.append(_norm(_ast_stringify(n["c"][1][1])))
            elif n.get("t") == "Table":
                captions.append(_norm(_ast_stringify(n["c"][1][1])))
            elif n.get("t") == "Link" and n["c"][2][0].startswith("#"):
                refs.append(_norm(_ast_stringify(n["c"][1])))
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)

    walk(ast["blocks"])
    assert [c for c in captions if c] == CAPTIONS
    assert refs == REFERENCES
    assert isinstance(exporter, ASTExporter)


def test_odt(tmp_path):
    one = _one(tmp_path)
    one.compile("doc", export_format="odt")
    with zipfile.ZipFile(one.dist_dir / "doc.odt") as z:
        content = z.read("content.xml").decode("utf-8")

    def text(xml):
        return _norm(re.sub(r"<[^>]+>", "", xml))

    headings = [text(h) for h in re.findall(r"<text:h[^>]*>(.*?)</text:h>", content, re.S)]
    assert headings == HEADINGS
    paragraphs = [text(p) for p in re.findall(r"<text:p[^>]*>(.*?)</text:p>", content, re.S)]
    assert [p for p in paragraphs if re.match(r"(Figure|Table) [\w.]+:", p)] == CAPTIONS
    assert "See Figure 1.1, Table 2.1 and Figure A.1." in paragraphs
    assert "appendix" not in " ".join(paragraphs)  # the raw LaTeX marker is not printed


def test_pdf(tmp_path):
    pypdf = pytest.importorskip("pypdf")
    from paradoc.io.pdf.exporter import resolve_pdf_engine

    try:
        resolve_pdf_engine()
    except LatexNotInstalled as exc:
        pytest.skip(str(exc))
    one = _one(tmp_path)
    one.compile("doc", export_format="pdf")
    reader = pypdf.PdfReader(str(one.dist_dir / "doc.pdf"))
    text = _norm(" ".join(page.extract_text() or "" for page in reader.pages))
    # Typeset spacing between a number and its title varies; compare without whitespace.
    squeezed = re.sub(r"\s+", "", text)
    for expected in [*HEADINGS, *CAPTIONS, "See Figure 1.1, Table 2.1 and Figure A.1."]:
        assert re.sub(r"\s+", "", expected) in squeezed, (expected, text)
    # No running count anywhere: a figure or table number without its chapter part.
    assert not re.search(r"(Figure|Table)\s+\d+(?![.\d])", text), text


DOCX_HEADING_STYLES = {
    "Heading1": (False, 1),
    "Heading2": (False, 2),
    "Heading3": (False, 3),
    "Appendix": (True, 1),
    "AppendixX1": (True, 2),
    "AppendixX2": (True, 3),
}


def _docx_paragraphs(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    for p in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S):
        style = re.search(r'<w:pStyle w:val="([^"]+)"', p)
        text = "".join(re.findall(r"<w:t(?: [^>]*)?>([^<]*)</w:t>", p))
        instr = [i.strip() for i in re.findall(r"<w:instrText[^>]*>([^<]*)</w:instrText>", p)]
        yield (style.group(1) if style else ""), _norm(text), instr


@pytest.mark.parametrize("indexed", [True, False], ids=["indexed-figures", "build-time-figures"])
def test_docx(tmp_path, indexed):
    one = _one(tmp_path)
    if not indexed:
        # Figures a filter or figure source makes at build time are not in OneDoc's index.
        one.figures.clear()
    one.compile("doc", export_format="docx", update_docx_with_com=False)

    headings, captions = [], {}
    main, app = [0] * 3, [0] * 3
    for style, text, instr in _docx_paragraphs(one.dist_dir / "doc.docx"):
        if style in DOCX_HEADING_STYLES:
            # The template's heading list styles number these: "%1.%2" / "Appendix %1".
            is_app, lvl = DOCX_HEADING_STYLES[style]
            c = app if is_app else main
            c[lvl - 1] += 1
            c[lvl:] = [0] * (3 - lvl)
            first = chr(64 + c[0]) if is_app else str(c[0])
            headings.append(
                f"{'Appendix ' if is_app and lvl == 1 else ''}{'.'.join([first, *map(str, c[1:lvl])])} {text}"
            )
        m = re.match(r"(Figure|Table) [\w.]+: (.*)", text)
        if m and instr:
            captions[f"{m.group(1)} {m.group(2)}"] = instr

    assert headings == HEADINGS
    # Every caption: the chapter number / appendix letter (STYLEREF) and a counter restarting
    # at each top-level heading (SEQ \s 1) -- what Word evaluates to "Figure 1.1", "Figure A.1".
    for caption in CAPTIONS:
        kind, number, title = re.match(r"(\w+) ([\w.]+): (.*)", caption).groups()
        key = f"{kind} {title}"
        assert key in captions, (key, captions)
        styleref, seq = captions[key][0], captions[key][-1]
        heading_style = '"Appendix"' if number.startswith("A") else '"Heading 1"'
        assert styleref.startswith("STYLEREF") and heading_style in styleref, (caption, captions[key])
        assert seq.startswith(f"SEQ {kind}") and "\\s 1" in seq, (caption, captions[key])
