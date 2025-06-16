"""
This module contains integration tests for the reduction of a REF_M run containing two peaks.
The main test, `test_reduce_REF_M_run`, verifies the reduction process for run 41447 by:
1. Setting up mock filesystem and data server.
2. Gathering necessary auxiliary files for the reduction.
3. Defining reduction options for multiple peaks.
4. Adding the path to the reduction script to the system path.
5. Running the reduction script as a module.
6. Asserting the creation of the HTML report and reduction files.
7. Asserting the creation of stitched files from multiple runs.
"""

# standard imports
import itertools
import os
import shutil

# third party imports
import pytest

# mr_reduction imports
from mr_reduction.simple_utils import add_to_sys_path


@pytest.mark.datarepo
def test_reduce_REF_M_run(mock_filesystem, data_server):
    #
    # Gather all necessary auxiliary files for reduction of run 42537
    #
    # direct beam for data run 41447
    mock_filesystem.DirectBeamFinder.return_value.search.return_value = 42534
    # autoreduced files from previous runs, to be stitched to profile from 42537
    for run, suffix in itertools.product(
        ["42535_1", "42535_2", "42536_1", "42536_2"],
        ["Off_Off_autoreduce.dat", "On_Off_autoreduce.dat", "partial.py"],
    ):
        source_file = data_server.path_to(f"REF_M_{run}_{suffix}")
        shutil.copy(source_file, mock_filesystem.tempdir)

    #
    # Options to reduce the two peaks of run 41447
    #
    common = {  # options for all peaks
        "use_const_q": False,
        "q_step": -0.022,
        "use_sangle": False,
        "fit_peak_in_roi": False,
        "peak_count": 2,  # run 42537 has two peaks
    }
    # Options for first peak
    peak1 = {
        "force_peak": True,
        "peak_min": 169,
        "peak_max": 192,
        "use_roi_bck": False,
        "force_background": True,
        "bck_min": 30,
        "bck_max": 70,
        "use_side_bck": False,
        "bck_width": 10,
        "force_low_res": False,
        "low_res_min": 50,
        "low_res_max": 175,
    }
    # Options for second peak
    peak2 = {
        "force_peak_s2": True,
        "peak_min_s2": 207,
        "peak_max_s2": 220,
        "use_roi_bck_s2": False,
        "force_background_s2": False,
        "bck_min_s2": 30,
        "bck_max_s2": 70,
        "use_side_bck_s2": False,
        "bck_width_s2": 11,
        "force_low_res_s2": False,
        "low_res_min_s2": 50,
        "low_res_max_s2": 175,
    }
    # Options for third peak (will be ignored because `peak_count` is 2)
    peak3 = {
        "force_peak_s3": True,
        "peak_min_s3": 180,
        "peak_max_s3": 190,
        "use_roi_bck_s3": False,
        "force_background_s3": True,
        "bck_min_s3": 7,
        "bck_max_s3": 102,
        "use_side_bck_s3": False,
        "bck_width_s3": 12,
        "force_low_res_s3": False,
        "low_res_min_s3": 50,
        "low_res_max_s3": 175,
    }
    values = {**common, **peak1, **peak2, **peak3}  # all options into one dictionary
    values["events_file"] = data_server.path_to("REF_M_42537.nxs.h5")
    values["outdir"] = mock_filesystem.tempdir

    # folder "autoreduce/" is not part of package `mr_reduction` so we need to add its path
    # Ideally, one would like to open a subprocess and invoke the reduction script, but it's not possible because
    # we need to mock the file system. A new subprocess will "lose" the mock since it's a new python instance.

    with add_to_sys_path(os.path.dirname(data_server.path_to_template)):
        from reduce_REF_M_run import reduce_single_run, run_number  # use script as module

        reduce_single_run(values)

    # assert the HTML report has been created
    assert os.path.isfile(os.path.join(mock_filesystem.tempdir, f"REF_M_{run_number(values['events_file'])}.html"))

    # assert reduction files have been produced for run 42537
    for sn in (1, 2):  # peak number
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

    # assert stitched files have been produced (file names use run 42535 because this is
    # the first in the sequence of experiments encompassing run 42535 through 42538)
    for sn in (1, 2):
        for suffix in ["_combined.py", "_Off_Off_combined.dat", "_On_Off_combined.dat"]:
            file = f"REF_M_42535_{sn}{suffix}"
            assert os.path.isfile(os.path.join(mock_filesystem.tempdir, file)), f"{file} doesn't exist"


if __name__ == "__main__":
    pytest.main([__file__])
