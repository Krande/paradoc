import logging

import pytest

from paradoc import OneDoc
from paradoc.exceptions import LatexNotInstalled
from paradoc.utils import make_df


def my_calc_example_1(a, b):
    """A calculation with doc stub"""
    V_x = a + 1 * (0.3 + a * b) ** 2
    return V_x


def my_calc_example_2(a, b):
    """
    A calculation with a longer doc stub
    """
    V_n = a + 1 * (0.16 + a * b) ** 2
    V_x = V_n * 0.98
    return V_x


@pytest.fixture(scope="function")
def test_doc(files_dir, tmp_path):
    logging.getLogger().setLevel(logging.INFO)
    report_dir = files_dir / "doc_math"

    inputs = [(0, 0), (1, 1), (2, 1), (2, 2)]
    df1 = make_df(inputs, ("a", "b", "V_x"), my_calc_example_1)
    df2 = make_df(inputs, ("a", "b", "V_x"), my_calc_example_2)

    one = OneDoc(report_dir, work_dir=tmp_path / "doc_math")

    one.add_equation("my_equation_1", my_calc_example_1, include_python_code=True)
    one.add_equation("my_equation_2", my_calc_example_2)

    one.add_table("results", df1, "Results from Equation my_equation")
    one.add_table("results_2", df2, "Results from Equation my_equation_2")

    return one


def test_math_docx(test_doc):
    test_doc.compile("MathDoc", export_format=OneDoc.FORMATS.DOCX)


def test_math_pdf_latex_installation(test_doc):
    try:
        test_doc.compile("MathDoc", export_format=OneDoc.FORMATS.PDF)
    except LatexNotInstalled as e:
        print(e)
