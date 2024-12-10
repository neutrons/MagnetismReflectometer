# pylint: disable=bare-except, invalid-name, too-many-arguments
"""
Merging tools for REF_M
"""

# standard imports
import datetime
import json
import os
import sys
import time
from glob import glob
from typing import List, Tuple

# third party imports
import mantid
import mantid.simpleapi as api
import numpy as np
import pandas
import pytz

# mr_reduction iports
import mr_reduction
from mr_reduction.runpeak import RunPeakNumber
from mr_reduction.script_output import write_reduction_script, write_tunable_reduction_script
from mr_reduction.settings import ar_out_dir, nexus_data_dir


def match_run_for_cross_section(run, ipts, cross_section, extra_search_dir=None) -> List[str]:
    """Return a list of matching runs (or RunPeakNumber's) to be stitched

    Examples
    --------
    >>> match_run_for_cross_section("1234", "IPTS-42666", "Off_Off")
    ["1233", "1234"]

    >>> match_run_for_cross_section("1234_2", "IPTS-42666", "Off_On")
    ["1234_2", "1235_2"]

    Parameters
    ----------
    run: str, RunPeakNumber
        Run number (e.g. "12345") or RunPeakNumber (e.g. "12345_2")
    ipts: str
        experiment identifier e.g. "IPTS-42666"

    cross_section: str
        polarization entry. One of "Off_Off", "On_Off", "Off_On", and "On_On"

    extra_search_dir: Optional[None]
        additional directory to look for matching runs for stitching

    Returns
    -------
    List[str]
    """
    runpeak = RunPeakNumber(run)
    peak_number = runpeak.peak_number

    # assemble the list of search directories
    search_dirs = list()
    if extra_search_dir is not None and os.path.isdir(extra_search_dir):
        search_dirs.append(extra_search_dir)
    if ar_out_dir(ipts) not in search_dirs:
        search_dirs.append(ar_out_dir(ipts))

    _previous_q_min = 0
    _previous_q_max = 0

    api.logger.notice("Matching for IPTS-%s r%s [%s]" % (ipts, run, cross_section))
    matched_runs = []
    series_end = False
    for i in range(10):  # search the previous 10 runs
        if series_end:
            break
        i_runpeak = RunPeakNumber(runpeak.run_number - i, runpeak.peak_number)
        for search_dir in search_dirs:
            file_path = os.path.join(search_dir, f"REF_M_{i_runpeak}_{cross_section}_autoreduce.dat")
            if os.path.isfile(file_path):
                if RunPeakNumber(i_runpeak).peak_number != peak_number:
                    continue  # peak numbers must be the same
                ref_data = pandas.read_csv(file_path, sep=r"\s+", comment="#", names=["q", "r", "dr", "dq", "a"])
                q_min = min(ref_data["q"])
                q_max = max(ref_data["q"])
                api.logger.notice("%s: [%s %s]" % (i_runpeak, q_min, q_max))

                if (q_max < _previous_q_max and q_max > _previous_q_min) or _previous_q_max == 0:
                    _previous_q_max = q_max
                    _previous_q_min = q_min
                    matched_runs.insert(0, str(i_runpeak))
                else:  # previous runs won't be a match, thus exit the `for i in range(10)` loop
                    series_end = True

                break  # no need to search in the other search directories

    return matched_runs


def _extract_sequence_id(file_path):
    """Extract the sequence_id from an autoreduced data file (REF_M_*_autoreduce.dat)

    The sequence_id indicates the first run number having the same peak(s) as the current
    run number. For instance, if the run number being reduced is 41447 and the sequence_id is 41445, it means
    that experiments with run numbers 41445, 41446, and 41447 were all done with the same peak(s) and same
    experiment configuation.

    Parameters
    ----------
    file_path: str
        File to process

    Returns
    -------
    Tuple[str, str, Optional[float]]
        run_peak_number str: RunPeakNumber's that were reduced
        group_id str: sequence_id
        lowest_q: float
    """
    assert file_path.endswith("autoreduce.dat"), "Input file is not an autoreduced data file"
    run_peak_number, group_id, lowest_q = None, None, None
    if os.path.isfile(file_path):
        with open(file_path, "r") as fd:
            for line in fd.readlines():
                if line.startswith("# sequence_id"):
                    try:
                        group_id = int(line[len("# sequence_id") :].strip())
                    except:  # noqa E722
                        api.logger.error("Could not extract group id from line: %s" % line)
                if line.startswith("# Input file indices:"):
                    try:
                        run_peak_number = line[len("# Input file indices:") :].strip()
                    except:  # noqa E722
                        api.logger.error("Could not extract run number from line: %s" % line)
                if not line.startswith("#") and len(line.strip()) > 0:
                    try:
                        toks = line.split()
                        lowest_q = float(toks[0])
                    except:  # noqa E722
                        api.logger.error("Could not extract lowest q from line: %s" % line)
                if all(x is not None for x in [run_peak_number, group_id, lowest_q]):
                    return run_peak_number, group_id, lowest_q
    return run_peak_number, group_id, lowest_q


