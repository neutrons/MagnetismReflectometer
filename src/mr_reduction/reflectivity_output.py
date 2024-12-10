# pylint: disable=too-many-locals, too-many-branches, invalid-name
"""
Write reflectivity output file
"""

# standard imports
import math
import time

# third party imports
import mantid

# mr_reduction imports
from mr_reduction.runpeak import RunPeakNumber
from mr_reduction.simple_utils import SampleLogs


def write_reflectivity(ws_list, output_path, cross_section):
    r"""Write out reflectivity output (usually from autoreduction, as file REF_M_*_autoreduce.dat)"""
    # Sanity check
    if not ws_list:
        return

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

    fd = open(output_path, "w")
    fd.write("# Datafile created by QuickNXS 2.0.0\n")
    fd.write("# Datafile created by Mantid %s\n" % mantid.__version__)
    fd.write("# Autoreduced\n")
    fd.write("# Date: %s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
    fd.write("# Type: Specular\n")
    peak_number = RunPeakNumber.peak_number_log(ws_list[0])
    runpeak_list = [str(RunPeakNumber(str(ws.getRunNumber()), peak_number)) for ws in ws_list]
    fd.write(f"# Input file indices: {','.join(runpeak_list)}\n")
    fd.write("# Extracted states: %s\n" % cross_section)
    fd.write("#\n")
    fd.write("# [Direct Beam Runs]\n")
    toks = ["%8s" % item for item in direct_beam_options]
    fd.write("# %s\n" % "  ".join(toks))

    # Direct beam section
    i_direct_beam = 0
    for ws in ws_list:
        i_direct_beam += 1
        sample_logs = SampleLogs(ws)
        normalization_run = sample_logs["normalization_run"]
        if normalization_run == "None":
            continue
        peak_min = sample_logs["norm_peak_min"]
        peak_max = sample_logs["norm_peak_max"]
        bg_min = sample_logs["norm_bg_min"]
        bg_max = sample_logs["norm_bg_max"]
        low_res_min = sample_logs["norm_low_res_min"]
        low_res_max = sample_logs["norm_low_res_max"]
        dpix = sample_logs["normalization_dirpix"]
        filename = sample_logs["normalization_file_path"]
        # In order to make the file loadable by QuickNXS, we have to change the
        # file name to the re-processed and legacy-compatible files.
        # The new QuickNXS can load both.
        if filename.endswith("nxs.h5"):
            filename = filename.replace("nexus", "data")
            filename = filename.replace(".nxs.h5", "_histo.nxs")

        item = dict(
            DB_ID=i_direct_beam,
            tth=0,
            P0=0,
            PN=0,
            x_pos=(peak_min + peak_max) / 2.0,
            x_width=peak_max - peak_min + 1,
            y_pos=(low_res_max + low_res_min) / 2.0,
            y_width=low_res_max - low_res_min + 1,
            bg_pos=(bg_min + bg_max) / 2.0,
            bg_width=bg_max - bg_min + 1,
            dpix=dpix,
            number=normalization_run,
            File=filename,
        )

        par_list = ["{%s}" % p for p in direct_beam_options]
        template = "# %s\n" % "  ".join(par_list)
        _clean_dict = {}
        for key in item:
            if isinstance(item[key], (bool, str)):
                _clean_dict[key] = "%8s" % item[key]
            else:
                _clean_dict[key] = "%8g" % item[key]
        fd.write(template.format(**_clean_dict))

    # Scattering data
    fd.write("#\n")
    fd.write("# [Data Runs]\n")
    toks = ["%8s" % item for item in dataset_options]
    fd.write("# %s\n" % "  ".join(toks))
    i_direct_beam = 0

    data_block = ""
    for ws in ws_list:
        i_direct_beam += 1

        sample_logs = SampleLogs(ws)
        peak_min = sample_logs["scatt_peak_min"]
        peak_max = sample_logs["scatt_peak_max"]
        bg_min = sample_logs["scatt_bg_min"]
        bg_max = sample_logs["scatt_bg_max"]
        low_res_min = sample_logs["scatt_low_res_min"]
        low_res_max = sample_logs["scatt_low_res_max"]
        dpix = sample_logs.mean("DIRPIX")
        # For live data, we might not have a file name
        if "Filename" in sample_logs:
            filename = sample_logs["Filename"]
            # In order to make the file loadable by QuickNXS, we have to change the
            # file name to the re-processed and legacy-compatible files.
            # The new QuickNXS can load both.
            if filename.endswith("nxs.h5"):
                filename = filename.replace("nexus", "data")
                filename = filename.replace(".nxs.h5", "_histo.nxs")
        else:
            filename = "live data"
        constant_q_binning = sample_logs["constant_q_binning"]
        scatt_pos = sample_logs["specular_pixel"]

        # For some reason, the tth value that QuickNXS expects is offset.
        # It seems to be because that same offset is applied later in the QuickNXS calculation.
        # Correct tth here so that it can load properly in QuickNXS and produce the same result.
        tth = sample_logs["two_theta"]
        det_distance = sample_logs.mean("SampleDetDis")
        # Check units
        if sample_logs.property("SampleDetDis").units not in ["m", "meter"]:
            det_distance /= 1000.0
        direct_beam_pix = sample_logs.mean("DIRPIX")

        # Get pixel size from instrument properties
        if ws.getInstrument().hasParameter("pixel-width"):
            pixel_width = float(ws.getInstrument().getNumberParameter("pixel-width")[0]) / 1000.0
        else:
            pixel_width = 0.0007
        tth -= ((direct_beam_pix - scatt_pos) * pixel_width) / det_distance * 180.0 / math.pi

        item = dict(
            scale=1,
            DB_ID=i_direct_beam,
            P0=0,
            PN=0,
            tth=tth,
            fan=constant_q_binning,
            x_pos=scatt_pos,
            x_width=peak_max - peak_min + 1,
            y_pos=(low_res_max + low_res_min) / 2.0,
            y_width=low_res_max - low_res_min + 1,
            bg_pos=(bg_min + bg_max) / 2.0,
            bg_width=bg_max - bg_min + 1,
            dpix=dpix,
            number=str(ws.getRunNumber()),
            File=filename,
        )

        par_list = ["{%s}" % p for p in dataset_options]
        template = "# %s\n" % "  ".join(par_list)
        _clean_dict = {}
        for key in item:
            if isinstance(item[key], str):
                _clean_dict[key] = "%8s" % item[key]
            else:
                _clean_dict[key] = "%8g" % item[key]
        fd.write(template.format(**_clean_dict))

        x = ws.readX(0)
        y = ws.readY(0)
        dy = ws.readE(0)
        dx = ws.readDx(0)
        tth = sample_logs["two_theta"] * math.pi / 360.0
        quicknxs_scale = quicknxs_scaling_factor(ws)
        for i in range(len(x)):
            data_block += "%12.6g  %12.6g  %12.6g  %12.6g  %12.6g\n" % (
                x[i],
                y[i] * quicknxs_scale,
                dy[i] * quicknxs_scale,
                dx[i],
                tth,
            )

    fd.write("#\n")
    fd.write("# [Global Options]\n")
    fd.write("# name           value\n")
    # TODO: set the sample dimension as an option
    fd.write("# sample_length  10\n")
    fd.write("#\n")
    fd.write("# [Sequence]\n")
    sample_logs = SampleLogs(ws_list[-1])  # sample logs of the last workspace
    if "sequence_id" in sample_logs:
        fd.write("# sequence_id %s\n" % sample_logs["sequence_id"])
    if "sequence_number" in sample_logs:
        fd.write("# sequence_number %s\n" % sample_logs["sequence_number"])
    if "sequence_total" in sample_logs:
        fd.write("# sequence_total %s\n" % sample_logs["sequence_total"])
    fd.write("#\n")
    fd.write("# [Data]\n")
    toks = ["%12s" % item for item in ["Qz [1/A]", "R [a.u.]", "dR [a.u.]", "dQz [1/A]", "theta [rad]"]]
    fd.write("# %s\n" % "  ".join(toks))
    fd.write("#\n%s\n" % data_block)

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
