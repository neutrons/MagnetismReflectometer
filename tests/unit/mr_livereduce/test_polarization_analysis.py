# third party imports
import numpy as np
import pytest
from mantid.simpleapi import LoadEventNexus

# mr_livereduce imports
from mr_livereduce.polarization_analysis import calculate_ratios


class TestPolarizationAnalysis:
    @pytest.mark.datarepo()
    def test_simple_load(self, data_server):
        ws = LoadEventNexus(Filename=data_server.path_to("REF_M_29160.nxs.h5"))
        _, ratio1, ratio2, asym1, _ = calculate_ratios(ws, delta_wl=0.05, roi=[156, 210, 49, 170], slow_filter=True)

        y1 = ratio1.readY(0)
        ref = np.loadtxt(data_server.path_to("r1_29160.txt")).T
        diff = (y1 - ref[1]) ** 2 / ref[2] ** 2
        assert np.sum(diff) / (len(y1) + 1.0) < 0.5

        y1 = ratio2.readY(0)
        ref = np.loadtxt(data_server.path_to("r2_29160.txt")).T
        diff = (y1 - ref[1]) ** 2 / ref[2] ** 2
        assert np.sum(diff) / (len(y1) + 1.0) < 0.5

        y1 = asym1.readY(0)
        ref = np.loadtxt(data_server.path_to("a2_29160.txt")).T
        diff = (y1 - ref[1]) ** 2 / ref[2] ** 2
        assert np.sum(diff) / (len(y1) + 1.0) < 0.5


if __name__ == "__main__":
    pytest.main([__file__])
