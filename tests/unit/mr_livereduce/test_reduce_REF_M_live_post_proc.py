# third party imports
import pytest

# mr_livereduce imports
from mr_livereduce.reduce_REF_M_live_post_proc import header_report, main, polarization_report, rebin_tof


@pytest.fixture(scope="module")
def accumulation_workspace(data_server):
    """Fixture to pro
    vide the input workspace for testing."""
    ws = data_server.load_events("REF_M_42535.nxs.h5")
    return ws


@pytest.mark.datarepo()
def test_rebin_tof(accumulation_workspace):
    ws = rebin_tof(accumulation_workspace)
    assert ws.getTofMin() < ws.getTofMax(), "Rebinning failed: min TOF should be less than max TOF"


@pytest.mark.datarepo()
def test_header_report(accumulation_workspace):
    report = header_report(accumulation_workspace)
    assert "<div>Run Number: 42535</div>" in report
    assert "<div>Events: 593081</div>" in report
    assert "<div>Sequence: 1 of 4</div>" in report
    assert "<div>Report time:" in report  # Check for the presence of the report time


@pytest.mark.datarepo()
def test_polarization_report(accumulation_workspace, browser):
    report = polarization_report(accumulation_workspace)
    assert "<td>Number of polarization states: 2</td>" in report  # Adjust this check based on actual report content
    assert "Off_Off / On_Off" in report or "On_Off - Off_Off" in report
    assert browser.render_report(report)  # open the report in the headless browser


if __name__ == "__main__":
    pytest.main([__file__])
