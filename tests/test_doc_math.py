import unittest

from common import files_dir, test_dir
from ex_funcs import my_calc_example_1

from paradoc import OneDoc


class MathDocTests(unittest.TestCase):
    def test_math_doc(self):
        report_dir = files_dir / "doc_math"

        one = OneDoc(report_dir, work_dir=test_dir / "doc_math")
        one.functions["my_equation"] = my_calc_example_1
        one.compile("MathDoc")


if __name__ == "__main__":
    unittest.main()
