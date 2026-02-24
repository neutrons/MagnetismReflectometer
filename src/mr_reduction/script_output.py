"""
This module provides functions to generate and write reduction scripts for reflectometry data.
It includes functions to create combined reduction scripts from multiple runs, as well as partial
scripts for individual runs. The scripts are used to process and analyze reflectometry data using
the Mantid framework.
"""

# standard imports
import os
import time
from enum import Enum, auto
from pathlib import Path

# third-party imports
import mantid
import mantid.simpleapi as api

# mr_reduction imports
from mr_reduction.reflectivity_output import quicknxs_scaling_factor
from mr_reduction.runpeak import RunPeakNumber
from mr_reduction.settings import PolarizationLogs
from mr_reduction.types import MantidWorkspace


def write_reduction_script(matched_runs, scaling_factors, ar_dir) -> str:
    """Write a combined reduction script

    Parameters
    ----------
    matched_runs : List[str]
        Data runs (or RunPeakNumber's) ordered by increasing Q, to be stitched together
        e.g ['1234', '1235'], ['1234_2', '1235_2']
    scaling_factors : List[float]
        Numbers by which to multiply each matched reflectivity curve, when stitching
    ar_dir: str
        Directory where to write the reduction script.
        In autoreduce mode, it will be /SNS/REF_M/IPTS-XXXX/shared/autoreduce

    Returns
    -------
    str
        File path of the combined reduction script (its file name is f"REF_M_{matched_runs[0]}_combined.py"")
    """
    script = "# Mantid version %s\n" % mantid.__version__
    script += "# Date: %s\n\n" % time.strftime("%Y-%m-%d %H:%M:%S")
    script += "from mantid.simpleapi import *\n\n"
    script += "# Dictionary of workspace names. Each entry is a list of cross-sections\n"
    script += "workspaces =  dict()\n"
    script += "parameters = dict()\n\n"

    reduce_call = "\ndef reduce():\n"
    prepare_call = "def prepare():\n"
    for i, runpeak in enumerate(matched_runs):
        file_path = os.path.join(ar_dir, "REF_M_%s_partial.py" % runpeak)
        if os.path.isfile(file_path):
            script += "\n# Run:%s\n" % runpeak
            script += "parameters['r_%s'] = dict(sf_%s = %s)\n" % (runpeak, runpeak, scaling_factors[i])
            _script = generate_split_script(runpeak, file_path)
            script += _script + "\n"
            reduce_call += "    reduce_%s()\n" % runpeak
            prepare_call += "    prepare_%s()\n" % runpeak

    script += prepare_call
    script += reduce_call
    script += "\n"
    script += "prepare()\n"
    script += "reduce()\n"
    script_filepath = os.path.join(ar_dir, f"REF_M_{matched_runs[0]}_combined.py")
    with open(script_filepath, "w") as fd:
        fd.write(script)
    return script_filepath


def write_partial_script(
    ws_grp: mantid.api.WorkspaceGroup | MantidWorkspace,
    output_dir: str,
    polarization_logs: PolarizationLogs | None = None,
) -> None:
    r"""
    Write a partial python reduction script. This script will be
    used by the merging process to produce a clean and final reduction
    script for the whole reflectivity curve.

    Parameters
    ----------
    ws_grp:
        a Mantid workspace or WorkspaceGroup
    output_dir: str
        Directory where to write the reduction script.
        In autoreduce mode, it will be /SNS/REF_M/IPTS-XXXX/shared/autoreduce
    """
    # This should work for either a workspace or workspace group,
    # so determine which one it is first.
    if isinstance(ws_grp, mantid.api.WorkspaceGroup):
        _ws = ws_grp[0]
        _ws_list = ws_grp
    else:
        _ws = ws_grp
        _ws_list = [ws_grp]

    script = generate_script_from_ws(_ws_list, group_name=str(ws_grp), polarization_logs=polarization_logs)
    run_number = _ws.getRunNumber()
    peak_number = RunPeakNumber.peak_number_log(_ws)
    runpeak = RunPeakNumber(run_number, peak_number)
    with open(os.path.join(output_dir, f"REF_M_{runpeak}_partial.py"), "w") as fd:
        fd.write(script)


class StringInsertMode(Enum):
    BEFORE = auto()
    AFTER = auto()
    PREPEND = auto()


