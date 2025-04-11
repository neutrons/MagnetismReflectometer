# standard imports
import itertools
import os
import shutil
import string

# third party imports
import pytest

# mr_reduction imports
from mr_reduction.simple_utils import add_to_sys_path


@pytest.mark.datarepo()
def test_template(mock_filesystem, data_server, autoreduction_script):
    r"""Substitute values in the template and then run a reduction using functions defined within the template

    Ideally, one would like to open a subprocess and invoke the reduction script, but it's not possible because
    we need to mock the file system. A new subprocess will "lose" the mock since it's a new python instance.
    """

    #
    # Gather all necessary auxiliary files for reduction of run 42537, which is the third run in the sequence
    # of runs that begins with run 42535.
    #
    # direct beam for data run 42537
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
    reduction_script = autoreduction_script()

    # We don't invoke the reduction script as a shell command because we need mock_filesystem.
    # Instead, we import functions from it
    with add_to_sys_path(os.path.dirname(reduction_script)):
        from reduce_REF_M import reduce_events_file, upload_html_report  # script being used as a module

        events_file = data_server.path_to("REF_M_42537.nxs.h5")
        outdir = mock_filesystem.tempdir  # instead of /SNS/IPTS-31954/shared/autoreduce/
        reports = reduce_events_file(events_file, outdir)  # reduce the two peaks and generate HTML reports
        report_file = os.path.join(mock_filesystem.tempdir, "report.html")
        upload_html_report(reports, publish=False, report_file=report_file)  # save reports to a files

    # assert the HTML report has been created
    assert os.path.isfile(report_file)

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
        for suffix in ["_combined.py", "_Off_Off_combined.dat", "_On_Off_combined.dat", "_tunable_combined.py"]:
            file = f"REF_M_42535_{sn}{suffix}"
            assert os.path.isfile(os.path.join(mock_filesystem.tempdir, file)), f"{file} doesn't exist"


if __name__ == "__main__":
    pytest.main([__file__])