def match_run_with_sequence(run, ipts, cross_section, extra_search_dir=None):
    r"""List of matching runs (or RunPeakNumber's) to be stitched.

        Matching runs are searched in `search_dir` as well as in the canonical aoutoreduce directory,
        /SNS/REF_M/IPTS-XXXX/shared/autoreduce.

        Examples
        --------
        >>> match_run_with_sequence("1234", "IPTS-42666", "Off_Off")
        ["1233", "1234"]

        >>> match_run_with_sequence("1234_2", "IPTS-42666", "Off_On")
        ["1233_2", "1234_2"]

        Parameters
        ----------
        run: str, RunPeakNumber
            Run number (e.g. "12345") or RunPeakNumber (e.g. "12345_2")
        ipts: str
            experiment identifier e.g. "IPTS-42666"
        cross_section: str
            polarization entry. One of "Off_Off", "On_Off", "Off_On", and "On_On"
    `    extra_search_dir: Optional[str]
            additional directory to find matching runs`

        Returns
        -------
        List[str]
    """
    runpeak = RunPeakNumber(run)
    peak_number = runpeak.peak_number
    api.logger.notice(f"Matching sequence for {ipts} r{runpeak} [{cross_section}]")

    # assemble the list of data directories
    data_dirs = list()
    if extra_search_dir is not None and os.path.isdir(extra_search_dir):
        data_dirs.append(extra_search_dir)
    if ar_out_dir(ipts) not in data_dirs:
        data_dirs.append(ar_out_dir(ipts))

    # Check to see if we have the sequence_id information
    group_id = None
    for data_dir in data_dirs:
        file_path = os.path.join(data_dir, f"REF_M_{runpeak}_{cross_section}_autoreduce.dat")
        if os.path.isfile(file_path):
            _, group_id, _ = _extract_sequence_id(file_path)
            break

    # If we don't have a group id, just group together runs of increasing q-values
    if group_id is None:
        return match_run_for_cross_section(runpeak, ipts, cross_section, extra_search_dir=extra_search_dir)

    matched_runs = []  # list of [run-number, lowest-q] pairs
    _lowest_q_available = True
    for data_dir in data_dirs:
        for file_path in glob(os.path.join(data_dir, f"REF_M_*_{cross_section}_autoreduce.dat")):
            _runpeak, _group_id, lowest_q = _extract_sequence_id(file_path)
            if _runpeak in [m[0] for m in matched_runs]:
                continue  # this matching run number has been found in a previous data directory
            if RunPeakNumber(_runpeak).peak_number != peak_number:
                continue  # the peak numbers must be the same
            if _group_id == group_id:
                matched_runs.append([str(_runpeak), lowest_q])
                _lowest_q_available = _lowest_q_available and lowest_q is not None
    if _lowest_q_available:  # sort by lowest-q
        match_series = [item[0] for item in sorted(matched_runs, key=lambda a: a[1])]
    else:  # sort by run-number
        match_series = [item[0] for item in sorted(matched_runs, key=lambda a: a[0])]
    return match_series


