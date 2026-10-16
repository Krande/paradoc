"""The "chromium" PDF engine: HTML preparation (headings, images, tables, title page) and, where
Playwright and a Chromium build are available, a printed document with a header and footer."""

import pathlib

import pytest

from paradoc.io.pdf.chromium import (
    footer_template,
    header_template,
    layout_tables,
    number_headings,
    resolve_images,
    title_page_html,
    toc_html,
)
from paradoc.io.pdf.config import DocumentInfo, PdfExportConfig


def _doc(**kw) -> DocumentInfo:
    base = dict(
        company="Example Engineering",
        project="Bridge retrofit",
        title="Design report",
        document_number="EX-001",
        revision="B",
        status="DRAFT",
        revisions=[
            {"rev": "A", "date": "2026-01-10", "description": "First issue"},
            {"rev": "B", "date": "2026-02-02", "description": "Updated loads"},
            {"rev": "C", "date": "2026-03-01", "description": "Not issued yet"},
        ],
    )
    base.update(kw)
    return DocumentInfo(**base)


def test_headings_are_numbered_per_chapter_and_appendix():
    body = (
        '<h1 data-label="1" id="intro">Intro</h1><h2 id="a">A</h2><h3 id="a1">A1</h3><h2 id="b">B</h2>'
        '<h1 data-label="2" id="method">Method</h1><h2 id="c">C</h2>'
        '<h1 data-label="A" id="app">Appendix</h1><h2>Data <em>set</em></h2>'
        '<h1 class="unnumbered" id="refs">References</h1>'
    )
    out, heads = number_headings(body)
    assert [(h.number, h.text) for h in heads] == [
        ("1", "Intro"),
        ("1.1", "A"),
        ("1.1.1", "A1"),
        ("1.2", "B"),
        ("2", "Method"),
        ("2.1", "C"),
        ("A", "Appendix"),
        ("A.1", "Data set"),
        ("", "References"),
    ]
    assert '<span class="secno">2.1</span>C' in out
    assert heads[7].anchor == "data-set" and 'id="data-set"' in out  # a heading without an id gets one


def test_toc_lists_numbered_headings_to_the_requested_depth():
    _, heads = number_headings('<h1 data-label="1" id="x">X</h1><h2 id="y">Y</h2><h3 id="z">Z</h3>')
    toc = toc_html(heads, depth=2, pages={"x": 3, "y": 4})
    assert 'href="#x"' in toc and 'href="#y"' in toc and 'href="#z"' not in toc
    assert '<span class="pg">4</span>' in toc


def test_images_resolve_against_the_search_dirs(tmp_path):
    PIL = pytest.importorskip("PIL.Image")
    a, b = tmp_path / "dist", tmp_path / "src" / "chapter"
    (a / "images").mkdir(parents=True)
    b.mkdir(parents=True)
    (tmp_path / "src" / "assets").mkdir()
    img = PIL.new("RGB", (200, 100), "white")
    img.paste((0, 0, 0), (80, 40, 120, 60))
    img.save(a / "images" / "plot.png")
    img.save(tmp_path / "src" / "assets" / "poster.png")
    body = (
        '<img src="images/plot.png"><img src="../assets/poster.png"><img src="missing.png"><img src="https://x/y.png">'
    )

    out, missing = resolve_images(body, [a, b], crop_dir=tmp_path / "crop")

    assert missing == ["missing.png"]
    assert out.count('src="file://') == 2 and 'src="https://x/y.png"' in out
    cropped = sorted((tmp_path / "crop").iterdir())
    assert len(cropped) == 2 and PIL.open(cropped[0]).size[0] < 200


def test_table_widths_follow_the_column_width_mode():
    short = '<table style="width:50%"><colgroup><col style="width: 10%"/></colgroup><tr><td>1.5</td></tr></table>'
    long = '<table><colgroup><col style="width: 90%"/></colgroup><tr><td>' + "word " * 20 + "</td></tr></table>"
    assert layout_tables(short, "relative", 24) == short
    out = layout_tables(short + long, "content", 24)
    assert "colgroup" not in out and "width:50%" not in out
    assert out.count('class="pd-wide"') == 1  # only the table with long text spans the text width


