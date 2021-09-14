import unittest

from common import files_dir, test_dir
from ex_funcs import my_calc_example_1, my_calc_example_2

from paradoc import OneDoc
from paradoc.utils import basic_equation_compiler, make_df


class MathDocTests(unittest.TestCase):
    def test_math_doc(self):
        report_dir = files_dir / "doc_math"

        inputs = [(0, 0), (1, 1), (2, 1), (2, 2)]
        df1 = make_df(inputs, ("a", "b", "V_x"), my_calc_example_1)
        df2 = make_df(inputs, ("a", "b", "V_x"), my_calc_example_2)

        one = OneDoc(report_dir, work_dir=test_dir / "doc_math")

        one.equations["my_equation"] = basic_equation_compiler(my_calc_example_1)
        one.equations["my_equation_2"] = basic_equation_compiler(my_calc_example_2)
        one.add_table("results", df1)
        one.add_table("results_2", df2)

        one.compile("MathDoc")


if __name__ == "__main__":
    unittest.main()