def compute_scaling_factors(
    matched_runs, ipts, cross_section, extra_search_dir=None
) -> Tuple[List[float], str, str, str, str]:
    r"""Compute the scaling factors for an input set of runs (or RunPeakNumber's) by comparing with
    direct-beam runs having the same instrument configuration as the `matched_runs`.

    Compute the successive scaling factors for an input set of runs (or RunPeakNumber's) ordered by increasing Q as
    we stitch one after the other.

    Parameters
    ----------
    matched_runs: List[str]
        List of RunPeakNumber's (e.g. ['1234', '1235'] or ['1234_2', '1235_2']) if reducing only the second
        peak is present in the experiments. Runs are ordered by increasing Q, which are to be reduced and
        stitched together.
    ipts: str
        Experiment identifier (e.g. 'IPTS-42666')
    cross_section: str
            polarization entry. One of "Off_Off", "On_Off", "Off_On", and "On_On"
    extra_search_dir: str
        Directory where to find the reduced matching runs, in addition to the canonicalautoreduce
        directory /SNS/REF_M/IPTS-XXXX/shared/autoreduce

    Returns
    -------
    Tuple[List[float], str, str, str, str]
        scaling_factors: List[float]
        direct_beam_info: str
        data_info: str
        data_buffer: str
        _cross_section_label: str Polarization state
    """
    _previous_ws = None
    running_scale = 1.0
    direct_beam_info = ""
    data_buffer = ""
    data_info = ""
    _cross_section_label = cross_section

    direct_beam_count = 0
    run_count = 0
    scaling_factors = [1.0]

    search_dirs = list()
    if extra_search_dir is not None and os.path.isdir(extra_search_dir):
        search_dirs.append(extra_search_dir)
    search_dirs.append(ar_out_dir(ipts))

    for i_runpeak in matched_runs:
        for search_dir in search_dirs:
            file_path = os.path.join(search_dir, "REF_M_%s_%s_autoreduce.dat" % (i_runpeak, cross_section))
            if os.path.isfile(file_path):
                _file_handle = open(file_path, "r")
                ref_data = pandas.read_csv(_file_handle, sep=r"\s+", comment="#", names=["q", "r", "dr", "dq", "a"])

                ws = api.CreateWorkspace(DataX=ref_data["q"], DataY=ref_data["r"], DataE=ref_data["dr"])
                ws = api.ConvertToHistogram(ws)
                if _previous_ws is not None:
                    _, scale = api.Stitch1D(_previous_ws, ws)
                    running_scale *= scale
                    scaling_factors.append(running_scale)
                _previous_ws = api.CloneWorkspace(ws)

                # Rewind and get meta-data
                _file_handle.seek(0)
                _direct_beams_started = 0
                _data_runs_started = 0
                for line in _file_handle.readlines():
                    # Look for cross-section label
                    if line.find("Extracted states:") > 0:
                        toks = line.split(":")
                        if len(toks) > 1:
                            _cross_section_label = toks[1].strip()

                    # If we are in the data run block, copy the data we need
                    if _data_runs_started == 1 and line.find(str(i_runpeak)) > 0:
                        toks = ["%8s" % t for t in line.split()]
                        if len(toks) > 10:
                            toks[1] = "%8g" % scaling_factors[run_count]
                            run_count += 1
                            toks[14] = "%8s" % str(run_count)
                            _line = "  ".join(toks).strip() + "\n"
                            data_info += _line.replace("# ", "#")

                    # Find out whether we started the direct beam block
                    if line.find("Data Runs") > 0:
                        _direct_beams_started = 0
                        _data_runs_started = 1

                    # Get the direct beam info
                    if _direct_beams_started == 2:
                        toks = ["%8s" % t for t in line.split()]
                        if len(toks) > 10:
                            direct_beam_count += 1
                            toks[1] = "%8g" % direct_beam_count
                            _line = "  ".join(toks).strip() + "\n"
                            direct_beam_info += _line.replace("# ", "#")

                    # If we are in the direct beam block, we need to skip the column info line
                    if _direct_beams_started == 1 and line.find("DB_ID") > 0:
                        _direct_beams_started = 2

                    # Find out whether we started the direct beam block
                    if line.find("Direct Beam Runs") > 0:
                        _direct_beams_started = 1

                for i in range(len(ref_data["q"])):
                    data_buffer += "%12.6g  %12.6g  %12.6g  %12.6g  %12.6g\n" % (
                        ref_data["q"][i],
                        running_scale * ref_data["r"][i],
                        running_scale * ref_data["dr"][i],
                        ref_data["dq"][i],
                        ref_data["a"][i],
                    )
                break  # no need to search in the other search directories

    return scaling_factors, direct_beam_info, data_info, data_buffer, _cross_section_label


