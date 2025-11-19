import pytest
from mantid.simpleapi import LoadEventNexus, LoadNexus, mtd
from mantid.utils.logging import capture_logs

from mr_reduction.filter_events import create_table, filter_cross_sections, get_xs_list


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


class TestFilterCrossSections:
    @pytest.mark.datarepo
    def test_filter(self, data_server):
        """
        Test the function that split events according to the concurrent cross section,
        using a run with logs containing entries with a time stamp that predates the start time or the run.
        """
        workspace = LoadNexus(
            Filename=data_server.path_to("REF_M_44316.nxs"), OutputWorkspace=mtd.unique_hidden_name()
        )
        workspace_group = filter_cross_sections(workspace, output_workspace="44316")
        assert list(workspace_group.getNames()) == ["44316_Off_Off", "44316_On_Off"]
        assert [workspace.getNumberEvents() for workspace in workspace_group] == [289972, 281213]

    @pytest.mark.datarepo
    def test_no_veto_logs(self, data_server):
        workspace = LoadEventNexus(
            Filename=data_server.path_to("REF_M_45129.nxs.h5"), OutputWorkspace=mtd.unique_hidden_name()
        )
        with capture_logs(level="warning") as messages:
            filter_cross_sections(workspace, output_workspace="45129")
            assert "Polarizer veto log 'SF1_Veto' not found in sample logs" in messages.getvalue()


class TestCrossSectionList:
    @pytest.mark.datarepo
    def test_get_xs_list_from_workspace(self, data_server):
        """
        Test the function that retrieves the list of cross sections from a mantid workspace.
        """
        workspace = LoadEventNexus(
            Filename=data_server.path_to("REF_M_44380.nxs.h5"), OutputWorkspace=mtd.unique_hidden_name()
        )
        # run_number, xs_list = get_xs_list(input_workspace=workspace, min_event_count=100)
        xs_list = get_xs_list(input_workspace=workspace, min_event_count=100)
        run_number = int(workspace.getRunNumber())
        assert list(xs_list.getNames()) == [f"{run_number}_Off_Off"]

    @pytest.mark.datarepo
    def test_get_xs_list_from_filename(self, data_server):
        """
        Test the function that retrieves the list of cross sections from a nexus file.
        """
        # run_number, xs_list = get_xs_list(file_path=data_server.path_to("REF_M_44380.nxs.h5"), min_event_count=100)
        xs_list = get_xs_list(file_path=data_server.path_to("REF_M_44380.nxs.h5"), min_event_count=100)
        run_number = xs_list[0].getRunNumber()
        assert list(xs_list.getNames()) == [f"{run_number}_Off_Off"]

    @pytest.mark.datarepo
    def test_get_xs_list_legacy(self, data_server):
        """
        Test the function that retrieves the list of cross sections from a legacy nexus file.
        """
        xs_list = get_xs_list(file_path=data_server.path_to("REF_M_24945_event.nxs"))
        assert list(xs_list.getNames()) == [
            "REF_M_24945_event.nxs_Off_Off",
            "REF_M_24945_event.nxs_On_Off",
            "REF_M_24945_event.nxs_Off_On",
            "REF_M_24945_event.nxs_On_On",
        ]

    @pytest.mark.datarepo
    def test_get_xs_list_invalid_args(self):
        """
        Test the function that retrieves the list of cross sections with invalid arguments.
        """
        with pytest.raises(ValueError, match="Either 'file_path' or 'input_workspace' must be provided"):
            get_xs_list()


if __name__ == "__main__":
    pytest.main([__file__])
