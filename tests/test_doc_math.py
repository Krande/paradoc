import unittest
from paradoc import OneDoc
from common import files_dir, test_dir

class MathDocTests(unittest.TestCase):
    def test_math_doc(self):
        report_dir = files_dir / "doc_math"
        one = OneDoc(report_dir)
        one.compile('MathDoc')


if __name__ == '__main__':
    unittest.main()