def apply_scaling_factors(
    matched_runs, ipts, cross_section, scaling_factors, extra_search_dir=None
) -> List[Tuple[str, str]]:
    r"""Apply the scaling factors (used for stitching) that were computed with the cross-section having the highest
    event count to rescale the reflectivity profiles of the other cross-sections.

    The goals is to stitch the data runs for the other cross sections using the scaling factors computed with the
    events from the cross-section having the highest event count.

    Parameters
    ----------
    matched_runs: List[str]
        List of RunPeakNumber's (e.g. ['1234', '1235'] or ['1234_2', '1235_2']) if reducing only the second
        peak is present in the experiments. Runs are ordered by increasing Q, which are to be reduced and
        stitched together.
    ipts: str
        Experiment identifier (e.g. 'IPTS-42666')
    cross_section: str
        polarization entry. One of "Off_Off", "On_Off", "Off_On", and "On_On". It should be the cross section
        with the highest event count.
    scaling_factors: List[float]
        Numbers by which to multiply each matched reflectivity curve, when stitching
    extra_search_dir: Optional[str]
        additional directory where to find matching partial scripts for the matching runs. Search is also
        carried out on the canonical autoreduce directory /SNS/REF_M/IPTS-XXXX/shared/autoreduce

    Returns
    -------
    List[Tuple[str, str]]
        Rescaled reflectiviy profiles of the other cross-sections. One entry per cross section other than
        input `cross_section`, e.g ('On_Off', '0.02344 5.666 ....'), ("On_On", '')
    """

    search_dirs = list()
    if extra_search_dir is not None and os.path.isdir(extra_search_dir):
        search_dirs.append(extra_search_dir)
    if ar_out_dir(ipts) not in search_dirs:
        search_dirs.append(ar_out_dir(ipts))

    data_buffers = []
    for xs in ["Off_Off", "On_Off", "Off_On", "On_On"]:
        # Skip the cross section that we computed the scaling factors with since we havce that data already
        if xs == cross_section:
            continue
        data_buffer = ""

        for j, i_runpeak in enumerate(matched_runs):
            for search_dir in search_dirs:
                file_path = os.path.join(search_dir, "REF_M_%s_%s_autoreduce.dat" % (i_runpeak, xs))
                if os.path.isfile(file_path):
                    with open(file_path, "r") as file_handle:
                        ref_data = pandas.read_csv(
                            file_handle, sep=r"\s+", comment="#", names=["q", "r", "dr", "dq", "a"]
                        )
                    for i in range(len(ref_data["q"])):
                        data_buffer += "%12.6g  %12.6g  %12.6g  %12.6g  %12.6g\n" % (
                            ref_data["q"][i],
                            scaling_factors[j] * ref_data["r"][i],
                            scaling_factors[j] * ref_data["dr"][i],
                            ref_data["dq"][i],
                            ref_data["a"][i],
                        )
                    break  # no need to search in the other search directory

        data_buffers.append((xs, data_buffer))
    return data_buffers


def select_cross_section(run, ipts, extra_search_dir=None):
    r"""Select the cross-section with the lowest relative error

    Parameters
    ----------
    run: str, RunPeakNumber
        Run number (e.g. "12345") or RunPeakNumber (e.g. "12345_2")
    ipts: str
        experiment identifier e.g. "IPTS-42666"
    extra_search_dir: Optional[str]
        additional directory where to find reflectivity profiles for each cross section of the matching runs.
        Search will also be carried out the canonical autoreduce directory /SNS/REF_M/IPTS-XXXX/shared/autoreduce

    Returns
    -------
    str
        One of "Off_Off", "On_Off", "Off_On", and "On_On"
    """
    search_dirs = list()
    if extra_search_dir is not None and os.path.isdir(extra_search_dir):
        search_dirs.append(extra_search_dir)
    if ar_out_dir(ipts) not in search_dirs:
        search_dirs.append(ar_out_dir(ipts))

    runpeak = RunPeakNumber(run)  # e.g. "12345" or "12345_2"
    best_xs = None
    best_error = None

    for xs in ["Off_Off", "On_Off", "Off_On", "On_On"]:
        for search_dir in search_dirs:
            file_path = os.path.join(search_dir, f"REF_M_{runpeak}_{xs}_autoreduce.dat")
            if os.path.isfile(file_path):
                api.logger.notice("Found: %s" % file_path)
                ref_data = pandas.read_csv(file_path, sep=r"\s+", comment="#", names=["q", "r", "dr", "dq", "a"])
                relative_error = np.sum(ref_data["dr"] * ref_data["dr"]) / np.sum(ref_data["r"])
                if best_xs is None or relative_error < best_error:
                    best_xs = xs
                    best_error = relative_error
                break  # no need to search in the other search directory
    return best_xs


