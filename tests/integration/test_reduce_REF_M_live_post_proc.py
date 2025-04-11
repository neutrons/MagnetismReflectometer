# standard imports
import itertools
import os
import shutil
import unittest.mock as mock

# third party imports
import pytest
from mr_livereduce.reduce_REF_M_live_post_proc import main


@pytest.mark.datarepo()
def test_main(mock_filesystem, data_server, browser, autoreduction_script):
    r"""Substitute values in the template and then run a reduction using functions defined within the template

    Ideally, one would like to open a subprocess and invoke the reduction script, but it's not possible because
    we need to mock the file system. A new subprocess will "lose" the mock since it's a new python instance.
    """

    #
    # Gather all necessary auxiliary files for reduction of run 42537, which is the third run in the sequence
    # of runs that begins with run 42535.
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

    # Create a temporary autoreduction script reduce_REF_M.py and pass its parent directory to PYTHONPATH.
    # The default options in this script are good for reducing the two peaks of run 41447.
    autoreduction_script(outdir=mock_filesystem.tempdir)

    #
    # Invoke the main routine of the livereduction script. It will digest the autoreduction script
    # reduce_REF_M.py we just created
    #
    accumulation_workspace = data_server.load_events("REF_M_42537.nxs.h5")
    report_file = os.path.join(mock_filesystem.tempdir, "report.html")  # HTML report file
    with mock.patch("mr_livereduce.reduce_REF_M_live_post_proc.GLOBAL_AR_DIR", mock_filesystem.tempdir):
        with mock.patch("mr_livereduce.reduce_REF_M_live_post_proc.GLOBAL_LR_DIR", mock_filesystem.tempdir):
            main(
                accumulation_workspace,
                outdir=mock_filesystem.tempdir,  # instead of /SNS/IPTS-31954/shared/autoreduce/
                publish=False,  # don't upload the HTML report to the livedata server
                report_file=report_file,
            )

    #
    # Check the results of the livereduction
    #

    # assert the HTML report can be rendered by a headless Chromium browser
    browser.get(f"file://{report_file}")

    # assert reduction files have been produced for run 42537
    for peak_number in (1, 2):
        for suffix in [
            "_Off_Off_autoreduce.dat",
            "_Off_Off_autoreduce.nxs.h5",
            "_On_Off_autoreduce.dat",
            "_On_Off_autoreduce.nxs.h5",
            ".ort",  # ORSO ASCII format
            "_partial.py",
            ".json",
        ]:
            file = f"REF_M_42537_{peak_number}{suffix}"
            assert os.path.isfile(os.path.join(mock_filesystem.tempdir, file)), f"{file} doesn't exist"

    # assert stitched files have been produced (file names use run 42535 because this is
    # the first in the sequence of experiments encompassing run 42535 through 42538)
    for peak_number in (1, 2):
        for suffix in [
            "_combined.py",
            "_Off_Off_combined.dat",
            "_On_Off_combined.dat",
            "_combined.ort",  # ORSO ASCII format
            "_tunable_combined.py",
        ]:
            file = f"REF_M_42535_{peak_number}{suffix}"
            assert os.path.isfile(os.path.join(mock_filesystem.tempdir, file)), f"{file} doesn't exist"


if __name__ == "__main__":
    pytest.main([__file__])
