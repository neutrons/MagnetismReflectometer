import unittest
import sys
import os
sys.path.append("livereduce")
sys.path.append(".")

from mr_reduction.settings import MANTID_PATH
sys.path.insert(0, MANTID_PATH)
import mantid.simpleapi as api

import numpy as np

import polarization_analysis
from polarization_analysis import calculate_ratios
from mr_reduction.data_info import Fitter
import mr_reduction.mr_reduction as mr
from mr_reduction.mr_direct_beam_finder import DirectBeamFinder


class PolarizationAnalysisTest(unittest.TestCase):
    def test_simple_load(self):
        """
            REF_M_29160.nxs.h5: 58d6698e1d6bf98e0315687cb980d333
        """
        ws=api.LoadEventNexus(Filename="REF_M_29160")
        _, ratio1, ratio2, asym1, _ = calculate_ratios(ws, delta_wl = 0.05,
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

class FindPeaks(unittest.TestCase):
    def test_peaks(self):
        """
            REF_M_24949_event.nxs.md5: 214df921d4fa70ff5a33c4eb6f8284ad
            http://198.74.56.37/ftp/external-data/md5/%(hash)
        """
        ws=api.LoadEventNexus(Filename='REF_M_24949', OutputWorkspace='REF_M_24949')
        fitter = Fitter(ws, prepare_plot_data=True)
        x, y = fitter.fit_2d_peak()
        api.logger.notice("Found: %s %s" % (str(x), str(y)))
        center_x = np.sum(x)/2.0
        self.assertGreater(center_x, 120)
        self.assertLess(center_x, 130)

class TestReduction(unittest.TestCase):
    def test_reduce(self):
        processor = mr.ReductionProcess(data_run='REF_M_29160', output_dir='.')
        processor.pol_state = 'SF1'
        processor.ana_state = 'SF2'
        processor.pol_veto = ''
        processor.ana_veto = ''
        processor.reduce()

    def test_reduce_with_dirst(self):
        """
             This will excercise a different path in looking for direct beams.
        """
        ws=api.LoadEventNexus(Filename="REF_M_29160")
        finder = DirectBeamFinder(ws)
        finder.data_dir = os.getcwd()
        finder.ar_dir = os.getcwd()
        finder.db_dir = os.getcwd()
        finder.search()

if __name__ == '__main__':
    unittest.main()
