import unittest

from common import files_dir, test_dir
from ex_funcs import my_calc_example_1, my_calc_example_2

from paradoc import OneDoc
from paradoc.exceptions import LatexNotInstalled
from paradoc.utils import make_df


class MathDocTests(unittest.TestCase):
    def setUp(self) -> None:
        report_dir = files_dir / "doc_math"

        inputs = [(0, 0), (1, 1), (2, 1), (2, 2)]
        df1 = make_df(inputs, ("a", "b", "V_x"), my_calc_example_1)
        df2 = make_df(inputs, ("a", "b", "V_x"), my_calc_example_2)

        one = OneDoc(report_dir, work_dir=test_dir / "doc_math")

        one.add_equation("my_equation_1", my_calc_example_1, include_python_code=True)
        one.add_equation("my_equation_2", my_calc_example_2)

        one.add_table("results", df1, "Results from Equation my_equation")
        one.add_table("results_2", df2, "Results from Equation my_equation_2")

        self.one = one

    def test_math_docx(self):
        self.one.compile("MathDoc", export_format=OneDoc.FORMATS.DOCX)

    def test_math_pdf_latex_installation(self):
        try:
            self.one.compile("MathDoc", export_format=OneDoc.FORMATS.PDF)
        except LatexNotInstalled as e:
            print(e)


if __name__ == "__main__":
    unittest.main()
