import pytest
from mantid.simpleapi import LoadNexus, mtd

from mr_reduction.filter_events import get_xs_list


@pytest.mark.datarepo
def test_get_xs_list(data_server):
    events = LoadNexus(Filename=data_server.path_to("REF_M_44316.nxs"), OutputWorkspace=mtd.unique_hidden_name())
    workspace_group = get_xs_list(input_workspace=events, output_workspace="44316")
    assert [workspace.getNumberEvents() for workspace in workspace_group] == [289972, 281213]


if __name__ == "__main__":
    pytest.main([__file__])
