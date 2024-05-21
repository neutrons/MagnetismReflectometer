# third party imports
import numpy as np
import pytest
from mantid.simpleapi import LoadEventNexus

# mr_reduction imports
from mr_reduction.data_info import Fitter
from mr_reduction.logging import logger


class TestFindPeaks:
    @pytest.mark.sns_mounted()
    def test_peaks(self):
        """
        REF_M_24949_event.nxs.md5: 214df921d4fa70ff5a33c4eb6f8284ad
        http://198.74.56.37/ftp/external-data/md5/%(hash)
        """
        ws = LoadEventNexus(Filename="/SNS/REF_M/IPTS-21391/nexus/REF_M_29160.nxs.h5", OutputWorkspace="REF_M_29160")
        fitter = Fitter(ws, prepare_plot_data=True)
        x, y = fitter.fit_2d_peak()
        logger.info("Found: %s %s" % (str(x), str(y)))
        center_x = np.sum(x) / 2.0
        assert center_x > 120
        assert center_x < 174


if __name__ == "__main__":
    pytest.main([__file__])
