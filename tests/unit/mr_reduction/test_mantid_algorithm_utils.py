import mantid.simpleapi as api
import pytest
from mantid.api import (
    IEventWorkspaceProperty,
    MatrixWorkspaceProperty,
    PropertyMode,
    PythonAlgorithm,
)
from mantid.kernel import Direction

from mr_reduction.mantid_algorithm_utils import mantid_algorithm_exec


@pytest.fixture
def mock_algorithm():
    class MockAlgorithm(PythonAlgorithm):
        def __init__(self):
            super().__init__()

        def PyInit(self):
            self.declareProperty(
                MatrixWorkspaceProperty("OutputWorkspace", "", Direction.Output),
                "Output workspace",
            )

        def PyExec(self):
            if not self.getProperty("OutputWorkspace").isDefault:
                ws = api.CreateSingleValuedWorkspace(42)
                self.setProperty("OutputWorkspace", ws)

    return MockAlgorithm


def test_mantid_algorithm_exec(mock_algorithm):
    # Check that the function returns the OutputWorkspace if it is set
    result = mantid_algorithm_exec(mock_algorithm, OutputWorkspace="OutputWorkspace")
    assert result.readY(0) == 42.0

    # Check that the function returns None if OutputWorkspace is not set
    result = mantid_algorithm_exec(mock_algorithm)
    assert result is None
