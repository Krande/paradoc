"""Export paths that must not fall over on an ordinary document or an ordinary machine."""

import pytest
from docx import Document
from docx.oxml.ns import qn

from paradoc.exceptions import LatexNotInstalled
from paradoc.io.pdf import exporter as pdf_exporter
from paradoc.io.word.reference_helper import ReferenceHelper
from paradoc.io.word.utils import request_field_update_on_open


def test_a_table_directly_after_another_has_no_caption_rather_than_crashing():
    doc = Document()
    doc.add_paragraph("Table 1-1: The first table")
    first = doc.add_table(rows=1, cols=1)
    doc.add_table(rows=1, cols=1)

    helper = ReferenceHelper()
    # The block before the second table is the first table, which has no `.text`.
    assert helper._extract_caption_text_from_caption(first) is None
    assert helper._extract_caption_text_from_caption(doc.paragraphs[0]) == "The first table"


def test_field_update_on_open_goes_where_the_schema_puts_it_and_can_be_removed(tmp_path):
    path = tmp_path / "doc.docx"
    Document().save(str(path))

    request_field_update_on_open(path)
    settings = Document(str(path)).settings.element
    flag = settings.find(qn("w:updateFields"))
    assert flag is not None and flag.get(qn("w:val")) == "true"
    # Word rejects settings.xml with elements out of schema order; `compat` follows `updateFields`.
    tags = [el.tag for el in settings]
    if qn("w:compat") in tags:
        assert tags.index(qn("w:updateFields")) < tags.index(qn("w:compat"))

    request_field_update_on_open(path)  # idempotent
    assert len(Document(str(path)).settings.element.findall(qn("w:updateFields"))) == 1

    request_field_update_on_open(path, request=False)
    assert Document(str(path)).settings.element.find(qn("w:updateFields")) is None


def test_an_image_path_reaches_markdown_with_forward_slashes():
    from paradoc.document import _md_image_path

    # Backslashes in `![cap](...)` are markdown escapes: pandoc would look for "C:docsbeam.png".
    assert _md_image_path(r"C:\docs\_assets\beam.png") == "C:/docs/_assets/beam.png"
    assert _md_image_path("images/plot.png") == "images/plot.png"


def test_an_uncaptioned_table_is_formatted_like_a_captioned_one():
    from docx.shared import Pt

    from paradoc.common import TableFormat
    from paradoc.io.word.exporter import _is_figure_layout_table
    from paradoc.io.word.models import apply_table_format

    doc = Document()
    tbl = doc.add_table(rows=2, cols=2)
    for r, row in enumerate(tbl.rows):
        for c, cell in enumerate(row.cells):
            cell.paragraphs[0].add_run(f"{r}{c}")
    assert not _is_figure_layout_table(tbl)

    # "Table Grid": python-docx's blank document lacks the default "Grid Table 1 Light", which
    # paradoc's own Word template provides.
    apply_table_format(tbl, TableFormat(style="Table Grid"))
    runs = [cell.paragraphs[0].runs[0] for row in tbl.rows for cell in row.cells]
    assert all(run.font.size == Pt(11) and run.font.name == "Arial" for run in runs)
    assert [run.font.bold for run in runs] == [True, True, False, False]  # header row only


def test_pdf_fonts_default_to_system_fonts_unless_the_document_sets_them(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    assert pdf_exporter.default_font_args(None) == ["--variable=mainfont=Cambria", "--variable=monofont=Consolas"]

    meta = tmp_path / "metadata.yaml"
    meta.write_text("title: x\nmainfont: Georgia\n", encoding="utf-8")
    assert pdf_exporter.default_font_args(meta) == ["--variable=monofont=Consolas"]

    monkeypatch.setattr("sys.platform", "linux")
    meta.write_text("title: x\n", encoding="utf-8")
    assert pdf_exporter.default_font_args(meta) == [
        "--variable=mainfont=DejaVu Serif",
        "--variable=monofont=DejaVu Sans Mono",
    ]


def test_pdf_engine_falls_back_past_a_missing_xelatex(monkeypatch):
    monkeypatch.delenv("PARADOC_PDF_ENGINE", raising=False)
    monkeypatch.setattr(pdf_exporter.shutil, "which", lambda name: "/bin/tectonic" if name == "tectonic" else None)
    assert pdf_exporter.resolve_pdf_engine() == "/bin/tectonic"


def test_pdf_engine_override_and_absence_are_reported(monkeypatch):
    monkeypatch.setattr(pdf_exporter.shutil, "which", lambda name: None)
    monkeypatch.setenv("PARADOC_PDF_ENGINE", "no-such-engine")
    with pytest.raises(LatexNotInstalled, match="no-such-engine"):
        pdf_exporter.resolve_pdf_engine()
    monkeypatch.delenv("PARADOC_PDF_ENGINE")
    with pytest.raises(LatexNotInstalled, match="tectonic"):
        pdf_exporter.resolve_pdf_engine()
