# third-party imports
import pytest
from mantid.simpleapi import LoadNexus, mtd

# mr_reduction imports
from mr_reduction.filter_events import MRFilterCrossSections
from mr_reduction.settings import ANA_STATE, ANA_VETO, POL_STATE, POL_VETO
from mr_reduction.simple_utils import run_mantid_algorithm


@pytest.mark.datarepo()
def test_MRFilterCrossSections(data_server):
    workspace = LoadNexus(Filename=data_server.path_to("REF_M_44316.nxs"), OutputWorkspace=mtd.unique_hidden_name())
    workspace_group = run_mantid_algorithm(
        MRFilterCrossSections,
        output_property="CrossSectionWorkspaces",
        InputWorkspace=workspace,
        PolState=POL_STATE,
        PolVeto=POL_VETO,
        AnaState=ANA_STATE,
        AnaVeto=ANA_VETO,
        CrossSectionWorkspaces="44316",
    )
    assert [workspace.getNumberEvents() for workspace in workspace_group] == [289972, 281213]


if __name__ == "__main__":
    pytest.main([__file__])
