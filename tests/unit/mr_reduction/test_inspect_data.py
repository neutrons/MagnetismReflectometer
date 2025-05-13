from unittest.mock import MagicMock, patch

import pytest

from mr_reduction.inspect_data import DataInspector


class TestDataInspector:
    @patch("mr_reduction.inspect_data.workspace_handle")
    @pytest.mark.parametrize(
        "startx, sizex, starty, sizey, roi2_startx, roi2_sizex, peak, low_res, background",  # noqa PT006
        [
            # Case 1: ROI1 [100, 150] inside ROI2 [90, 160]
            (100, 50, 10, 90, 90, 70, [100, 150], [10, 100], [90, 160]),
            # Case 2: ROI2 [10, 20] occurs at lower values than ROI1 [100, 150]
            (100, 50, 10, 90, 10, 10, [100, 150], [10, 100], [10, 20]),
            # invalid: ROI2 [200, 220] occurs at higher values than ROI1 [100, 150]
            (100, 50, 10, 90, 200, 20, [100, 150], [10, 100], [0, 0]),
            # invalid: ROI2 [110, 130] inside ROI1 [100, 150]
            (100, 50, 10, 90, 110, 20, [100, 150], [10, 100], [0, 0]),
            # invalid: ROI2 [110, 210] starts inside ROI1 [100, 150]
            (100, 50, 10, 90, 110, 100, [100, 150], [10, 100], [0, 0]),
            # invalide: ROI2 [90, 110] ends inside ROI1 [100, 150]
            (100, 50, 10, 90, 90, 20, [100, 150], [10, 100], [0, 0]),
        ],
    )
    def test_process_pv_roi(
        self,
        mock_workspace_handle,
        startx,
        sizex,
        starty,
        sizey,
        roi2_startx,
        roi2_sizex,
        peak,
        low_res,
        background,
    ):
        """
        Test scenarios for DataInspector's `process_pv_roi` method.

        The test cases focus on validating a variety of Region of Interest (ROI) configurations
        and how the `process_pv_roi` method interprets and processes them. Mock
        objects and parameterized data are used to simulate input workspaces and
        expected results.
        """

        class MockDataInspector(DataInspector):
            # a simplified __init__ prevents all the work that DataInspector.__init__ does
            def __init__(self, input_workspace):  # noqa: ARG002
                self.roi_peak = None
                self.roi_low_res = None
                self.roi_background = None

        # Mock EventWorkspace and its getRun method. Mock function workspace_handle
        mock_workspace = MagicMock()
        mock_workspace_handle.return_value = mock_workspace
        mock_run = {
            "ROI1StartX": MagicMock(),
            "ROI1SizeX": MagicMock(),
            "ROI1StartY": MagicMock(),
            "ROI1SizeY": MagicMock(),
            "ROI2StartX": MagicMock(),
            "ROI2SizeX": MagicMock(),
        }
        # Set mock values
        mock_run["ROI1StartX"].getStatistics().mean = startx
        mock_run["ROI1SizeX"].getStatistics().mean = sizex
        mock_run["ROI1StartY"].getStatistics().mean = starty
        mock_run["ROI1SizeY"].getStatistics().mean = sizey
        mock_run["ROI2StartX"].getStatistics().mean = roi2_startx
        mock_run["ROI2SizeX"].getStatistics().mean = roi2_sizex
        mock_workspace.getRun.return_value = mock_run

        # Create a MockDataInspector instance and call process_pv_roi
        inspector = MockDataInspector(input_workspace=mock_workspace)
        inspector.process_pv_roi(mock_workspace)

        # Assert the calculated ROIs
        assert inspector.roi_peak == peak
        assert inspector.roi_low_res == low_res
        assert inspector.roi_background == background


if __name__ == "__main__":
    pytest.main([__file__])