def write_reflectivity_cross_section(
    runpeak, ipts, cross_section, matched_runs, direct_beam_info, data_info, data_buffer, xs_label, output_dir=None
) -> str:
    r"""

    Parameters
    ----------
    runpeak: str
        Run number (e.g. "12345") or RunPeakNumber (e.g. "12345_2") with the lowest Q-range among all data
        runs to be stitched together.
    ipts: str
        Experiment identifier (e.g. "IPTS-42666")
    cross_section: str
        Polarization entry. One of "Off_Off", "On_Off", "Off_On", or "On_On"
    matched_runs: List[str]
        List of RunPeakNumber's (e.g. ['1234', '1235'] or ['1234_2', '1235_2']) if reducing only the second
        peak is present in the experiments. Runs are ordered by increasing Q, which are to be reduced and
        stitched together.
    direct_beam_info: str
        Configuration for the "reduction" of the direct beam run. Items are
        DB_ID, P0, PN, x_pos, x_width, y_pos, y_width, bg_pos, bg_width, dpix, tth, runnumber, filepath]
    data_info: str
    data_buffer: str
        Stitched reflectivity profiles
    xs_label: str
        Cross section label. One of "Off-Off", "On-Off", "Off-On", or "On-On"
    output_dir: str
        Directory where to write the reduction script. If `None`, defaults to the canonical autoreduce
        directory /SNS/REF_M/IPTS-XXXX/shared/autoreduce

    Returns
    -------
    str
        File path to the reflectivity profile
    """
    direct_beam_options = [
        "DB_ID",
        "P0",
        "PN",
        "x_pos",
        "x_width",
        "y_pos",
        "y_width",
        "bg_pos",
        "bg_width",
        "dpix",
        "tth",
        "number",
        "File",
    ]
    dataset_options = [
        "scale",
        "P0",
        "PN",
        "x_pos",
        "x_width",
        "y_pos",
        "y_width",
        "bg_pos",
        "bg_width",
        "fan",
        "dpix",
        "tth",
        "number",
        "DB_ID",
        "File",
    ]

    if output_dir is None or os.path.isdir(output_dir) is False:
        output_dir = ar_out_dir(ipts)
    file_path = os.path.join(output_dir, "REF_M_%s_%s_combined.dat" % (runpeak, cross_section))
    with open(file_path, "w") as fd:
        fd.write(f"# Datafile created by mr_reduction {mr_reduction.__version__}\n")
        fd.write("# Datafile created by Mantid %s\n" % mantid.__version__)
        fd.write("# Date: %s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
        fd.write("# Type: Specular\n")
        fd.write("# Input file indices: %s\n" % ",".join(matched_runs))
        fd.write("# Extracted states: %s\n" % xs_label)
        fd.write("#\n")
        fd.write("# [Direct Beam Runs]\n")
        toks = ["%8s" % item for item in direct_beam_options]
        fd.write("# %s\n" % "  ".join(toks))
        fd.write(direct_beam_info)
        fd.write("#\n")
        fd.write("# [Data Runs]\n")
        toks = ["%8s" % item for item in dataset_options]
        fd.write("# %s\n" % "  ".join(toks))
        fd.write(data_info)
        fd.write("#\n")
        fd.write("# [Global Options]\n")
        fd.write("# name           value\n")
        fd.write("# sample_length  10\n")
        fd.write("#\n")
        fd.write("# [Data]\n")
        toks = ["%12s" % item for item in ["Qz [1/A]", "R [a.u.]", "dR [a.u.]", "dQz [1/A]", "theta [rad]"]]
        fd.write("# %s\n" % "  ".join(toks))
        fd.write(data_buffer)
    return file_path


def plot_combined(matched_runs, scaling_factors, ipts, extra_search_dir=None, publish=True):
    r"""Create plotly figures for the reflectivity profile of each cross section, and embed them in an <div> container.

    Parameters
    ----------
    matched_runs: List[str]
        List of RunPeakNumber's (e.g. ['1234', '1235'] or ['1234_2', '1235_2']) if reducing only the second
        peak is present in the experiments. Runs are ordered by increasing Q, which are to be reduced and
        stitched together.
    scaling_factors: List[float]
        Numbers by which to multiply each matched reflectivity curve, when stitching
    ipts: str
        Experiment identifier (e.g. "IPTS-42666")
    extra_search_dir: Optional[str]
        additional directory where to find reflectivity profiles for each cross section of the matching runs.
        Search will also be carried out the canonical autoreduce directory /SNS/REF_M/IPTS-XXXX/shared/autoreduce
    publish: bool
        if True, store the HTML page in the livedata server

    Returns
    -------
    str
        The contents inside the <div>..</div> element
    """
    search_dirs = list()
    if extra_search_dir is not None and os.path.isdir(extra_search_dir):
        search_dirs.append(extra_search_dir)
    if ar_out_dir(ipts) not in search_dirs:
        search_dirs.append(ar_out_dir(ipts))

    # Collect reflectivity profiles for each cross section
    data_names = []  # list of cross sections
    data_list = []  # a list of reflectivity profiles with columns Q, r, and dr. One profile for each cross section
    for i, runpeak in enumerate(matched_runs):
        for xs in ["Off_Off", "On_Off", "Off_On", "On_On"]:
            for search_dir in search_dirs:
                file_path = os.path.join(search_dir, "REF_M_%s_%s_autoreduce.dat" % (runpeak, xs))
                if os.path.isfile(file_path):
                    ref_data = pandas.read_csv(file_path, sep=r"\s+", comment="#", names=["q", "r", "dr", "dq", "a"])
                    data_list.append(
                        [ref_data["q"], scaling_factors[i] * ref_data["r"], scaling_factors[i] * ref_data["dr"]]
                    )
                    data_names.append("r%s [%s]" % (runpeak, xs))
                    break  # no need to search in the other search directory

    try:
        # Depending on where we run, we might get our publisher from different places, or not at all.
        try:  # version on autoreduce
            from postprocessing.publish_plot import plot1d
        except ImportError:  # version on instrument computers
            from finddata.publish_plot import plot1d
        if data_names:
            return plot1d(
                RunPeakNumber(matched_runs[-1]).run_number,
                data_list,
                data_names=data_names,
                instrument="REF_M",
                x_title="Q (1/A)",
                x_log=False,
                y_title="Reflectivity",
                y_log=True,
                show_dx=False,
                publish=publish,
            )
        else:
            api.logger.notice("Nothing to plot")
    except:  # noqa E722
        api.logger.error(str(sys.exc_info()[1]))
        api.logger.error("No publisher module found")
    return None


def combined_curves(run, ipts, output_dir=None):
    r"""Stitch reflectivity curves from different runs of the same group.

    Runs of the same group were produced with the same sample and different incident angle

    Parameters
    ----------
    run: str, RunPeakNumber
        Run number (e.g. "12345") or RunPeakNumber (e.g. "12345_2")
    ipts: str
        e.g. "IPTS-21391"
    output_dir: Optional[str]
        directory where to write the stitched reflectivity curve. Defaults to the canonical autoreduce
        directory /SNS/REF_M/IPTS-XXXX/shared/autoreduce

    Returns
    -------
    Tuple[List[str], List[float], List[str]]
        matched_runs: List[str] Data runs (or RunPeakNumber's) ordered by increasing Q, to be stitched together
        scaling_factors: List[float] numbers by which to multiply each matched reflectivity curve, when stitching
        file_list: List[str]] paths to the reflectivity profile files, one file for each cross section.
    """
    runpeak = RunPeakNumber(run)  # e.g. "12345", "12345_2"
    # Select the cross section with the best statistics
    high_stat_xs = select_cross_section(runpeak, ipts, extra_search_dir=output_dir)
    api.logger.notice("High xs: %s" % high_stat_xs)

    # Match the given run with previous runs if they are overlapping in Q
    matched_runs = match_run_with_sequence(runpeak, ipts, high_stat_xs, extra_search_dir=output_dir)
    api.logger.notice("Matched runs: %s" % str(matched_runs))

    # Compute scaling factors for this cross section
    try:
        scaling_factors, direct_beam_info, data_info, data_buffer, xs_label = compute_scaling_factors(
            matched_runs, ipts, high_stat_xs, extra_search_dir=output_dir
        )
    except:  # noqa E722
        return matched_runs, np.ones(len(matched_runs)), [""] * len(matched_runs)

    # Write combined python script
    write_reduction_script(matched_runs, scaling_factors, ipts, output_dir=output_dir, extra_search_dir=output_dir)
    write_tunable_reduction_script(matched_runs, scaling_factors, ipts, output_dir=output_dir)

    xs_buffers = apply_scaling_factors(matched_runs, ipts, high_stat_xs, scaling_factors, extra_search_dir=output_dir)
    xs_buffers.append((high_stat_xs, data_buffer))

    file_list = []
    for item in xs_buffers:  # e.g ('On_On', '0.00345  9.92443 ...')
        if item[1]:  # reflectivity profile exists for the selected cross-section
            _file_path = write_reflectivity_cross_section(
                matched_runs[0],
                ipts,
                item[0],
                matched_runs,
                direct_beam_info,
                data_info,
                item[1],
                xs_label,
                output_dir=output_dir,
            )
            file_list.append(_file_path)

    return matched_runs, scaling_factors, file_list


def combined_catalog_info(matched_runs, ipts, output_files, output_dir=None, run_peak_number=None) -> str:
    r"""Produce cataloging information for reduced data and save to file in JSON format.

    Parameters
    ----------
    matched_runs: List[str]
        List of RunPeakNumber's (e.g. ['1234', '1235'] or ['1234_2', '1235_2']) if reducing only the second
        sample present in the experiments. Runs are ordered by increasing Q, which are to be reduced and
        stitched together.
    ipts: str
        Experiment identifier (e.g. "IPTS-42666")
    output_files: List[str]]
        Paths to the reflectivity profile files, one file for each cross section.
    output_dir: Optional[str]
        directory where to write the catalog file. Defaults to the canonical autoreduce
        directory /SNS/REF_M/IPTS-XXXX/shared/autoreduce
    run_peak_number: str
        run-sample number (e.g. '12345' or '12345_2') we want to associate this reduction with. If `None`, pick
        the first run-sample number from `matched_runs`

    Returns
    -------
    str
        File path to the JSON file containing the catalog info, its name is f"REF_M_{run_peak_number}.json"
    """
    NEW_YORK_TZ = pytz.timezone("America/New_York")
    info = dict(user="auto", created=NEW_YORK_TZ.localize(datetime.datetime.now()).isoformat(), metadata=dict())

    # List of input files
    input_list = []
    for runpeak in matched_runs:
        data_filename = f"REF_M_{RunPeakNumber(runpeak).run_number}.nxs.h5"
        data_file = os.path.join(nexus_data_dir(ipts), data_filename)
        if os.path.isfile(data_file):
            input_list.append(dict(location=data_file, type="raw", purpose="sample-data"))
    info["input_files"] = input_list

    # List of output files
    output_list = []
    for runpeak in output_files:
        output_list.append(dict(location=runpeak, type="processed", purpose="reduced-data", fields=dict()))
    info["output_files"] = output_list

    if output_dir is None or os.path.isdir(output_dir) is False:
        output_dir = ar_out_dir(ipts)
    if run_peak_number is None:
        run_peak_number = matched_runs[0]
    json_path = os.path.join(output_dir, f"REF_M_{run_peak_number}.json")
    with open(json_path, "w") as fd:
        fd.write(json.dumps(info, indent=4))
    return json_path
