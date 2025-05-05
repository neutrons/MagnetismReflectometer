# third-party imports
import pytest
from mantid.simpleapi import LoadNexus, mtd

# mr_reduction imports
from mr_reduction.filter_events import split_events


@pytest.mark.datarepo()
def test_split_events(data_server):
    events = LoadNexus(Filename=data_server.path_to("REF_M_44316.nxs"), OutputWorkspace=mtd.unique_hidden_name())
    workspace_group = split_events(input_workspace=events, output_workspace="44316")
    assert [workspace.getNumberEvents() for workspace in workspace_group] == [289972, 281213]


if __name__ == "__main__":
    pytest.main([__file__])
