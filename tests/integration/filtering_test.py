"""
Simple script to run the automated reduction on a data file
"""

# standard imports
import os

# mr_reduction imports
import mr_reduction.mr_reduction as mr

# third party packages
import pytest


@pytest.mark.sns_mounted()
def test_reduction_with_filtering():
    data_dir = "/SNS/REF_M/shared/ADARA.Test.Data.2018"

    adara_file = os.path.join(data_dir, "REF_M_28142.nxs.h5")
    # trans_file = os.path.join(data_dir, "translation_output/REF_M_28142_event.nxs")
    # legacy_file = "/SNS/REF_M/IPTS-18659/0/28142/NeXus/REF_M_28142_event.nxs"

    processor = mr.ReductionProcess(data_run=adara_file, output_dir=".")
    processor.pol_state = "SF1"
    processor.ana_state = "SF2"
    processor.pol_veto = ""
    processor.ana_veto = ""
    processor.reduce()


if __name__ == "__main__":
    pytest.main([__file__])
