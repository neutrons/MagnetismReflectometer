# standard imports
from typing import Optional, Union

# third-party imports
from mantid.api import Workspace, WorkspaceGroup
from mantid.dataobjects import Workspace2D
from mantid.simpleapi import AddSampleLog, mtd

PEAK_NUMBER_LOG = "peak_number"


class RunPeakNumber:
    r"""An extension of the run number when the run contains more than one peak

    Examples
    --------
    - 12345 when run 12345 has one peak
    - 12345_1, 12345_2 when run 12345 has two peaks

    Parameters
    ----------
    run_number
        the integer run number (e.g. 12345)
    peak_number
        a number identifying the peak, beginning at 1
    """

    @staticmethod
    def peak_number_log(input_workspace: Union[str, Workspace]) -> Optional[int]:
        r"""
        Fetch the peak number from the logs of the input workspace

        Parameters
        ----------
        input_workspace
            Name or handle to a Mantid workspace

        Returns
        -------
        Peak number, or `None` if no peak number is found in the logs
        """
        workspace = mtd[str(input_workspace)]
        if isinstance(workspace, WorkspaceGroup):
            workspace = workspace[0]
        run = workspace.getRun()
        if run.hasProperty(PEAK_NUMBER_LOG):
            return run.getProperty(PEAK_NUMBER_LOG).value
        else:
            return None

    def __init__(self, runpeak: Union[str, int, "RunPeakNumber"], peak_number: Union[str, int] = None):
        r"""
        A RunPeakNumber is a run number (e.g. 12345) or a combination of a run number and a peak number
        (e.g. 12335_2 for run number 12345 and peak number 2). Peak numbers start at 1, not 0.

        Parameters
        ----------
        runpeak: Union[str, int, 'RunPeakNumber']
            Either a run number as `str` or `int`, or a run-peak number as a `str` or a RunPeakNumber instance.
            Examples: 12345, "12335", "12345_2", RunPeakNumber("12335", "2")
        peak_number: Optional[Union[str, int]]
            Combine with `runpeak` only if `runpeak` represents a run number. Ignore otherwise.
        """

        self._peak_number = None
        if isinstance(runpeak, int):  # runpeak represents a run number
            self._run_number = runpeak
        elif isinstance(runpeak, str):
            if "_" in runpeak:  # runpeak represents a RunPeakNumber
                self._run_number, self._peak_number = [int(x) for x in runpeak.split("_")]
            else:  # runpeak represents a run number
                self._run_number = int(runpeak)
        elif isinstance(runpeak, RunPeakNumber):  # runpeak is a RunPeakNumber instance
            self._run_number = runpeak._run_number
            self._peak_number = runpeak._peak_number
        else:
            raise ValueError("`runpeak` is not a valid run number or run-peak number")
        if self._peak_number is None and peak_number is not None:
            self._peak_number = int(peak_number)

        if self._peak_number is not None:
            assert int(self._peak_number) > 0, "Peak number must be greater than 0"

    @property
    def run_number(self):
        r"""Mimic immutable attribute"""
        return self._run_number

    @property
    def peak_number(self):
        r"""Mimic immutable attribute"""
        return self._peak_number

    def __repr__(self):
        output = str(self.run_number)
        if self.peak_number is not None:
            output += "_" + str(self.peak_number)
        return output

    def log_peak_number(self, input_workspace: Union[str, Workspace2D, WorkspaceGroup]):
        r"""
        Insert the peak number into the logs of the input workspace

        Parameters
        ----------
        input_workspace
            Name or handle to the Mantid workspace. If a Mantid `WorkspaceGroup`,
            insert the peak number into each workspace of the group

        Raises
        ------
        ValueError
            If the peak number is `None`
        """
        if self._peak_number is None:
            raise ValueError("Peak number cannot be None")
        workspace = mtd[str(input_workspace)]  # handle to the workspace
        if isinstance(workspace, WorkspaceGroup):
            for ws in workspace:
                self.log_peak_number(ws)
        else:
            AddSampleLog(
                Workspace=workspace,
                LogType="Number",
                NumberType="Int",
                LogName=PEAK_NUMBER_LOG,
                LogText=str(self._peak_number),
            )
