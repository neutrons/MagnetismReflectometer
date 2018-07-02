import unittest
import sys
sys.path.append("livereduce")
sys.path.append(".")

from mr_reduction.settings import MANTID_PATH
sys.path.insert(0, MANTID_PATH)
import mantid.simpleapi as api

import numpy as np

import polarization_analysis
from polarization_analysis import calculate_ratios


class PolarizationAnalysisTest(unittest.TestCase):
    def test_simple_load(self):
        ws=api.LoadEventNexus(Filename="REF_M_29160")
        _, ratio1, ratio2, asym1 = calculate_ratios(ws,
                                                    delta_wl = 0.05,
                                                    roi=[156,210,49,170],
                                                    slow_filter=True)

        y1 = ratio1.readY(0)
        ref = np.loadtxt("test/r1_29160.txt").T
        diff = (y1-ref[1])**2/ref[2]**2
        self.assertTrue(np.sum(diff)/(len(y1)+1.0) < 0.5)

        y1 = ratio2.readY(0)
        ref = np.loadtxt("test/r2_29160.txt").T
        diff = (y1-ref[1])**2/ref[2]**2
        self.assertTrue(np.sum(diff)/(len(y1)+1.0) < 0.5)

        y1 = asym1.readY(0)
        ref = np.loadtxt("test/a2_29160.txt").T
        diff = (y1-ref[1])**2/ref[2]**2
        self.assertTrue(np.sum(diff)/(len(y1)+1.0) < 0.5)

if __name__ == '__main__':
    unittest.main()
