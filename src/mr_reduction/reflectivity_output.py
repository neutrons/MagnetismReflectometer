"""
Write reflectivity output file
"""

# standard imports
import math
import time
from collections.abc import Sequence

import mantid

import mr_reduction
from mr_reduction.beam_options import DirectBeamOptions, ReflectedBeamOptions
from mr_reduction.runpeak import RunPeakNumber
from mr_reduction.simple_utils import SampleLogs

QUICKNXS_DATA_COLUMNS = ("Qz [1/A]", "R [a.u.]", "dR [a.u.]", "dQz [1/A]", "theta [rad]")


def quicknxs_file_header(input_file_indices: Sequence[str], extracted_states: str) -> str:
    """Header block required by QuickNXS reduced file reader."""
    run_indices = ",".join(map(str, input_file_indices))
    return (
        "# Datafile created by QuickNXS\n"
        f"# Datafile created using mr_reduction {mr_reduction.__version__}\n"
        f"# Datafile created using Mantid {mantid.__version__}\n"
        f"# Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        "# Type: Specular\n"
        f"# Input file indices: {run_indices}\n"
        f"# Extracted states: {extracted_states}\n"
        "#\n"
    )


def quicknxs_global_options_block(sample_length: float = 10) -> str:
    """Standard Global Options section for reduced data files."""
    return f"# [Global Options]\n# name           value\n# sample_length  {sample_length:g}\n#\n"


def quicknxs_data_header(include_separator: bool = False) -> str:
    """Data section header with the canonical 5-column reflectivity layout."""
    tokens = ["%12s" % item for item in QUICKNXS_DATA_COLUMNS]
    header = "# [Data]\n# %s\n" % "  ".join(tokens)
    if include_separator:
        header += "#\n"
    return header


def write_reflectivity(ws_list, output_path, cross_section):
    r"""Write out reflectivity output (usually from autoreduction, as file REF_M_*_autoreduce.dat)"""
    # Sanity check
    if not ws_list:
        return

    peak_number = RunPeakNumber.peak_number_log(ws_list[0])
    runpeak_list = [str(RunPeakNumber(str(ws.getRunNumber()), peak_number)) for ws in ws_list]

    with open(output_path, "w") as fd:
        fd.write(quicknxs_file_header(input_file_indices=runpeak_list, extracted_states=cross_section))

        #
        # Write direct beam options
        #
        fd.write(DirectBeamOptions.dat_header())
        for i_direct_beam, ws in enumerate(ws_list, start=1):
            direct_beam_options = DirectBeamOptions.from_workspace(ws, i_direct_beam)
            if direct_beam_options is not None:
                fd.write(direct_beam_options.as_dat)

        #
        # Write scattering options and collect scattering data for later
        fd.write("#\n")
        fd.write(ReflectedBeamOptions.dat_header())
        data_lines = []
        for i_direct_beam, ws in enumerate(ws_list, start=1):
            reflected_beam_options = ReflectedBeamOptions.from_workspace(ws, i_direct_beam)
            fd.write(reflected_beam_options.as_dat)
            # collect the numerical data into `data_lines`
            x, y, dy, dx = ws.readX(0), ws.readY(0), ws.readE(0), ws.readDx(0)
            theta = reflected_beam_options.tth * math.pi / 360.0
            sf = quicknxs_scaling_factor(ws)
            for i in range(len(x)):
                row = (x[i], y[i] * sf, dy[i] * sf, dx[i], theta)
                data_lines.append("%12.6g  %12.6g  %12.6g  %12.6g  %12.6g\n" % row)

        fd.write("#\n")
        fd.write(quicknxs_global_options_block())

        #
        # Write sequence information from the last workspace in the list
        #
        fd.write("# [Sequence]\n")
        sample_logs = SampleLogs(ws_list[-1])  # use the last workspace for the sequence information
        line_template = "# {0} {1}\n"
        for entry in ["sequence_id", "sequence_number", "sequence_total"]:
            if entry in sample_logs:
                fd.write(line_template.format(entry, sample_logs[entry]))

        #
        # Write scattering data
        #
        fd.write("#\n")
        fd.write(quicknxs_data_header(include_separator=True))
        fd.write("".join(data_lines))

        fd.write("\n")


def quicknxs_scaling_factor(ws) -> float:
    """FOR COMPATIBILITY WITH QUICKNXS"""
    sample_logs = SampleLogs(ws)
    peak_min = sample_logs["scatt_peak_min"]
    peak_max = sample_logs["scatt_peak_max"] + 1.0
    low_res_min = sample_logs["scatt_low_res_min"]
    low_res_max = sample_logs["scatt_low_res_max"] + 1.0
    norm_x_min = sample_logs["norm_peak_min"]
    norm_x_max = sample_logs["norm_peak_max"] + 1.0
    norm_y_min = sample_logs["norm_low_res_min"]
    norm_y_max = sample_logs["norm_low_res_max"] + 1.0
    tth = sample_logs["two_theta"] * math.pi / 360.0
    quicknxs_scale = (float(norm_x_max) - float(norm_x_min)) * (float(norm_y_max) - float(norm_y_min))
    quicknxs_scale /= (float(peak_max) - float(peak_min)) * (float(low_res_max) - float(low_res_min))
    _scale = 0.005 / math.sin(tth) if tth > 0.0002 else 1.0
    quicknxs_scale *= _scale
    return quicknxs_scale
