# third party packages
# mr_reduction imports
import mr_reduction.mr_reduction as mr
import pytest


class TestReduction:
    @pytest.mark.datarepo()
    def test_reduce(self, data_server, tempdir: str):
        processor = mr.ReductionProcess(data_run=data_server.path_to("REF_M_29160.nxs.h5"), output_dir=tempdir)
        processor.pol_state = "SF1"
        processor.ana_state = "SF2"
        processor.pol_veto = ""
        processor.ana_veto = ""
        processor.reduce()


if __name__ == "__main__":
    pytest.main([__file__])
