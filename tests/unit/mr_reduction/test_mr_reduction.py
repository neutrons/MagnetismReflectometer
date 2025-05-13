import numpy as np
import pytest
from mantid.simpleapi import DeleteWorkspace, LoadEventNexus, mtd

from mr_reduction.data_info import Fitter2


@pytest.fixture(scope="module")
def workspace(data_server):
    workspace_name = mtd.unique_hidden_name()
    LoadEventNexus(Filename=data_server.path_to("REF_M_29160.nxs.h5"), OutputWorkspace=workspace_name)
    yield workspace_name
    DeleteWorkspace(workspace_name)


@pytest.fixture(scope="module")
def workspace_39012(data_server):
    workspace_name = mtd.unique_hidden_name()
    LoadEventNexus(Filename=data_server.path_to("REF_M_39012.nxs.h5"), OutputWorkspace=workspace_name)
    yield workspace_name
    DeleteWorkspace(workspace_name)


class TestFindPeaks:
    def is_within_range(self, contained, container):
        return container[0] <= contained[0] < contained[1] <= container[1]

    @pytest.mark.datarepo
    def test_peaks(self, workspace):
        fitter = Fitter2(workspace)
        x, y = fitter.fit_2d_peak()
        center_x = np.sum(x) / 2.0
        assert 168 < center_x < 180

    @pytest.mark.datarepo
    def test_peak_with_constraints(self, workspace, workspace_39012):
        fitter = Fitter2(workspace)

        [x_min, x_max], [y_min, y_max] = fitter.fit_2d_peak(x_range=[165, 185], y_range=[70, 155])
        assert self.is_within_range([x_min, x_max], [165, 185])
        assert self.is_within_range([y_min, y_max], [70, 155])

        [x_min, x_max], [y_min, y_max] = fitter.fit_2d_peak(x_range=[250, 275], y_range=[70, 110])
        assert self.is_within_range([x_min, x_max], [250, 275])
        assert self.is_within_range([y_min, y_max], [70, 110])

        [x_min, x_max], [y_min, y_max] = fitter.fit_2d_peak(x_range=[250, 270], y_range=[135, 155])
        assert self.is_within_range([x_min, x_max], [250, 275])
        assert self.is_within_range([y_min, y_max], [135, 155])

        fitter = Fitter2(workspace_39012)
        [x_min, x_max], [y_min, y_max] = fitter.fit_2d_peak(x_range=[140, 160], y_range=[70, 130])
        assert self.is_within_range([x_min, x_max], [140, 160])
        assert self.is_within_range([y_min, y_max], [70, 130])

        fitter = Fitter2(workspace_39012)
        [x_min, x_max], [y_min, y_max] = fitter.fit_2d_peak(x_range=[140, 160], y_range=[140, 190])
        assert self.is_within_range([x_min, x_max], [140, 160])
        assert self.is_within_range([y_min, y_max], [140, 190])


if __name__ == "__main__":
    pytest.main([__file__])
