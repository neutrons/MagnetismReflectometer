# third party imports
import pytest
from mantid.api import WorkspaceGroup
from mantid.simpleapi import AddSampleLog, CreateWorkspace, GroupWorkspaces

# mr_reduction imports
from mr_reduction.runsample import SAMPLE_NUMBER_LOG, RunSampleNumber


class TestRunSampleNumber:
    def test_init(self):
        with pytest.raises(AssertionError) as e:
            RunSampleNumber("1234", 0)
        assert str(e.value) == "Sample number must be greater than 0"
        runsample = RunSampleNumber("1234")
        assert str(runsample) == "1234"
        runsample = RunSampleNumber("1234_42")
        assert str(runsample) == "1234_42"
        runsample = RunSampleNumber("1234_42", "15")  # ignore sample_number
        assert str(runsample) == "1234_42"
        runsample2 = RunSampleNumber(runsample)
        assert str(runsample2) == "1234_42"

    def test_str(self):
        assert str(RunSampleNumber("1234")) == "1234"
        assert str(RunSampleNumber(1234, 1)) == "1234_1"

    def test_log_sample_number(self):
        w1 = CreateWorkspace(DataX=[0.0, 1.0], DataY=[0.0, 1.0])
        w2 = CreateWorkspace(DataX=[0.0, 1.0], DataY=[0.0, 1.0])
        wg = GroupWorkspaces([w1, w2])

        runsample_empty = RunSampleNumber(1234)
        with pytest.raises(ValueError, match="Sample number cannot be None"):
            runsample_empty.log_sample_number(w1)
        with pytest.raises(ValueError, match="Sample number cannot be None"):
            runsample_empty.log_sample_number(str(w1))
        with pytest.raises(ValueError, match="Sample number cannot be None"):
            runsample_empty.log_sample_number(wg)

        runsample = RunSampleNumber(1234, 2)
        runsample.log_sample_number(wg)
        assert w1.getRun().hasProperty(SAMPLE_NUMBER_LOG)
        assert w2.getRun().hasProperty(SAMPLE_NUMBER_LOG)

    def test_sample_number_log(self):
        w1 = CreateWorkspace(DataX=[0.0, 1.0], DataY=[0.0, 1.0])
        AddSampleLog(Workspace=w1, LogType="Number", NumberType="Int", LogName=SAMPLE_NUMBER_LOG, LogText=str(42))
        assert RunSampleNumber.sample_number_log(w1) == 42
        assert RunSampleNumber.sample_number_log(str(w1)) == 42

        w2 = CreateWorkspace(DataX=[0.0, 1.0], DataY=[0.0, 1.0])
        wg = GroupWorkspaces([w1, w2])
        assert RunSampleNumber.sample_number_log(wg) == 42


if __name__ == "__main__":
    pytest.main([__file__])
