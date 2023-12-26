import os

from paradoc import OneDoc

auto_open = os.getenv("AUTO_OPEN", False)


def test_doc1_export_to_html(files_dir, test_dir):
    source = files_dir / "doc1"
    dest = test_dir / "report_md_html/index.html"

    one = OneDoc(source, work_dir=dest.parent)
    one.compile("index", auto_open=auto_open, export_format=OneDoc.FORMATS.HTML)


def test_doc2_export_to_html(files_dir, test_dir):
    source = files_dir / "doc2"
    dest = test_dir / "report_md_html/index.html"

    one = OneDoc(source, work_dir=dest.parent)
    one.compile("index", auto_open=auto_open, export_format=OneDoc.FORMATS.HTML)
