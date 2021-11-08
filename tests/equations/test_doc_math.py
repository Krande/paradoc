import logging

import pytest

from ex_funcs import my_calc_example_1, my_calc_example_2
from paradoc import OneDoc
from paradoc.exceptions import LatexNotInstalled
from paradoc.utils import make_df


@pytest.fixture
def test_doc(files_dir, test_dir):
    logging.getLogger().setLevel(logging.INFO)
    report_dir = files_dir / "doc_math"

    inputs = [(0, 0), (1, 1), (2, 1), (2, 2)]
    df1 = make_df(inputs, ("a", "b", "V_x"), my_calc_example_1)
    df2 = make_df(inputs, ("a", "b", "V_x"), my_calc_example_2)

    one = OneDoc(report_dir, work_dir=test_dir / "doc_math")

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
