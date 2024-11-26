# pylint: disable=too-many-locals, too-many-branches, invalid-name
"""
This module provides functions to write reflectivity output files for reflectometry data.
It includes functions to generate and write reflectivity data to files in a format compatible
with QuickNXS and Mantid. The module handles both direct beam and scattering data, and ensures
the output files contain all necessary metadata and data points for further analysis.

Functions:
- write_reflectivity: Writes reflectivity data to an output file.
- quicknxs_scaling_factor: Computes a scaling factor for compatibility with QuickNXS.
"""

# standard imports
import math
import time
from dataclasses import asdict, dataclass
from typing import List, Optional

# third party imports
import mantid
from mantid.simpleapi import mtd

# mr_reduction imports
import mr_reduction
from mr_reduction.runpeak import RunPeakNumber
from mr_reduction.types import MantidWorkspace


@dataclass
class DirectBeamOptions:
    DB_ID: int
    P0: int
    PN: int
    x_pos: float  # peak center
    x_width: float  # peak width
    y_pos: float  # average background value
    y_width: float  # error in the background noise
    bg_pos: float
    bg_width: float
    dpix: float  # sample log entry "normalization_dirpix"
    tth: int
    number: int  # run number
    File: str  # normalization run in the re-processed and legacy-compatible, readable by QuickNXS

    @staticmethod
    def from_workspace(input_workspace: MantidWorkspace, direct_beam_counter=0) -> Optional["DirectBeamOptions"]:
        """Create an instance of DirectBeamOptions from a workspace."""
        run_object = mtd[str(input_workspace)].getRun()

        normalization_run = run_object.getProperty("normalization_run").value
        if normalization_run == "None":
            return None

        peak_min = run_object.getProperty("norm_peak_min").value
        peak_max = run_object.getProperty("norm_peak_max").value
        bg_min = run_object.getProperty("norm_bg_min").value
        bg_max = run_object.getProperty("norm_bg_max").value
        low_res_min = run_object.getProperty("norm_low_res_min").value
        low_res_max = run_object.getProperty("norm_low_res_max").value
        dpix = run_object.getProperty("normalization_dirpix").value
        filename = run_object.getProperty("normalization_file_path").value
        # In order to make the file loadable by QuickNXS, we have to change the
        # file name to the re-processed and legacy-compatible files.
        # The new QuickNXS can load both.
        if filename.endswith("nxs.h5"):
            filename = filename.replace("nexus", "data")
            filename = filename.replace(".nxs.h5", "_histo.nxs")

        return DirectBeamOptions(
            DB_ID=direct_beam_counter,
            P0=0,
            PN=0,
            x_pos=(peak_min + peak_max) / 2.0,
            x_width=peak_max - peak_min + 1,
            y_pos=(low_res_max + low_res_min) / 2.0,
            y_width=low_res_max - low_res_min + 1,
            bg_pos=(bg_min + bg_max) / 2.0,
            bg_width=bg_max - bg_min + 1,
            dpix=dpix,
            tth=0,
            number=normalization_run,
            File=filename,
        )

    @classmethod
    def dat_header(cls) -> str:
        """Header for the direct beam options in the *_autoreduced.dat file"""
        return "# [Direct Beam Runs]\n# %s\n" % "  ".join(["%8s" % field for field in cls.__dataclass_fields__])

    @property
    def options(self) -> List[str]:
        """List of option names"""
        return self.__dataclass_fields__

    @property
    def as_dat(self):
        """ "Formatted string representation of the DirectBeamOptions suitable for an *_autoreduced.dat file"""
        par_list = ["{%s}" % p for p in self.options]
        template = "# %s\n" % "  ".join(par_list)
        _clean_dict = {}
        for option in self.options:
            value = getattr(self, option)
            if isinstance(value, (bool, str)):
                _clean_dict[option] = "%8s" % value
            else:
                _clean_dict[option] = "%8g" % value
        return template.format(**_clean_dict)


