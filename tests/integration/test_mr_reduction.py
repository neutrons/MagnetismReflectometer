# third party packages
# mr_reduction imports
import mr_reduction.mr_reduction as mr
import pytest


class TestReduction:
    @pytest.mark.sns_mounted()
    def test_reduce(self, tempdir: str):
        processor = mr.ReductionProcess(data_run="/SNS/REF_M/IPTS-21391/nexus/REF_M_29160.nxs.h5", output_dir=tempdir)
        processor.pol_state = "SF1"
        processor.ana_state = "SF2"
        processor.pol_veto = ""
        processor.ana_veto = ""
        processor.reduce()


if __name__ == "__main__":
    pytest.main([__file__])
