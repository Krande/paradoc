"""A DOCX template of one's own: its page header's DOCPROPERTY fields show the document properties the
export is given, and its own tables (a title page's, say) are left as the template has them."""

from docx import Document
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

from paradoc import MY_DOCX_TMPL, MY_DOCX_TMPL_BLANK, OneDoc
from paradoc.io.word.compose.properties import CustomProperties


def _field(name: str) -> str:
    def run(inner):
        return f"<w:r>{inner}</w:r>"

    return (
        f"<w:p {nsdecls('w')}>"
        + run('<w:fldChar w:fldCharType="begin"/>')
        + run(f'<w:instrText xml:space="preserve"> DOCPROPERTY  {name}  \\* MERGEFORMAT </w:instrText>')
        + run('<w:fldChar w:fldCharType="separate"/>')
        + run("<w:t></w:t>")
        + run('<w:fldChar w:fldCharType="end"/>')
        + "</w:p>"
    )


def _template(path):
    doc = Document(str(MY_DOCX_TMPL))
    header = doc.sections[0].header
    header.is_linked_to_previous = False
    header._element.append(parse_xml(_field("DocumentNumber")))
    header._element.append(parse_xml(_field("Revision")))
    # A title block: a table of the template's own, first in its body.
    table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Document no."
    table.cell(0, 0).paragraphs[0].alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
    doc.element.body.insert(0, table._tbl)
    props = CustomProperties(doc)
    props["DocumentNumber"] = ""
    props["Revision"] = ""
    doc.save(str(path))
    return path


def test_header_fields_show_the_given_properties_and_the_templates_table_stays(tmp_path):
    src = tmp_path / "doc"
    (src / "00-main").mkdir(parents=True)
    (src / "00-main" / "01-intro.md").write_text(
        "# Introduction\n\nText.\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\nTable: Numbers {#tbl:numbers}\n",
        encoding="utf-8",
    )
    tmpl = _template(tmp_path / "template.docx")
    one = OneDoc(src, work_dir=tmp_path / "work")
    one.compile(
        "report",
        export_format="docx",
        update_docx_with_com=False,
        main_tmpl=tmpl,
        app_tmpl=MY_DOCX_TMPL_BLANK,
        document_properties={"DocumentNumber": "EX-001", "Revision": "B"},
    )
    out = Document(str(one.dist_dir / "report.docx"))
    props = dict(CustomProperties(out).items())
    assert props["DocumentNumber"] == "EX-001" and props["Revision"] == "B"
    header_text = [p.text for p in out.sections[0].header.paragraphs]
    assert "EX-001" in header_text and "B" in header_text
    title_block = out.tables[0]
    assert title_block.cell(0, 0).text == "Document no."
    assert title_block.cell(0, 0).paragraphs[0].alignment == WD_PARAGRAPH_ALIGNMENT.LEFT  # not restyled
    data = out.tables[1]
    assert data.cell(1, 0).paragraphs[0].alignment == WD_PARAGRAPH_ALIGNMENT.RIGHT  # paradoc's data tables


def test_set_properties_sets_them(tmp_path):
    doc = Document(str(MY_DOCX_TMPL))
    props = CustomProperties(doc)
    props.set_properties({"Title": "Report", "Revision": "C"})
    assert props["Title"] == "Report" and props["Revision"] == "C"