def _insert_relative_to_keyword(
    lines: list[str],
    keyword: str,
    content: str,
    *,
    mode: StringInsertMode,
) -> None:
    """
    Modify `lines` relative to the first line whose stripped content starts
    with `keyword`.

    Parameters
    ----------
    lines : list[str]
        List of lines to modify in place
    keyword : str
        Keyword to search for
    content : str
        Content to insert
    mode : StringInsertMode
        Modes:
        - BEFORE: insert `content` as a new line before the match
        - AFTER: insert `content` as a new line after the match
        - PREPEND: prepend `content` to the matching line
    """
    for i, line in enumerate(lines):
        if line.strip().startswith(keyword):
            if mode is StringInsertMode.BEFORE:
                lines.insert(i, content)
            elif mode is StringInsertMode.AFTER:
                lines.insert(i + 1, content)
            elif mode is StringInsertMode.PREPEND:
                lines[i] = content + line
            else:
                raise ValueError(f"Unknown InsertMode: {mode}")
            return

    api.logger.warning(
        f"Failed to insert content relative to keyword '{keyword}'. Keyword not found in generated script."
    )


def generate_script_from_ws(
    ws_grp: list | mantid.api.WorkspaceGroup,
    group_name: str,
    quicknxs_mode: bool = True,
    include_workspace_string: bool = True,
    polarization_logs: PolarizationLogs | None = None,
) -> str:
    r"""Generate a partial reduction script from a set of workspaces.

    This function needs to be compatible with the case of a single workspace.
    For this reason, we are not assuming that ws_grp is a workspace group.
    We therefore need the name of the grouping we want to associate this set with in the output script.

    The script calls the following algorithms/functions sequentially:
        LoadEventNexus
        filter_events.split_events
        LoadEventNexus
        GroupWorkspaces
        MagnetismReflectometryReduction
        Scale

    Parameters
    ----------
    ws_grp: list, mantid.dataobjects.Workspace2D, mantid.api.WorkspaceGroup
        Mantid workspace(s), or workspace group
    group_name: str
        name of the group the workspace belongs to
    quicknxs_mode: bool
        If True, the script will include a scaling factor correction for compatibility with QuickNXS
    include_workspace_string: bool
        If True, the script will include a line defining the workspace group
        (e.g. "workspaces['r_12345_1'] = ['12345_Off_Off__reflectivity', '12345_On_Off__reflectivity']")
    polarization_logs: PolarizationLogs | None
        If provided, the script will use the polarization logs definition in the generated script

    Returns
    -------
    str
    """
    if len(ws_grp) == 0:
        return "# No workspace was generated\n"

    if polarization_logs is None:
        # use the default
        polarization_logs = PolarizationLogs()

    xs_list = [str(_ws) for _ws in ws_grp if not str(_ws).endswith("unfiltered")]
    script = ""
    if include_workspace_string is True:
        script += f"workspaces['{group_name}'] = {str(xs_list)}\n"

    # ignore these algorithms when generating the script
    mantid_algs_to_ignore = [
        # called by mr_reduction.filter_events.split_events
        "CreateEmptyTableWorkspace",
        "FilterEvents",
        # skip diagnostic saving to Nexus
        "SaveNexus",
    ]

    script_text = api.GeneratePythonScript(ws_grp[0], IgnoreTheseAlgs=mantid_algs_to_ignore, ExcludeHeader=True)

    api.logger.notice(f"GeneratePythonScript script length {len(script_text)}")

    lines = script_text.split("\n")

    # insert function `split_events` which is not part of the workspace history and required imports
    imports_snippet = """from mr_reduction.filter_events import split_events
from mr_reduction.settings import PolarizationLogs"""
    _insert_relative_to_keyword(lines, "from mantid.simpleapi import *", imports_snippet, mode=StringInsertMode.AFTER)
    _insert_relative_to_keyword(lines, "LoadEventNexus", "ws = ", mode=StringInsertMode.PREPEND)
    polarization_logs_snippet = f'polarization_logs = PolarizationLogs(pol_state="{polarization_logs.POL_STATE}", '
    polarization_logs_snippet += f'pol_veto="{polarization_logs.POL_VETO}", '
    polarization_logs_snippet += f'ana_state="{polarization_logs.ANA_STATE}", '
    polarization_logs_snippet += f'ana_veto="{polarization_logs.ANA_VETO}")'
    split_events_snippet = f"""{polarization_logs_snippet}
ws_list = split_events(input_workspace=ws, polarization_logs=polarization_logs)"""
    _insert_relative_to_keyword(lines, "ws = LoadEventNexus", split_events_snippet, mode=StringInsertMode.AFTER)

    # reformat for better readability
    refl_algo_idx = next((i for i, line in enumerate(lines) if "MagnetismReflectometryReduction(" in line), None)
    if refl_algo_idx is None:
        api.logger.warning(
            "Failed to reformat generated script around 'MagnetismReflectometryReduction('. Pattern not found."
        )
    else:
        tmp_refl_algo_line = lines[refl_algo_idx].replace(", ", ",\n                                ")
        lines[refl_algo_idx] = tmp_refl_algo_line
    script_text = "\n".join(lines)
    script += script_text
    script += "\n"

    api.logger.notice(f"Script length after formatting {len(script)}")

    if quicknxs_mode is True:
        qnxs_scale = quicknxs_scaling_factor(ws_grp[0])
        script += "scaling_factor *= %s\n" % qnxs_scale
        for item in xs_list:
            script += "Scale(InputWorkspace='%s', Operation='Multiply',\n" % str(item)
            script += "      Factor=scaling_factor, OutputWorkspace='%s')\n\n" % str(item)

        api.logger.notice(f"Script length after adding quicknxs scaling {len(script)}")

    return script