def write_reflectivity(ws_list, output_path, cross_section) -> None:
    r"""Write out reflectivity output (usually from autoreduction, as file REF_M_*_autoreduce.dat)

    This function generates and writes reflectivity data to an output file, typically used in autoreduction processes.
    The output file is usually named in the format `REF_M_*_autoreduce.dat`.

    Parameters:
    ws_list (list): A list of workspace objects containing reflectivity data.
    output_path (str): The path where the output file will be written.
    cross_section (str): The cross-section information to be included in the output file.
    """
    # Sanity check
    if not ws_list:
        return

    fd = open(output_path, "w")

    fd.write(f"# Datafile created by mr_reduction QuickNXS {mr_reduction.__version__}\n")
    fd.write("# Datafile created by Mantid %s\n" % mantid.__version__)
    fd.write("# Autoreduced\n")
    fd.write("# Date: %s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
    fd.write("# Type: Specular\n")

    peak_number = RunPeakNumber.peak_number_log(ws_list[0])
    runpeak_list = [str(RunPeakNumber(str(ws.getRunNumber()), peak_number)) for ws in ws_list]
    fd.write(f"# Input file indices: {','.join(runpeak_list)}\n")

    fd.write("# Extracted states: %s\n" % cross_section)
    fd.write("#\n")

    # Direct beam section
    fd.write(DirectBeamOptions.dat_header())
    i_direct_beam = 0
    for ws in ws_list:
        i_direct_beam += 1
        direct_beam_options = DirectBeamOptions.from_workspace(ws, i_direct_beam)
        if direct_beam_options is not None:
            fd.write(direct_beam_options.as_dat)

    # Scattering data
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

    fd.write("#\n")
    fd.write("# [Data Runs]\n")
    toks = ["%8s" % item for item in dataset_options]
    fd.write("# %s\n" % "  ".join(toks))
    i_direct_beam = 0

    data_block = ""
    for ws in ws_list:
        i_direct_beam += 1

        run_object = ws.getRun()
        peak_min = run_object.getProperty("scatt_peak_min").value
        peak_max = run_object.getProperty("scatt_peak_max").value
        bg_min = run_object.getProperty("scatt_bg_min").value
        bg_max = run_object.getProperty("scatt_bg_max").value
        low_res_min = run_object.getProperty("scatt_low_res_min").value
        low_res_max = run_object.getProperty("scatt_low_res_max").value
        dpix = run_object.getProperty("DIRPIX").getStatistics().mean
        # For live data, we might not have a file name
        if "Filename" in run_object:
            filename = run_object.getProperty("Filename").value
            # In order to make the file loadable by QuickNXS, we have to change the
            # file name to the re-processed and legacy-compatible files.
            # The new QuickNXS can load both.
            if filename.endswith("nxs.h5"):
                filename = filename.replace("nexus", "data")
                filename = filename.replace(".nxs.h5", "_histo.nxs")
        else:
            filename = "live data"
        constant_q_binning = run_object.getProperty("constant_q_binning").value
        scatt_pos = run_object.getProperty("specular_pixel").value
        # norm_x_min = run_object.getProperty("norm_peak_min").value
        # norm_x_max = run_object.getProperty("norm_peak_max").value
        # norm_y_min = run_object.getProperty("norm_low_res_min").value
        # norm_y_max = run_object.getProperty("norm_low_res_max").value

        # For some reason, the tth value that QuickNXS expects is offset.
        # It seems to be because that same offset is applied later in the QuickNXS calculation.
        # Correct tth here so that it can load properly in QuickNXS and produce the same result.
        tth = run_object.getProperty("two_theta").value
        det_distance = run_object["SampleDetDis"].getStatistics().mean
        # Check units
        if run_object["SampleDetDis"].units not in ["m", "meter"]:
            det_distance /= 1000.0
        direct_beam_pix = run_object["DIRPIX"].getStatistics().mean

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
        tth = ws.getRun().getProperty("two_theta").value * math.pi / 360.0
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
    if run_object.hasProperty("sequence_id"):
        fd.write("# sequence_id %s\n" % run_object.getProperty("sequence_id").value[0])
    if run_object.hasProperty("sequence_number"):
        fd.write("# sequence_number %s\n" % run_object.getProperty("sequence_number").value[0])
    if run_object.hasProperty("sequence_total"):
        fd.write("# sequence_total %s\n" % run_object.getProperty("sequence_total").value[0])
    fd.write("#\n")
    fd.write("# [Data]\n")
    toks = ["%12s" % item for item in ["Qz [1/A]", "R [a.u.]", "dR [a.u.]", "dQz [1/A]", "theta [rad]"]]
    fd.write("# %s\n" % "  ".join(toks))
    fd.write("#\n%s\n" % data_block)

    fd.close()


def quicknxs_scaling_factor(ws) -> float:
    """FOR COMPATIBILITY WITH QUICKNXS"""
    run_object = ws.getRun()
    peak_min = run_object.getProperty("scatt_peak_min").value
    peak_max = run_object.getProperty("scatt_peak_max").value + 1.0
    low_res_min = run_object.getProperty("scatt_low_res_min").value
    low_res_max = run_object.getProperty("scatt_low_res_max").value + 1.0
    norm_x_min = run_object.getProperty("norm_peak_min").value
    norm_x_max = run_object.getProperty("norm_peak_max").value + 1.0
    norm_y_min = run_object.getProperty("norm_low_res_min").value
    norm_y_max = run_object.getProperty("norm_low_res_max").value + 1.0
    tth = run_object.getProperty("two_theta").value * math.pi / 360.0
    quicknxs_scale = (float(norm_x_max) - float(norm_x_min)) * (float(norm_y_max) - float(norm_y_min))
    quicknxs_scale /= (float(peak_max) - float(peak_min)) * (float(low_res_max) - float(low_res_min))
    _scale = 0.005 / math.sin(tth) if tth > 0.0002 else 1.0
    quicknxs_scale *= _scale
    return quicknxs_scale
