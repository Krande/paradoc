import pandas as pd

from paradoc import OneDoc
from paradoc.common import TableFormat


def test_table(files_dir, test_dir):
    report_dir = files_dir / "doc_table"
    one = OneDoc(report_dir, work_dir=test_dir / "doc_table")
    df = pd.DataFrame([(0, 0), (1, 2)], columns=["a", "b"])

    one.add_table("my_table", df, "A basic table")
    one.add_table("my_table_2", df, "A slightly smaller table", TableFormat(font_size=8))
    one.add_table("my_table_3", df, "No Space 1")
    one.add_table("my_table_4", df, "No Space 2")
    one.add_table("my_table_5", df, "No Space 3")

    one.compile("TableDoc")


def test_regular_table(files_dir, test_dir):
    report_dir = files_dir / "doc_regular_table"
    one = OneDoc(report_dir, work_dir=test_dir / "doc_regular_table")

    one.compile("TableDoc", export_format="docx")
