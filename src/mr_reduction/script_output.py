# standard imports
import os
import time

# third-party imports
import mantid
import mantid.simpleapi as api

# mr_reduction imports
from mr_reduction.reflectivity_output import quicknxs_scaling_factor
from mr_reduction.runsample import RunSampleNumber
from mr_reduction.settings import ar_out_dir


def write_reduction_script(matched_runs, scaling_factors, ipts) -> str:
    r"""Write a combined reduction script by pasting together the reduction script for each run that
    is to be stitched with the others.

    Parameters
    ----------
    matched_runs : List[str]
        Data runs (or RunSampleNumber's) ordered by increasing Q, to be stitched together
        e.g ['1234', '1235'], ['1234_2', '1235_2']
    scaling_factors : List[float]
        Numbers by which to multiply each matched reflectivity curve, when stitching
    ipts: str
        Experiment identifier (e.g. 'IPTS-42666')

    Returns
    -------
    str
        File path of the combined reduction script (its file name is f"REF_M_{matched_runs[0]}_combined.py")
    """
    script = "# Mantid version %s\n" % mantid.__version__
    script += "# Date: %s\n\n" % time.strftime("%Y-%m-%d %H:%M:%S")
    script += "from mantid.simpleapi import *\n\n"
    script += "# Dictionary of workspace names. Each entry is a list of cross-sections\n"
    script += "workspaces =  dict()\n"

    output_dir = ar_out_dir(ipts)
    for i, runsample in enumerate(matched_runs):
        file_path = os.path.join(output_dir, "REF_M_%s_partial.py" % runsample)
        if not os.path.isfile(file_path):
            api.logger.notice("Partial script doesn't exist: %s" % file_path)
            continue
        with open(file_path, "r") as _fd:
            script += "# Run:%s\n" % runsample
            script += "scaling_factor = %s\n" % scaling_factors[i]
            script += _fd.read() + "\n"

    script_filename = f"REF_M_{matched_runs[0]}_combined.py"
    with open(os.path.join(output_dir, script_filename), "w") as fd:
        fd.write(script)
    return script_filename


def write_tunable_reduction_script(matched_runs, scaling_factors, ipts) -> str:
    """Write a combined reduction script

    Parameters
    ----------
    matched_runs : List[str]
        Data runs (or RunSampleNumber's) ordered by increasing Q, to be stitched together
        e.g ['1234', '1235'], ['1234_2', '1235_2']
    scaling_factors : List[float]
        Numbers by which to multiply each matched reflectivity curve, when stitching
    ipts: str
        Experiment identifier (e.g. 'IPTS-42666')

    Returns
    -------
    str
        File path of the combined reduction script (its file name is f"REF_M_{matched_runs[0]}_tunable_combined.py"")
    """
    script = "# Mantid version %s\n" % mantid.__version__
    script += "# Date: %s\n\n" % time.strftime("%Y-%m-%d %H:%M:%S")
    script += "from mantid.simpleapi import *\n\n"
    script += "# Dictionary of workspace names. Each entry is a list of cross-sections\n"
    script += "workspaces =  dict()\n"
    script += "parameters = dict()\n\n"

    output_dir = ar_out_dir(ipts=ipts)
    reduce_call = "\ndef reduce():\n"
    prepare_call = "def prepare():\n"
    for i, runsample in enumerate(matched_runs):
        file_path = os.path.join(output_dir, "REF_M_%s_partial.py" % runsample)
        if not os.path.isfile(file_path):
            api.logger.notice("Partial script doesn't exist: %s" % file_path)
            continue
        script += "\n# Run:%s\n" % runsample
        script += "parameters['r_%s'] = dict(sf_%s = %s)\n" % (runsample, runsample, scaling_factors[i])
        _script = generate_split_script(runsample, file_path)
        script += _script + "\n"
        reduce_call += "    reduce_%s()\n" % runsample
        prepare_call += "    prepare_%s()\n" % runsample

    script += prepare_call
    script += reduce_call
    script_filepath = os.path.join(output_dir, f"REF_M_{matched_runs[0]}_tunable_combined.py")
    with open(script_filepath, "w") as fd:
        fd.write(script)
    return script_filepath


