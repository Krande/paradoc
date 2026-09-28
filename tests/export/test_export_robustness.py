"""Export paths that must not fall over on an ordinary document or an ordinary machine."""

import pathlib
import re
import shutil
import subprocess

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


def _variables(args):
    return dict(
        a.removeprefix("--variable=").split("=", 1) for a in args if a.startswith("--variable=") and "=" in a[11:]
    )


def test_pdf_defaults_page_fonts_and_headings(tmp_path, monkeypatch):
    from paradoc.io.pdf.config import PdfExportConfig

    monkeypatch.setattr("sys.platform", "win32")
    args = pdf_exporter.pandoc_args(PdfExportConfig(), None, tmp_path)
    assert _variables(args) == {
        "papersize": "a4",
        "fontsize": "10pt",
        "geometry": "margin=2cm",
        "mainfont": "Cambria",
        "monofont": "Consolas",
    }
    assert "--variable=block-headings" in args

    monkeypatch.setattr("sys.platform", "linux")
    assert _variables(pdf_exporter.pandoc_args(PdfExportConfig(), None, tmp_path))["mainfont"] == "DejaVu Serif"


def test_pdf_settings_come_from_the_config_but_the_documents_own_metadata_wins(tmp_path):
    from paradoc.io.pdf.config import PdfExportConfig

    cfg = PdfExportConfig(fontsize="12pt", mainfont="Georgia", block_headings=False, figure_max_height=0.3)
    meta = tmp_path / "metadata.yaml"
    meta.write_text("title: x\nfontsize: 11pt\n", encoding="utf-8")
    args = pdf_exporter.pandoc_args(cfg, meta, tmp_path)
    variables = _variables(args)
    assert "fontsize" not in variables  # the document says 11pt itself
    assert variables["mainfont"] == "Georgia"
    assert "--variable=block-headings" not in args
    header = next(a for a in args if a.startswith("--include-in-header=")).split("=", 1)[1]
    text = open(header, encoding="utf-8").read()
    assert "\\floatplacement{figure}{H}" in text and "0.3\\textheight" in text


def test_pdf_config_is_read_from_paradoc_toml_and_typos_are_rejected(tmp_path):
    from paradoc.tasks.config import load_task_config

    toml = tmp_path / "paradoc.toml"
    toml.write_text('[build.pdf]\noutputs = ["pdf"]\n\n[build.pdf.pdf]\ntable_font_size = "small"\n', encoding="utf-8")
    cfg = load_task_config(toml, profile="pdf").pdf
    assert cfg.table_font_size == "small" and cfg.figure_placement == "H"  # the rest keep defaults

    toml.write_text('[build.pdf]\noutputs = ["pdf"]\n\n[build.pdf.pdf]\ntable_font = "small"\n', encoding="utf-8")
    with pytest.raises(Exception, match="table_font"):
        load_task_config(toml, profile="pdf")


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="needs pandoc")
def test_short_tables_size_columns_to_content_and_long_ones_keep_wrapping(tmp_path):
    from paradoc.io.pdf.config import PdfExportConfig

    lua = pdf_exporter.table_filter(PdfExportConfig(), tmp_path)

    def latex(md):
        run = subprocess.run(
            ["pandoc", "-f", "markdown", "-t", "latex", f"--lua-filter={lua}"],
            input=md, capture_output=True, text=True, encoding="utf-8", check=True,
        )  # fmt: skip
        return run.stdout

    numbers = (
        "+------+----------+\n| Mode | ccx_HEXR |\n+======+==========+\n| 1    | 14.3018  |\n+------+----------+\n"
    )
    out = latex(numbers)
    assert "\\begin{longtable}[]{@{}ll@{}}" in out  # natural widths: no p{...} to overrun
    assert "\\begingroup\\footnotesize\\setlength{\\tabcolsep}{3pt}" in out and "\\endgroup" in out

    prose = "+----+------+\n| A  | B    |\n+====+======+\n| x  | " + "long text " * 5 + "|\n+----+------+\n"
    assert "p{" in latex(prose.replace("+------+", "+" + "-" * 52 + "+"))


def test_images_are_made_absolute_and_cropped_of_empty_margins(tmp_path):
    # pillow is optional: without it trim_whitespace declines and images go in uncropped.
    Image = pytest.importorskip("PIL.Image")

    from paradoc.io.pdf.config import PdfExportConfig

    src_dir = tmp_path / "build" / "01-app"
    src_dir.mkdir(parents=True)
    im = Image.new("RGB", (200, 100), "white")
    im.paste((255, 0, 0), (90, 40, 110, 60))  # a 20x20 block in a mostly-empty picture
    im.save(src_dir / "poster.png")

    out = tmp_path / "dist"
    out.mkdir()
    md = "![A poster](poster.png){#fig:p}\n\n![remote](https://example.com/x.png)"
    new = pdf_exporter.prepare_images(md, src_dir, out, PdfExportConfig())
    path = re.search(r"\]\(([^)]+)\)\{#fig:p\}", new).group(1)
    assert pathlib.Path(path).is_absolute() and "\\" not in path
    assert Image.open(path).size[0] < 40  # cropped to the block plus a little padding
    assert "https://example.com/x.png" in new

    assert (
        pdf_exporter.prepare_images(md, src_dir, out, PdfExportConfig(figure_trim_whitespace=False)).count(
            (src_dir / "poster.png").as_posix()
        )
        == 1
    )


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
