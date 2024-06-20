# standard imports
from typing import Optional, Union

# third-party imports
from mantid.api import Workspace, WorkspaceGroup
from mantid.dataobjects import Workspace2D
from mantid.simpleapi import AddSampleLog, mtd

SAMPLE_NUMBER_LOG = "sample_number"


class RunSampleNumber:
    r"""An extension of the run number when the run contains more than one sample

    Examples
    --------
    - 12345 when run 12345 has one sample
    - 12345_1, 12345_2 when run 12345 has two samples

    Parameters
    ----------
    run_number
        the integer run number (e.g. 12345)
    sample_number
        a number identifying the sample, beginning at 1
    """

    @staticmethod
    def sample_number_log(input_workspace: Union[str, Workspace]) -> Optional[int]:
        r"""
        Fetch the sample number from the logs of the input workspace

        Parameters
        ----------
        input_workspace
            Name or handle to a Mantid workspace

        Returns
        -------
        Sample number, or `None` if no sample number is found in the logs
        """
        workspace = mtd[str(input_workspace)]
        if isinstance(workspace, WorkspaceGroup):
            workspace = workspace[0]
        run = workspace.getRun()
        if run.hasProperty(SAMPLE_NUMBER_LOG):
            return run.getProperty(SAMPLE_NUMBER_LOG).value
        else:
            return None

    def __init__(self, runsample: Union[str, int, "RunSampleNumber"], sample_number: Union[str, int] = None):
        r"""
        A RunSampleNumber is a run number (e.g. 12345) or a combination of a run number and a sample number
        (e.g. 12335_2 for run number 12345 and sample number 2). Sample numbers start at 1, not 0.

        Parameters
        ----------
        runsample: Union[str, int, 'RunSampleNumber']
            Either a run number as `str` or `int`, or a run-sample number as a `str` or a RunSampleNumber instance.
            Examples: 12345, "12335", "12345_2", RunSampleNumber("12335", "2")
        sample_number: Optional[Union[str, int]]
            Combine with `runsample` only if `runsample` represents a run number. Ignore otherwise.
        """

        self._sample_number = None
        if isinstance(runsample, int):  # runsample represents a run number
            self._run_number = runsample
        elif isinstance(runsample, str):
            if "_" in runsample:  # runsample represents a RunSampleNumber
                self._run_number, self._sample_number = [int(x) for x in runsample.split("_")]
            else:  # runsample represents a run number
                self._run_number = int(runsample)
        elif isinstance(runsample, RunSampleNumber):  # runsample is a RunSampleNumber instance
            self._run_number = runsample._run_number
            self._sample_number = runsample._sample_number
        else:
            raise ValueError("`runsample` is not a valid run number or run-sample number")
        if self._sample_number is None and sample_number is not None:
            self._sample_number = int(sample_number)

        if self._sample_number is not None:
            assert int(self._sample_number) > 0, "Sample number must be greater than 0"

    @property
    def run_number(self):
        r"""Mimic immutable attribute"""
        return self._run_number

    @property
    def sample_number(self):
        r"""Mimic immutable attribute"""
        return self._sample_number

    def __repr__(self):
        output = str(self.run_number)
        if self.sample_number is not None:
            output += "_" + str(self.sample_number)
        return output

    def log_sample_number(self, input_workspace: Union[str, Workspace2D, WorkspaceGroup]):
        r"""
        Insert the sample number into the logs of the input workspace

        Parameters
        ----------
        input_workspace
            Name or handle to the Mantid workspace. If a Mantid `WorkspaceGroup`,
            insert the sample number into each workspace of the group

        Raises
        ------
        ValueError
            If the sample number is `None`
        """
        if self._sample_number is None:
            raise ValueError("Sample number cannot be None")
        workspace = mtd[str(input_workspace)]  # handle to the workspace
        if isinstance(workspace, WorkspaceGroup):
            for ws in workspace:
                self.log_sample_number(ws)
        else:
            AddSampleLog(
                Workspace=workspace,
                LogType="Number",
                NumberType="Int",
                LogName=SAMPLE_NUMBER_LOG,
                LogText=str(self._sample_number),
            )
