# third party imports
import mantid
import pytest
from mantid.simpleapi import CreateWorkspace, DeleteWorkspace, mtd

# mr_reduction imports
from mr_reduction.data_info import DataType


class TestDataType:
    @staticmethod
    def workspace(metadata_data_type=None):
        ws = CreateWorkspace(DataX=[0, 1], DataY=[0, 10], OutputWorkspace=mtd.unique_hidden_name())
        run = ws.mutableRun()
        if metadata_data_type is not None:
            run.addProperty("data_type", [metadata_data_type], True)
        return ws

    @pytest.mark.parametrize(
        ("metadata_data_type", "expected"),
        [
            (1, DataType.DIRECT_BEAM),
            (0, DataType.REFLECTED_BEAM),
            (42, DataType.REFLECTED_BEAM),
            (None, DataType.REFLECTED_BEAM),
        ],
    )
    def test_initialization(self, metadata_data_type, expected):
        ws = self.workspace(metadata_data_type=metadata_data_type)
        assert DataType.from_workspace(ws) == expected
        DeleteWorkspace(ws)


if __name__ == "__main__":
    pytest.main([__file__])