def write_partial_script(ws_grp):
    """
    Write a partial python reduction script. This script will be
    used by the merging process to produce a clean and final reduction
    script for the whole reflectivity curve.

    :param ws_grp: a Mantid workspace or WorkspaceGroup
    """
    # This should work for either a workspace or workspace group,
    # so determine which one it is first.
    if isinstance(ws_grp, mantid.api.WorkspaceGroup):
        _ws = ws_grp[0]
        _ws_list = ws_grp
    else:
        _ws = ws_grp
        _ws_list = [ws_grp]

    script = generate_script_from_ws(_ws_list, group_name=str(ws_grp))
    ipts = _ws.getRun().getProperty("experiment_identifier").value
    run_number = _ws.getRunNumber()
    sample_number = RunSampleNumber.sample_number_log(_ws)
    runsample = RunSampleNumber(run_number, sample_number)
    output_dir = ar_out_dir(ipts)
    with open(os.path.join(output_dir, f"REF_M_{runsample}_partial.py"), "w") as fd:
        fd.write(script)


def generate_script_from_ws(ws_grp, group_name):
    r"""Generate a partial reduction script from a set of workspaces.

    This function needs to be compatible with the case of a single workspace.
    For this reason, we are not assuming that ws_grp is a workspace group.
    We therefore need the name of the grouping we want to associate this set with in the output script.

    The script calls the following algorithms sequentially:
        LoadEventNexus
        MRFilterCrossSections
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

    Returns
    -------
    str
    """
    if len(ws_grp) == 0:
        return "# No workspace was generated\n"

    xs_list = [str(_ws) for _ws in ws_grp if not str(_ws).endswith("unfiltered")]
    script = "workspaces['%s'] = %s\n" % (group_name, str(xs_list))

    script_text = api.GeneratePythonScript(ws_grp[0])
    # Skip the header
    lines = script_text.split("\n")
    script_text = "\n".join(lines[4:])
    script += script_text.replace(", ", ",\n                                ")
    script += "\n"
    qnxs_scale = quicknxs_scaling_factor(ws_grp[0])
    # Scale correction for QuickNXS compatibility
    script += "scaling_factor *= %s\n" % qnxs_scale
    for item in xs_list:
        script += "Scale(InputWorkspace='%s', Operation='Multiply',\n" % str(item)
        script += "      Factor=scaling_factor, OutputWorkspace='%s')\n\n" % str(item)

    return script


def generate_split_script(run_sample_number, partial_script_path) -> str:
    r"""Split a reduction script into two parts: one to set up the parameters and one to execute the reduction.

    This script is the same as input `partial_script_path` except that the call to Mantid algorithm
    MagnetismReflectometryReduction uses kwargs dictionary, and the call is wrapped by a python function which
    is not called in the script. Thus, this script does everything to reduce the run except the actual call to
    MagnetismReflectometryReduction.

    Parameters
    ----------
    run_sample_number: str
        run number (e.g. '12345') or RunSampleNumber (e.g. '12345_2')
    partial_script_path: str
        File path to the reduction script for one data run (e.g. '/tmp/REF_M_12345_2_partial.py' for run `12345_2`)

    Returns
    -------
    str
        Contents of the reduction script
    """
    red_script = "def prepare_%s():\n" % run_sample_number
    scale_script = ""

    with open(partial_script_path, "r") as fd:
        _script_started = False
        _scale_started = False
        _first_line = True
        for line in fd.readlines():
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
            elif _scale_started:
                scale_script += "    " + line.replace(
                    "scaling_factor", 'parameters["r_%s"]["sf_%s"]' % (run_sample_number, run_sample_number)
                )
            else:
                red_script += "    " + line.replace(
                    "scaling_factor", 'parameters["r_%s"]["sf_%s"]' % (run_sample_number, run_sample_number)
                )

    red_script = red_script.replace("MagnetismReflectometryReduction", "params_%s = dict" % run_sample_number)
    red_script = red_script.replace("wsg", "wsg_%s" % run_sample_number)
    red_script += '    parameters["r_%s"]["params"] = params_%s\n' % (run_sample_number, run_sample_number)

    red_script += "\ndef reduce_%s():\n" % run_sample_number
    red_script += '    MagnetismReflectometryReduction(**parameters["r_%s"]["params"])\n' % run_sample_number
    red_script += scale_script

    return red_script
