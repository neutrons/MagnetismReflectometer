"""
Script digested by Mantid algorithm LiveDataAlgorithm.
LiveDataAlgorithm creates child algorithm "RunPythonScript" and run
RunPythonScript(InputWorkspace=input, Filename="reduce_REF_M_live_post_proc.py")
"""

# standard library imports
import math
import os
import time
from contextlib import contextmanager
from typing import Optional

# third-party imports
import mantid
from mantid import simpleapi as api

# mr_reduction and mr_livereduce imports
from mr_livereduce.polarization_analysis import calculate_ratios
from mr_reduction import settings as reduction_settings
from mr_reduction.simple_utils import SampleLogs, add_to_sys_path, workspace_handle
from mr_reduction.types import MantidWorkspace
from mr_reduction.web_report import _plot1d

GLOBAL_LR_DIR = "/SNS/REF_M/shared/livereduce"


@contextmanager
def debug_logger(logpath: str = os.path.join(GLOBAL_LR_DIR, "livereduce_REF_M.log"), debug: bool = True):
    logfile = None
    if debug:
        logfile = open(logpath, "a")
        logfile.write("Starting post-proc\n")
    try:
        yield logfile
    finally:
        if logfile is not None:
            logfile.write("DONE\n")
            logfile.close()


def rebin_tof(input_workspace: MantidWorkspace, output_workspace: str = None) -> mantid.dataobjects.EventWorkspace:
    """
    Rebin the input workspace to a fixed binning of 50 microseconds.

    The input workspace is overwritten only when `output_workspace` is the name of `input_workspace`.

    Parameters
    ----------
    input_workspace
        The input workspace to be rebinned as an EventWorkspace or the name of the workspace
    output_workspace
        The name of the rebinned workspace. If None, a unique name will be generated.

    Returns
    -------

    """
    ws = workspace_handle(input_workspace)
    tof_min = math.floor(ws.getTofMin())
    tof_max = math.ceil(ws.getTofMax())
    assert tof_min < tof_max, "Found min TOF > max TOF in aggregated input Events workspace"
    if not output_workspace:
        output_workspace = api.mtd.unique_hidden_name()  #  new workspace with a hidden name
    return api.Rebin(ws, params=f"{tof_min}, 50, {tof_max}", PreserveEvents=True, OutputWorkspace=output_workspace)


def header_report(workspace: MantidWorkspace) -> str:
    """Basic information on the run"""
    try:
        samplelogs = SampleLogs(workspace)
        report = f"<div>Run Number: {workspace.getRunNumber()}</div>\n"
        report += f"<div>Events: {workspace.getNumberEvents()}</div>\n"
        report += f"<div>Sequence: {samplelogs['sequence_number']} of {samplelogs['sequence_total']}</div>\n"
        report += f"<div>Report time: {time.ctime()}</div>\n"
    except Exception as exception:  # noqa E722
        report = f"<div>{exception}</div>\n"
    return report


def polarization_report(workspace: MantidWorkspace) -> str:
    def div_plot1d(ratio: Optional[MantidWorkspace], y_label: str):
        if ratio is not None:
            plot = _plot1d(
                ratio.readX(0),
                ratio.readY(0),
                x_range=None,
                x_label="Wavelength",
                y_label=y_label,
                title="",
                x_log=False,
                y_log=False,
            )
            return f"<td>{plot}</td>\n"
        return ""

    report = "<hr>\n"  # insert a horizontal line
    try:
        ws_list, ratio1, ratio2, asym1, labels = calculate_ratios(workspace, delta_wl=0.05, slow_filter=True)
        report += "<table style='width:100%'>\n"
        report += f"<tr><td>Number of polarization states: {len(ws_list)}</td></tr>\n"
        report += "<tr>\n"
        for quantity, label in zip([ratio1, ratio2, asym1], labels):
            report += div_plot1d(quantity, label)
        report += "</tr>\n"
        report += "</table>\n"
    except Exception as exception:  # noqa E722
        report += f"<div>Error: {exception}</div>\n"
    return report


def main():
    r"""Livereduce the accumulation events workspace and upload the HTML report to the livedata server"""
    with debug_logger(debug=True) as logfile:
        live_report = [header_report(input)]
        with add_to_sys_path(reduction_settings.GLOBAL_AR_DIR):  # "/SNS/REF_M/shared/autoreduce"
            from reduce_REF_M import (  # import from the autoreduction script reduce_REF_M.py
                reduce_events,
                upload_html_report,
            )

            events_binned = rebin_tof(input)
            live_report += reduce_events(workspace=events_binned, log_file_handle=logfile)
            live_report.append(polarization_report(events_binned))
            upload_html_report(live_report, publish=True, run_number=events_binned.getRunNumber())


if __name__ == "__main__":
    main()