def test_title_page_lists_revisions_up_to_the_current_one():
    page = title_page_html(_doc(revision="B", note="Rebuilt from archived results."), None, None)
    assert "First issue" in page and "Updated loads" in page and "Not issued yet" not in page
    assert page.index("Updated loads") < page.index("First issue")  # newest on top
    assert "2026-02-02" in page and "Rebuilt from archived results." in page and "DRAFT" in page

    older = title_page_html(_doc(revision="A"), None, None)
    assert "Updated loads" not in older and "2026-01-10" in older


def test_header_carries_document_data_and_footer_the_company():
    cfg = PdfExportConfig(engine="chromium")
    doc = _doc()
    head = header_template(doc, cfg, "data:image/svg+xml;base64,AAAA")
    foot = footer_template(doc, cfg, "data:image/svg+xml;base64,AAAA")
    assert "Bridge retrofit" in head and "Design report" in head and "Rev B \u00b7 2026-02-02" in head
    assert 'class="pageNumber"' in head and 'class="totalPages"' in head
    assert "Example Engineering" not in head and "data:image" not in head
    assert "Example Engineering" in foot and "data:image" in foot and "DRAFT" in foot
    assert "pageNumber" not in foot


def test_branding_can_go_in_the_header_instead():
    cfg = PdfExportConfig(engine="chromium", branding="header")
    doc = _doc()
    head = header_template(doc, cfg, "data:image/svg+xml;base64,AAAA")
    foot = footer_template(doc, cfg)
    assert "Example Engineering" in head and "Bridge retrofit" in head and "DRAFT \u2013 Rev B" in head
    assert "EX-001" in foot and "Issued 2026-02-02" in foot
    assert 'class="pageNumber"' in foot and 'class="totalPages"' in foot


def test_pdf_overrides_merge_over_the_profile():
    from paradoc.tasks.orchestrator import _deep_merge

    base = {"engine": "chromium", "document": {"revision": "B", "company": "X"}}
    merged = PdfExportConfig.model_validate(_deep_merge(base, {"document": {"revision": "A"}}))
    assert merged.document.revision == "A" and merged.document.company == "X"


def _chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        from paradoc.io.pdf.chromium import launch_browser

        with sync_playwright() as p:
            launch_browser(p).close()
        return True
    except Exception:  # noqa: BLE001 -- no playwright, or no browser build
        return False


@pytest.mark.skipif(not _chromium_available(), reason="needs Playwright and a Chromium build")
def test_a_document_prints_with_title_page_toc_and_page_numbers(tmp_path):
    pypdf = pytest.importorskip("pypdf")
    from paradoc import OneDoc

    src = tmp_path / "doc"
    (src / "00-main").mkdir(parents=True)
    (src / "01-app").mkdir()
    (src / "00-main" / "01-intro.md").write_text(
        "# Introduction\n\nSome text.\n\n## Scope\n\nMore text.\n\n# Method\n\n## Loads\n\nText.\n", encoding="utf-8"
    )
    (src / "01-app" / "01-data.md").write_text("# Data\n\nAppendix text.\n", encoding="utf-8")
    one = OneDoc(src, work_dir=tmp_path / "work")
    cfg = PdfExportConfig(engine="chromium", document=_doc())
    one.compile("report", export_format="pdf", pdf_config=cfg)

    pdf = pathlib.Path(one.dist_dir) / "report.pdf"
    reader = pypdf.PdfReader(str(pdf))
    n = len(reader.pages)
    text = [p.extract_text() for p in reader.pages]
    assert n >= 5  # title, contents, two chapters and the appendix, each on its own page
    assert "Design report" in text[0] and "EX-001" in text[0]
    assert "Contents" in text[1]
    assert all(f"Page {i + 1} of {n}" in t for i, t in enumerate(text))
    assert all("DRAFT" in t and "Rev B" in t and "Example Engineering" in t for t in text)
    # The TOC's page number for chapter 2 is the page the chapter starts on.
    method_page = next(i + 1 for i, t in enumerate(text) if "2 Method" in t.replace("\n", " ") and i > 1)
    assert f"Method {method_page}" in " ".join(text[1].split()).replace(". ", " ")
