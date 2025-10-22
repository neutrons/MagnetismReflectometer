import mantid.simpleapi as api
import numpy as np
import scipy
from mantid.api import (
    AlgorithmFactory,
    IEventWorkspaceProperty,
    MatrixWorkspaceProperty,
    PropertyMode,
    PythonAlgorithm,
)
from mantid.dataobjects import EventWorkspace
from mantid.kernel import Direction, FloatArrayLengthValidator, FloatArrayProperty
from mantid.simpleapi import Rebin, SumSpectra, logger

from mr_reduction.mantid_algorithm_utils import mantid_algorithm_exec


def apply_dead_time_correction(
    ws: EventWorkspace,
    paralyzable_deadtime: bool,
    deadtime_value: float,
    deadtime_tof_step: float,
    deadtime_tof_range: tuple[float, float] | None = None,
    error_ws: EventWorkspace | None = None,
) -> EventWorkspace:
    """Apply dead time correction, and ensure that it is done only once per workspace.

    Parameters
    ----------
    ws:
        Workspace with raw data to compute correction for
    paralyzable_deadtime:
        If True, the paralyzable correction will be applied, else non-paralyzable
    deadtime_value:
        The dead time, in microseconds
    deadtime_tof_step:
        TOF bin size for computing deadtime correction, in microseconds
    deadtime_tof_range:
        TOF range for computing deadtime correction, in microseconds
    error_ws:
        Workspace with error events

    Returns
    -------
    EventWorkspace
        The input workspace with events weighted by the deadtime correction
    """
    if not ws.getRun().hasProperty("dead_time_applied"):
        algo_kwargs = dict(
            InputWorkspace=ws,
            InputErrorEventsWorkspace=error_ws,
            Paralyzable=paralyzable_deadtime,
            DeadTime=deadtime_value,
            TOFStep=deadtime_tof_step,
            OutputWorkspace="corr",
        )
        if deadtime_tof_range is not None:
            algo_kwargs["TOFRange"] = deadtime_tof_range
        corr_ws = mantid_algorithm_exec(SingleReadoutDeadTimeCorrection, **algo_kwargs)
        ws = api.Multiply(ws, corr_ws, OutputWorkspace=str(ws))
        api.AddSampleLog(Workspace=ws, LogName="dead_time_applied", LogText="1", LogType="Number")
    return ws


class SingleReadoutDeadTimeCorrection(PythonAlgorithm):
    """Dead time correction algorithm for single-readout detectors."""

    def category(self):
        return "Reflectometry\\SNS"

    def name(self):
        return "SingleReadoutDeadTimeCorrection"

    def version(self):
        return 1

    def summary(self):
        return "Single read-out dead time correction calculation"

    def PyInit(self):
        self.declareProperty(
            IEventWorkspaceProperty("InputWorkspace", "", Direction.Input),
            "Input workspace used to compute dead time correction",
        )
        self.declareProperty(
            IEventWorkspaceProperty("InputErrorEventsWorkspace", "", Direction.Input, PropertyMode.Optional),
            "Input workspace with error events used to compute dead time correction",
        )
        self.declareProperty("DeadTime", 4.2, doc="Dead time in microseconds")
        self.declareProperty(
            "TOFStep",
            100.0,
            doc="TOF bins to compute deadtime correction for, in microseconds",
        )
        self.declareProperty(
            "Paralyzable",
            False,
            doc="If true, paralyzable correction will be applied, non-paralyzing otherwise",
        )
        self.declareProperty(
            FloatArrayProperty(
                "TOFRange",
                [0.0, 0.0],
                FloatArrayLengthValidator(2),
                direction=Direction.Input,
            ),
            "TOF range to use",
        )
        self.declareProperty(
            MatrixWorkspaceProperty("OutputWorkspace", "", Direction.Output),
            "Output workspace",
        )

    def PyExec(self):
        # Event data must include error events (all triggers on the detector)
        ws_event_data = self.getProperty("InputWorkspace").value
        ws_error_events = self.getProperty("InputErrorEventsWorkspace").value
        dead_time = self.getProperty("DeadTime").value
        tof_step = self.getProperty("TOFStep").value
        paralyzing = self.getProperty("Paralyzable").value
        output_workspace = self.getPropertyValue("OutputWorkspace")

        # Rebin the data according to the tof_step we want to compute the correction with
        tof_min, tof_max = self.getProperty("TOFRange").value
        if tof_min == 0 and tof_max == 0:
            tof_min = ws_event_data.getTofMin()
            tof_max = ws_event_data.getTofMax()
        logger.notice("TOF range: %f %f" % (tof_min, tof_max))
        _ws_sc = Rebin(
            InputWorkspace=ws_event_data,
            Params="%s,%s,%s" % (tof_min, tof_step, tof_max),
            PreserveEvents=False,
        )

        # Get the total number of counts on the detector for each TOF bin per pulse
        counts_ws = SumSpectra(_ws_sc, OutputWorkspace=output_workspace)

        # If we have error events, add them since those are also detector triggers
        if ws_error_events is not None:
            _errors = Rebin(
                InputWorkspace=ws_error_events,
                Params="%s,%s,%s" % (tof_min, tof_step, tof_max),
                PreserveEvents=False,
            )
            counts_ws += _errors

        # When operating at a given frequency, the proton charge of the blocked
        # pulsed is zero in the data file, so we don't have to adjust the number of pulses.
        t_series = np.asarray(_ws_sc.getRun()["proton_charge"].value)
        n_pulses = np.count_nonzero(t_series)

        rate = counts_ws.readY(0) / n_pulses

        # Compute the dead time correction for each TOF bin
        if paralyzing:
            true_rate = -scipy.special.lambertw(-rate * dead_time / tof_step).real / dead_time
            corr = true_rate / (rate / tof_step)
            # If we have no events, set the correction to 1 otherwise we will get a nan
            # from the equation above.
            corr[rate == 0] = 1
        else:
            corr = 1 / (1 - rate * dead_time / tof_step)

        if np.min(corr) < 0:
            error = "Corrupted dead time correction:\n" + "  Reflected: %s\n" % corr
            logger.error(error)

        counts_ws.setY(0, corr)

        # We don't compute an error on the dead time correction, so set it to zero
        counts_ws.setE(0, 0 * corr)
        counts_ws.setDistribution(True)

        self.setProperty("OutputWorkspace", counts_ws)


AlgorithmFactory.subscribe(SingleReadoutDeadTimeCorrection)
