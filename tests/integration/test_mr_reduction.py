# standard imports
import itertools
import os
import shutil

# mr_reduction imports
import mr_reduction.mr_reduction as mr
import numpy as np

# third party imports
import pytest
from mr_reduction import io_orso


class TestReduction:
    @pytest.mark.datarepo()
    def test_reduce_second_peak(self, mock_filesystem, data_server):
        # direct beam for data run 29137
        mock_filesystem.DirectBeamFinder.return_value.search.return_value = 29137
        processor = mr.ReductionProcess(
            data_run=data_server.path_to("REF_M_29160.nxs.h5"),
            peak_number=2,
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
            "REF_M_29160_2.ort",
            "REF_M_29160_2_combined.ort",
            "REF_M_29160_2_partial.py",
        ]:
            assert os.path.isfile(os.path.join(mock_filesystem.tempdir, file))
        questor = io_orso.Questor(filepath=os.path.join(mock_filesystem.tempdir, "REF_M_29160_2_combined.ort"))
        questor.assert_equal(cross_sections=["Off_Off"], polarizations=["pp"])
        # compare the first two elements of column R of the first dataset to [0.0164, 0.01745]
        questor.assert_almost_equal(decimal=4, partial_match=True, column_R=[[0.0164, 0.01745]])

    @pytest.mark.datarepo()
    def test_reduce_many_cross_sections_1(self, data_server, mock_filesystem):
        r"""
        This run number has events for cross sections Off_Off, On_Off, and On_On.
        There are no other previous numbers in the runs sequence, hence files REF_M_28142_*_autoreduce.dat
        and REF_M_28142_*_combined.dat are basically one and the same
        """
        mock_filesystem.DirectBeamFinder.return_value.search.return_value = None
        processor = mr.ReductionProcess(
            data_run=data_server.path_to("REF_M_28142.nxs.h5"), output_dir=mock_filesystem.tempdir
        )
        processor.pol_state = "SF1"
        processor.ana_state = "SF2"
        processor.pol_veto = ""
        processor.ana_veto = ""
        processor.reduce()
        # assert reduction files have been produced
        for file in [
            "REF_M_28142_Off_Off_autoreduce.dat",
            "REF_M_28142_Off_Off_combined.dat",
            "REF_M_28142_On_Off_autoreduce.dat",
            "REF_M_28142_On_Off_combined.dat",
            "REF_M_28142_On_On_autoreduce.dat",
            "REF_M_28142_On_On_combined.dat",
            "REF_M_28142.ort",
            "REF_M_28142_combined.ort",
            "REF_M_28142_combined.py",
            "REF_M_28142_partial.py",
        ]:
            assert os.path.isfile(os.path.join(mock_filesystem.tempdir, file)), f"File {file} doesn't exist"
        questor = io_orso.Questor(filepath=os.path.join(mock_filesystem.tempdir, "REF_M_28142_combined.ort"))
        questor.assert_equal(cross_sections=["Off_Off", "On_Off", "On_On"], polarizations=["pp", "mp", "mm"])

    @pytest.mark.datarepo()
    def test_check_correct_normalization(self, data_server, mock_filesystem):
        r"""
        This run number has events for cross sections Off_Off, On_Off, and On_On.
        There are no other previous numbers in the runs sequence, hence files REF_M_44382_*_autoreduce.dat
        and REF_M_44382_*_combined.dat are basically one and the same.

        The test checks that the first 20 values of the reflectivity are all similar in value
        """
        mock_filesystem.DirectBeamFinder.return_value.search.return_value = 44380  # normalization run
        processor = mr.ReductionProcess(
            data_run=data_server.path_to("REF_M_44382.nxs.h5"), output_dir=mock_filesystem.tempdir
        )
        processor.reduce()
        # load the On_Off and Off_Off reflectivities, and assert that the first 20 values are similar to each other
        for cross_section in ["On_Off", "Off_Off"]:
            reflectivities = np.loadtxt(
                os.path.join(mock_filesystem.tempdir, f"REF_M_44382_{cross_section}_autoreduce.dat"),
                usecols=1,
                comments="#",
            )
            assert np.all((reflectivities[:18] >= 0.09) & (reflectivities[:18] <= 0.11))

    @pytest.mark.datarepo()
    def test_reduce_many_cross_sections_2(self, mock_filesystem, data_server):
        r"""This run number has events for cross sections Off_Off, On_Off, and On_On
        Previous run numbers 41445 and 41446 are part of the sequence, hence files REF_M_41445_*_combined.dat
        are the result of stiching the autoreduced files from those runs to the profile from 41447
        """
        mock_filesystem.DirectBeamFinder.return_value.search.return_value = 41434

        processor = mr.ReductionProcess(
            data_run=data_server.path_to("REF_M_41447.nxs.h5"),
            output_dir=mock_filesystem.tempdir,  # mocks /SNS/REF_M/IPTS-21391/shared/autoreduce/
            use_sangle=False,
            const_q_binning=False,
            update_peak_range=False,
            peak_number=None,
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
            "REF_M_41447.ort",
            "REF_M_41445_combined.ort",
            "REF_M_41447_partial.py",
            "REF_M_41445_combined.py",
            "REF_M_41447.json",
            "REF_M_41445_Off_Off_combined.dat",
        ]:
            assert os.path.isfile(os.path.join(mock_filesystem.tempdir, file)), f"File {file} doesn't exist"
        questor = io_orso.Questor(filepath=os.path.join(mock_filesystem.tempdir, "REF_M_41447.ort"))
        questor.assert_equal(cross_sections=["Off_Off"], polarizations=["unpolarized"])
        questor.assert_almost_equal(decimal=3, incident_angle=[0.0273])

    @pytest.mark.datarepo()
    def test_reduce_multiple_peaks(self, mock_filesystem, data_server):
        r"""Find a run with two peaks, then reduce each, then paste their reports"""
        mock_filesystem.DirectBeamFinder.return_value.search.return_value = 42534

        # autoreduced files from previous runs, to be stitched to profile from 41447
        for run, suffix in itertools.product(
            ["42535_1", "42535_2", "42536_1", "42536_2"],
            ["_Off_Off_autoreduce.dat", "_On_Off_autoreduce.dat", "_partial.py", ".ort"],
        ):
            source_file = data_server.path_to(f"REF_M_{run}{suffix}")
            shutil.copy(source_file, mock_filesystem.tempdir)

        for peak_number, peak_roi in [(1, [169, 192]), (2, [207, 220])]:
            processor = mr.ReductionProcess(
                data_run=data_server.path_to("REF_M_42537.nxs.h5"),
                peak_number=peak_number,
                output_dir=mock_filesystem.tempdir,  # mocks /SNS/REF_M/IPTS-31954/shared/autoreduce/
                use_sangle=False,
                const_q_binning=False,
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
        for sn in (1, 2):  # peak number
            for suffix in [
                "_Off_Off_autoreduce.dat",
                "_Off_Off_autoreduce.nxs.h5",
                "_On_Off_autoreduce.dat",
                "_On_Off_autoreduce.nxs.h5",
                "_partial.py",
                ".json",
                ".ort",
            ]:
                file = f"REF_M_42537_{sn}{suffix}"
                assert os.path.isfile(os.path.join(mock_filesystem.tempdir, file)), f"{file} doesn't exist"

        # assert combined files have been produced (file names use run 42535 because
        # it's the first in the sequence of experiments encompassing run 42535 through 42538)
        for sn in (1, 2):
            for suffix in [
                "_combined.py",
                "_Off_Off_combined.dat",
                "_On_Off_combined.dat",
                "_combined.ort",
            ]:
                file = f"REF_M_42535_{sn}{suffix}"
                assert os.path.isfile(os.path.join(mock_filesystem.tempdir, file)), f"{file} doesn't exist"
            # inquire the combined ORSO files
            questor = io_orso.Questor(filepath=os.path.join(mock_filesystem.tempdir, f"REF_M_42535_{sn}_combined.ort"))
            questor.assert_equal(cross_sections=["Off_Off", "On_Off"], polarizations=["po", "mo"])


if __name__ == "__main__":
    pytest.main([__file__])
