import unittest

from common import files_dir, test_dir
from ex_funcs import my_calc_example_1, my_calc_example_2

from paradoc import OneDoc
from paradoc.utils import make_df


class MathDocTests(unittest.TestCase):
    def test_math_doc(self):
        report_dir = files_dir / "doc_math"

        inputs = [(0, 0), (1, 1), (2, 1), (2, 2)]
        df1 = make_df(inputs, ("a", "b", "V_x"), my_calc_example_1)
        df2 = make_df(inputs, ("a", "b", "V_x"), my_calc_example_2)

        one = OneDoc(report_dir, work_dir=test_dir / "doc_math")

        one.add_equation("my_equation", my_calc_example_1)
        one.add_equation("my_equation_2", my_calc_example_2)

        one.add_table("results", df1, "Results from Equation my_equation")
        one.add_table("results_2", df2, "Results from Equation my_equation_2")

        one.compile("MathDoc")


if __name__ == "__main__":
    unittest.main()
