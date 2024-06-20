# standard imports
import itertools
import os
import shutil
from unittest import mock

# mr_reduction imports
import mr_reduction.mr_reduction as mr

# third party imports
import pytest


class TestReduction:
    @pytest.mark.datarepo()
    def test_reduce(self, mock_filesystem, data_server):
        mock_filesystem.DirectBeamFinder.return_value.search.return_value = 29137
        processor = mr.ReductionProcess(
            data_run=data_server.path_to("REF_M_29160.nxs.h5"),
            sample_number=2,
            output_dir=mock_filesystem.tempdir,
            publish=False,  # don't upload to the livedata server
        )
        processor.pol_state = "SF1"
        processor.ana_state = "SF2"
        processor.pol_veto = ""
        processor.ana_veto = ""
        processor.reduce()
        # assert reduction files have been produced
        for file in [
            "REF_M_29160_2_combined.py",
            "REF_M_29160_2.json",
            "REF_M_29160_2_Off_Off_autoreduce.dat",
            "REF_M_29160_2_Off_Off_autoreduce.nxs.h5",
            "REF_M_29160_2_Off_Off_combined.dat",
            "REF_M_29160_2_partial.py",
            "REF_M_29160_2_tunable_combined.py",
        ]:
            assert os.path.isfile(os.path.join(mock_filesystem.tempdir, file))

    @pytest.mark.datarepo()
    def test_reduce_nany_cross_sections(self, mock_filesystem, data_server):
        r"""This run number has events for three different cross sections"""
        mock_filesystem.DirectBeamFinder.return_value.search.return_value = 41434

        processor = mr.ReductionProcess(
            data_run=data_server.path_to("REF_M_41447.nxs.h5"),
            sample_number=None,
            output_dir=mock_filesystem.tempdir,  # mocks /SNS/REF_M/IPTS-21391/shared/autoreduce/
            use_sangle=False,
            const_q_binning=False,
            const_q_cutoff=None,
            update_peak_range=False,
            use_roi=True,
            use_roi_bck=False,
            q_step=-0.022,
            force_peak_roi=True,
            peak_roi=[149, 159],
            force_bck_roi=True,
            bck_roi=[28, 80],
            use_tight_bck=False,
            bck_offset=10,
            publish=False,  # don't upload to the livedata server
        )
        processor.plot_2d = True

        # autoreduced files from previous runs, to be stitched to profile from 41447
        for run, suffix in itertools.product([41445, 41446], ["Off_Off_autoreduce.dat", "partial.py"]):
            source_file = data_server.path_to(f"REF_M_{run}_{suffix}")
            shutil.copy(source_file, mock_filesystem.tempdir)

        # reduce run 41447
        processor.reduce()

        # assert reduction files have been produced
        for file in [
            "REF_M_41447_Off_Off_autoreduce.dat",
            "REF_M_41447_Off_Off_autoreduce.nxs.h5",
            "REF_M_41447_partial.py",
            "REF_M_41445_combined.py",
            "REF_M_41447.json",
            "REF_M_41445_Off_Off_combined.dat",
            "REF_M_41445_tunable_combined.py",
        ]:
            assert os.path.isfile(os.path.join(mock_filesystem.tempdir, file)), "File {file} doesn't exist"

    @pytest.mark.datarepo()
    def test_reduce_multiple_samples(self):
        r"""Find a run with two samples, then reduce each, then paste their reports"""

        """
        Assert existence of files for each sample
        """
        pass


if __name__ == "__main__":
    pytest.main([__file__])