def generate_split_script(run_peak_number, partial_script_path) -> str:
    r"""Split a reduction script into two parts: one to set up the parameters and one to execute the reduction.

    This script is the same as input `partial_script_path` except that the call to Mantid algorithm
    MagnetismReflectometryReduction uses kwargs dictionary, and the call is wrapped by a python function which
    is not called in the script. Thus, this script does everything to reduce the run except the actual call to
    MagnetismReflectometryReduction.

    Parameters
    ----------
    run_peak_number: str
        run number (e.g. '12345') or RunPeakNumber (e.g. '12345_2')
    partial_script_path: str
        File path to the reduction script for one data run (e.g. '/tmp/REF_M_12345_2_partial.py' for run `12345_2`)

    Returns
    -------
    str
        Contents of the reduction script
    """
    red_script = "def prepare_%s():\n" % run_peak_number
    scale_script = ""

    with open(partial_script_path, "r") as fd:
        _script_started = False
        _script_finished = False
        _scale_started = False
        _first_line = True
        for line in fd.readlines():
            # can't use wildcard import inside functions
            if "from mantid.simpleapi import *" in line:
                continue

            if line.startswith("MagnetismReflectometryRed"):
                _script_started = True
            elif line.startswith("Scale"):
                _scale_started = True

            if _script_started:
                if _first_line:
                    red_script += "    " + line
                    _first_line = False
                else:
                    red_script += "                        " + line.strip() + "\n"
                if line.endswith(")\n"):
                    _script_started = False
                    _script_finished = True
            elif _script_finished:
                if line.startswith("AddSampleLog"):
                    scale_script += "    " + line.strip() + "\n"
                else:
                    scale_script += "                 " + line.strip() + "\n"
                if line.endswith(")\n"):
                    _script_finished = False
            elif _scale_started:
                scale_script += "    " + line.replace(
                    "scaling_factor", 'parameters["r_%s"]["sf_%s"]' % (run_peak_number, run_peak_number)
                )
            else:
                red_script += "    " + line.replace(
                    "scaling_factor", 'parameters["r_%s"]["sf_%s"]' % (run_peak_number, run_peak_number)
                )

    red_script = red_script.replace("MagnetismReflectometryReduction", "params_%s = dict" % run_peak_number)
    red_script = red_script.replace("wsg", "wsg_%s" % run_peak_number)
    red_script += '    parameters["r_%s"]["params"] = params_%s\n' % (run_peak_number, run_peak_number)

    red_script += "\ndef reduce_%s():\n" % run_peak_number
    red_script += '    MagnetismReflectometryReduction(**parameters["r_%s"]["params"])\n' % run_peak_number
    red_script += scale_script

    return red_script
