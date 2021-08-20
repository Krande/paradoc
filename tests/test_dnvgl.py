import unittest

from paradoc.rules.dnv.c203 import alloweable_stress_range
from paradoc.rules.dnv.c208 import local_yield_check
from paradoc.utils import func_to_eq


class TestC208(unittest.TestCase):
    def test_local_yield_check(self):
        res = local_yield_check(3.718e-3, 20e-3, 20e-3)

        assert res == 0.0099147
        eq, params = func_to_eq(local_yield_check)
        print(eq[0])
        print(params)


class TestC203(unittest.TestCase):
    def test_allowable_stress_range(self):
        _ = alloweable_stress_range(250e3, 2, 1.0, 1.0, "B1")


if __name__ == "__main__":
    unittest.main()
