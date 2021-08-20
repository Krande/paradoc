import logging
import os
import pathlib
import unittest

from paradoc.rules.eurocode import Bolt

logging.basicConfig(level=logging.INFO)

test_dir = pathlib.Path(os.getenv("PARADOC_temp_dir", "C:/ada/tests/paradoc/basic"))


class EurocodeTests(unittest.TestCase):
    def test_eurocode_bolts(self):
        b = Bolt(20e-3, 22e-3, 10e-3)
        F_bc = b.shear_capacity
        print(F_bc)


if __name__ == "__main__":
    unittest.main()
