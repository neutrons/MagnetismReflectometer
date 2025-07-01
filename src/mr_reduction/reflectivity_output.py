"""
Write reflectivity output file
"""

# standard imports
import math
import time

# third party imports
import mantid

# mr_reduction imports
import mr_reduction
from mr_reduction.beam_options import DirectBeamOptions, ReflectedBeamOptions
from mr_reduction.runpeak import RunPeakNumber
from mr_reduction.simple_utils import SampleLogs


def write_reflectivity(ws_list, output_path, cross_section):
    r"""Write out reflectivity output (usually from autoreduction, as file REF_M_*_autoreduce.dat)"""
    # Sanity check
    if not ws_list:
        return

    fd = open(output_path, "w")

    #
    # Write header
    #
    peak_number = RunPeakNumber.peak_number_log(ws_list[0])
    runpeak_list = [str(RunPeakNumber(str(ws.getRunNumber()), peak_number)) for ws in ws_list]
    fd.write(f"""# Datafile created by mr_reduction {mr_reduction.__version__}
# Datafile created by Mantid {mantid.__version__}
# Autoreduced
# Date: {time.strftime("%Y-%m-%d %H:%M:%S")}
# Type: Specular
# Input file indices: {",".join(runpeak_list)}
# Extracted states: {cross_section}
#
""")

    #
    # Write direct beam options
    #
    fd.write(DirectBeamOptions.dat_header())
    for i_direct_beam, ws in enumerate(ws_list, start=1):
        direct_beam_options = DirectBeamOptions.from_workspace(ws, i_direct_beam)
        if direct_beam_options is not None:
            fd.write(direct_beam_options.as_dat)

    #
    # Write scattering options and collect scatting data for later
    #
    fd.write("#\n")
    fd.write(ReflectedBeamOptions.dat_header())
    data_block = ""  # collect the data for later
    for i_direct_beam, ws in enumerate(ws_list, start=1):
        reflected_beam_options = ReflectedBeamOptions.from_workspace(ws, i_direct_beam)
        fd.write(reflected_beam_options.as_dat)
        # collect the numerical data into `data_block`
        x, y, dy, dx = ws.readX(0), ws.readY(0), ws.readE(0), ws.readDx(0)
        theta = reflected_beam_options.tth * math.pi / 360.0
        sf = quicknxs_scaling_factor(ws)
        for i in range(len(x)):
            data_block += "%12.6g  %12.6g  %12.6g  %12.6g  %12.6g\n" % (x[i], y[i] * sf, dy[i] * sf, dx[i], theta)

    fd.write("""#
# [Global Options]
# name           value
# sample_length  10
#
""")

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
    tokens = ["%12s" % item for item in ["Qz [1/A]", "R [a.u.]", "dR [a.u.]", "dQz [1/A]", "theta [rad]"]]
    header = "# %s" % "  ".join(tokens)
    fd.write(f"""#
# [Data]
{header}
#
{data_block}
""")

    fd.close()


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
