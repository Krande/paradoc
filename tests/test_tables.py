import unittest

import pandas as pd
from common import files_dir, test_dir

from paradoc import OneDoc
from paradoc.common import TableFormat


class TableTests(unittest.TestCase):
    def test_table(self):
        report_dir = files_dir / "doc_table"
        one = OneDoc(report_dir, work_dir=test_dir / "doc_table")
        df = pd.DataFrame([(0, 0), (1, 2)], columns=["a", "b"])

        one.add_table("my_table", df, "A basic table")
        one.add_table("my_table_2", df, "A slightly smaller table", TableFormat(font_size=8))

        one.compile("TableDoc")


if __name__ == "__main__":
    unittest.main()
