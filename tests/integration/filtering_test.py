"""
Simple script to run the automated reduction on a data file
"""

# standard imports
import itertools
import os

# mr_reduction imports
import mr_reduction.mr_reduction as mr

# third party packages
import pytest


@pytest.mark.datarepo()
def test_reduction_with_filtering(data_server, mock_filesystem):
    adara_file = data_server.path_to("REF_M_28142.nxs.h5")
    mock_filesystem.DirectBeamFinder.return_value.search.return_value = None
    processor = mr.ReductionProcess(data_run=adara_file, output_dir=mock_filesystem.tempdir)
    processor.pol_state = "SF1"
    processor.ana_state = "SF2"
    processor.pol_veto = ""
    processor.ana_veto = ""
    processor.reduce()
    # assert reduction files have been produced
    for x, f in itertools.product(["Off_Off", "On_Off", "On_On"], ["autoreduce", "combined"]):
        filepath = os.path.join(mock_filesystem.tempdir, f"REF_M_28142_{x}_{f}.dat")
        assert os.path.isfile(filepath)
    for f in ["combined", "partial", "tunable_combined"]:
        filepath = os.path.join(mock_filesystem.tempdir, f"REF_M_28142_{f}.py")
        assert os.path.isfile(filepath)


if __name__ == "__main__":
    pytest.main([__file__])
