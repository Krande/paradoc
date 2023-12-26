import os

from paradoc import OneDoc
from paradoc.exceptions import LatexNotInstalled

auto_open = os.getenv("AUTO_OPEN", False)


def test_doc1_export_to_pdf(files_dir, test_dir):
    source = files_dir / "doc1"
    dest_dir = test_dir / "report_doc1_pdf"

    try:
        one = OneDoc(source, work_dir=dest_dir)
        one.compile("report1", auto_open=auto_open, export_format=OneDoc.FORMATS.PDF)
    except LatexNotInstalled as e:
        print(e)


def test_doc2_export_to_pdf(files_dir, test_dir):
    source = files_dir / "doc2"
    dest_dir = test_dir / "report_doc2_pdf"

    try:
        one = OneDoc(source, work_dir=dest_dir)
        one.compile("report2", auto_open=auto_open, export_format=OneDoc.FORMATS.PDF)
    except LatexNotInstalled as e:
        print(e)
