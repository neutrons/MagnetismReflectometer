# third party imports
from distutils.dep_util import newer_pairwise

import pytest

# mr_livereduce imports
from mr_livereduce.reduce_REF_M_live_post_proc import debug_logger, header_report, polarization_report, rebin_tof


@pytest.fixture(scope="module")
def accumulation_workspace(data_server):
    """Fixture to pro
    vide the input workspace for testing."""
    ws = data_server.load_events("REF_M_42535.nxs.h5")
    return ws


def test_debug_logger(tmp_path):
    # Create a temporary log file path
    log_file_path = tmp_path / "test_log.log"

    # Use the debug_logger context manager
    with debug_logger(logpath=str(log_file_path), debug=True) as logfile:
        assert logfile is not None  # Ensure the logfile is opened
        logfile.write("Test log entry\n")

    # Verify the log file content
    with open(log_file_path, "r") as log_file:
        content = log_file.read()
        assert "Starting post-proc" in content
        assert "Test log entry" in content
        assert "DONE" in content

    # Ensure the log file is closed
    assert logfile.closed


@pytest.mark.datarepo()
def test_rebin_tof(accumulation_workspace):
    ws = rebin_tof(accumulation_workspace)
    assert ws.getTofMin() < ws.getTofMax(), "Rebinning failed: min TOF should be less than max TOF"


def test_header_report(accumulation_workspace):
    report = header_report(accumulation_workspace)
    assert "<div>Run Number: 42535</div>" in report
    assert "<div>Events: 593081</div>" in report
    assert "<div>Sequence: 1 of 4</div>" in report
    assert "<div>Report time:" in report  # Check for the presence of the report time


def test_polarization_report(accumulation_workspace, browser):
    report = polarization_report(accumulation_workspace)
    assert "<td>Number of polarization states: 2</td>" in report  # Adjust this check based on actual report content
    assert "Off_Off / On_Off" in report or "On_Off - Off_Off" in report
    assert browser.render_report(report)  # open the report in the headless browser


if __name__ == "__main__":
    pytest.main([__file__])
