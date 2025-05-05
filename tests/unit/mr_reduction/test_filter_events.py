# third-party imports
import pytest
from mantid.simpleapi import LoadNexus, mtd

# mr_reduction imports
from mr_reduction.filter_events import create_table, filter_cross_sections
from mr_reduction.settings import ANA_STATE, ANA_VETO, POL_STATE, POL_VETO


def test_create_table():
    """
    Test the creation of a table with input of a list containing an item (the first item)
    with a time stamp that predates the start time.
    """
    changes = [
        (1114103915483902567, False, [True, False, False, False]),
        (1114104949939068067, True, [False, False, True, False]),
        (1114104949966130867, True, [True, False, False, False]),
        (1114104949966130867, True, [True, False, False, False]),
        (1114104949968047467, False, [False, False, True, False]),
        (1114105024775176867, True, [False, False, True, False]),
        (1114105024785293967, False, [True, False, False, False]),
        (1114105024785293967, False, [True, False, False, False]),
        (1114105024785295267, False, [False, False, True, False]),
    ]
    table = create_table(changes, start_time=1114104876000000000, has_polarizer=True, has_analyzer=False)
    assert table.row(0) == {
        "start": pytest.approx(0.0, abs=0.1),
        "stop": pytest.approx(73.9, abs=0.1),
        "target": "Off_Off",
    }


@pytest.mark.datarepo()
def test_filter_cross_sections(data_server):
    """
    Test the function that split events according to the concurrent cross section,
    using a run with logs containing entries with a time stamp that predates the start time or the run.
    """
    workspace = LoadNexus(Filename=data_server.path_to("REF_M_44316.nxs"), OutputWorkspace=mtd.unique_hidden_name())
    workspace_group = filter_cross_sections(workspace, output_workspace="44316")
    assert list(workspace_group.getNames()) == ["44316_Off_Off", "44316_On_Off"]
    assert [workspace.getNumberEvents() for workspace in workspace_group] == [289972, 281213]


if __name__ == "__main__":
    pytest.main([__file__])
