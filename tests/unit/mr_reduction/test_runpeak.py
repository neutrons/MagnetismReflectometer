# third party imports
import pytest
from mantid.api import WorkspaceGroup
from mantid.simpleapi import AddSampleLog, CreateWorkspace, GroupWorkspaces

# mr_reduction imports
from mr_reduction.runpeak import PEAK_NUMBER_LOG, RunPeakNumber


class TestRunPeakNumber:
    def test_init(self):
        with pytest.raises(AssertionError) as e:
            RunPeakNumber("1234", 0)
        assert str(e.value) == "Peak number must be greater than 0"
        runpeak = RunPeakNumber("1234")
        assert str(runpeak) == "1234"
        runpeak = RunPeakNumber("1234_42")
        assert str(runpeak) == "1234_42"
        runpeak = RunPeakNumber("1234_42", "15")  # ignore peak_number
        assert str(runpeak) == "1234_42"
        runpeak2 = RunPeakNumber(runpeak)
        assert str(runpeak2) == "1234_42"

    def test_str(self):
        assert str(RunPeakNumber("1234")) == "1234"
        assert str(RunPeakNumber(1234, 1)) == "1234_1"

    def test_log_peak_number(self):
        w1 = CreateWorkspace(DataX=[0.0, 1.0], DataY=[0.0, 1.0])
        w2 = CreateWorkspace(DataX=[0.0, 1.0], DataY=[0.0, 1.0])
        wg = GroupWorkspaces([w1, w2])

        runpeak_empty = RunPeakNumber(1234)
        with pytest.raises(ValueError, match="Peak number cannot be None"):
            runpeak_empty.log_peak_number(w1)
        with pytest.raises(ValueError, match="Peak number cannot be None"):
            runpeak_empty.log_peak_number(str(w1))
        with pytest.raises(ValueError, match="Peak number cannot be None"):
            runpeak_empty.log_peak_number(wg)

        runpeak = RunPeakNumber(1234, 2)
        runpeak.log_peak_number(wg)
        assert w1.getRun().hasProperty(PEAK_NUMBER_LOG)
        assert w2.getRun().hasProperty(PEAK_NUMBER_LOG)

    def test_peak_number_log(self):
        w1 = CreateWorkspace(DataX=[0.0, 1.0], DataY=[0.0, 1.0])
        AddSampleLog(Workspace=w1, LogType="Number", NumberType="Int", LogName=PEAK_NUMBER_LOG, LogText=str(42))
        assert RunPeakNumber.peak_number_log(w1) == 42
        assert RunPeakNumber.peak_number_log(str(w1)) == 42

        w2 = CreateWorkspace(DataX=[0.0, 1.0], DataY=[0.0, 1.0])
        wg = GroupWorkspaces([w1, w2])
        assert RunPeakNumber.peak_number_log(wg) == 42


if __name__ == "__main__":
    pytest.main([__file__])
