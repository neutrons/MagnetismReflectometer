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
    def test_reduce_multiple_samples(self, mock_filesystem, data_server):
        r"""Find a run with two samples, then reduce each, then paste their reports"""
        # Reduce the two samples for 42535 to produce autoreduction files that will be stored in datarepo

        # Reduce the two samples for 42536, which will need the autoreduction files previously stored in the datarepo

        mock_filesystem.DirectBeamFinder.return_value.search.return_value = 42534

        # autoreduced files from previous runs, to be stitched to profile from 41447
        for run, suffix in itertools.product(
            ["42535_1", "42535_2", "42536_1", "42536_2"],
            ["Off_Off_autoreduce.dat", "On_Off_autoreduce.dat", "partial.py"],
        ):
            source_file = data_server.path_to(f"REF_M_{run}_{suffix}")
            shutil.copy(source_file, mock_filesystem.tempdir)

        for sample_number, peak_roi in [(1, [169, 192]), (2, [207, 220])]:
            processor = mr.ReductionProcess(
                data_run=data_server.path_to("REF_M_42537.nxs.h5"),
                sample_number=sample_number,
                output_dir=mock_filesystem.tempdir,  # mocks /SNS/REF_M/IPTS-31954/shared/autoreduce/
                use_sangle=False,
                const_q_binning=False,
                const_q_cutoff=None,
                update_peak_range=False,
                use_roi=True,
                use_roi_bck=False,
                q_step=-0.022,
                force_peak_roi=True,
                peak_roi=peak_roi,
                force_bck_roi=True,
                bck_roi=[30, 70],
                use_tight_bck=False,
                bck_offset=10,
                publish=False,  # don't upload to the livedata server
            )
            processor.plot_2d = True
            processor.reduce()
        # assert reduction files have been produced for run 42537

        for sn in (1, 2):  # sample number
            for suffix in [
                "_Off_Off_autoreduce.dat",
                "_Off_Off_autoreduce.nxs.h5",
                "_On_Off_autoreduce.dat",
                "_On_Off_autoreduce.nxs.h5",
                "_partial.py",
                ".json",
            ]:
                file = f"REF_M_42537_{sn}{suffix}"
                assert os.path.isfile(os.path.join(mock_filesystem.tempdir, file)), f"{file} doesn't exist"

        # assert stitched files have been produced (file names use run 42535 because
        # it's the first in the sequence of experiments encompassing run 42535 through 42538)
        for sn in (1, 2):
            for suffix in ["_combined.py", "_Off_Off_combined.dat", "_On_Off_combined.dat", "_tunable_combined.py"]:
                file = f"REF_M_42535_{sn}{suffix}"
                assert os.path.isfile(os.path.join(mock_filesystem.tempdir, file)), f"{file} doesn't exist"


if __name__ == "__main__":
    pytest.main([__file__])
