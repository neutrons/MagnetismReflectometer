from unittest.mock import MagicMock

import mantid.simpleapi as api
import pytest

import mr_reduction.dead_time_correction as dtc
from mr_reduction.mantid_algorithm_utils import mantid_algorithm_exec


@pytest.mark.datarepo
def test_apply_dead_time_correction(monkeypatch, data_server, temp_workspace_name):
    # load event workspace
    ws = api.LoadEventNexus(Filename=data_server.path_to("REF_M_44382.nxs.h5"), OutputWorkspace=temp_workspace_name())
    number_events = ws.getNumberEvents()

    # create correction workspace to return from mock deadtime correction
    correction_factor = 2.5
    tof_min = ws.getTofMin()
    tof_max = ws.getTofMax()
    corr_ws = api.CreateWorkspace(DataX=[tof_min, tof_max], DataY=[2.5], OutputWorkspace=temp_workspace_name())
    mock_mantid_exec = MagicMock(return_value=corr_ws)
    monkeypatch.setattr(dtc, "mantid_algorithm_exec", mock_mantid_exec)

    # apply deadtime correction to the workspace
    dtc.apply_dead_time_correction(ws, paralyzable_deadtime=True, deadtime_value=4.2, deadtime_tof_step=100.0)

    # verify that the events have been weighted
    ws_sum = api.SumSpectra(InputWorkspace=ws)
    assert ws_sum.readY(0).sum() == pytest.approx(correction_factor * number_events)
    assert "dead_time_applied" in ws.getRun().keys()


@pytest.mark.datarepo
@pytest.mark.parametrize(
    ("is_paralyzable", "load_error_events", "sum_expected"),
    [
        (False, False, 334.571733),
        (True, False, 334.572514),
        (False, True, 334.710516),
    ],
)
def test_single_readout_deadtime_correction(
    is_paralyzable, load_error_events, sum_expected, data_server, temp_workspace_name
):
    """Test of the dead-time correction algorithm SingleReadoutDeadTimeCorrection."""
    ws = api.LoadEventNexus(Filename=data_server.path_to("REF_M_44382.nxs.h5"), OutputWorkspace=temp_workspace_name())

    ws_error_events = None
    if load_error_events:
        ws_error_events = api.LoadErrorEventsNexus(
            Filename=data_server.path_to("REF_M_44382.nxs.h5"), OutputWorkspace=temp_workspace_name()
        )

    corr_ws = mantid_algorithm_exec(
        dtc.SingleReadoutDeadTimeCorrection,
        InputWorkspace=ws,
        InputErrorEventsWorkspace=ws_error_events,
        Paralyzable=is_paralyzable,
        OutputWorkspace="dead_time_corr",
    )
    sum_actual = corr_ws.readY(0).sum()
    assert sum_actual == pytest.approx(sum_expected)
