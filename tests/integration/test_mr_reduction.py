# standard imports
import os

# mr_reduction imports
import mr_reduction.mr_reduction as mr

# third party imports
import pytest


class TestReduction:
    @pytest.mark.datarepo()
    def test_reduce(self, mock_filesystem, data_server):
        mock_filesystem.DirectBeamFinder.return_value.search.return_value = 29137
        processor = mr.ReductionProcess(
            data_run=data_server.path_to("REF_M_29160.nxs.h5"), output_dir=mock_filesystem.tempdir
        )
        processor.pol_state = "SF1"
        processor.ana_state = "SF2"
        processor.pol_veto = ""
        processor.ana_veto = ""
        processor.reduce()
        for file in [
            "REF_M_29160_combined.py",
            "REF_M_29160.json",
            "REF_M_29160_Off_Off_autoreduce.dat",
            "REF_M_29160_Off_Off_autoreduce.nxs.h5",
            "REF_M_29160_Off_Off_combined.dat",
            "REF_M_29160_partial.py",
            "REF_M_29160_tunable_combined.py",
        ]:
            assert os.path.isfile(os.path.join(mock_filesystem.tempdir, file))


if __name__ == "__main__":
    pytest.main([__file__])
