# third party packages
import pytest
from mantid.simpleapi import LoadEventNexus

# mr_reduction imports
from mr_reduction.mr_direct_beam_finder import DirectBeamFinder


class TestDirectBeamFinder:
    @pytest.mark.sns_mounted()
    def test_reduce_with_dirst(self, tempdir: str):
        """
        This will excercise a different path in looking for direct beams.
        """
        ws = LoadEventNexus(Filename="/SNS/REF_M/IPTS-21391/nexus/REF_M_29160.nxs.h5")
        finder = DirectBeamFinder(ws)
        finder.data_dir = tempdir
        finder.ar_dir = tempdir
        finder.db_dir = tempdir
        finder.search()


if __name__ == "__main__":
    pytest.main([__file__])
