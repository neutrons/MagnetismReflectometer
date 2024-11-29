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
from dataclasses import dataclass, field
from typing import List, Optional

# third party imports
import mantid

# mr_reduction imports
import mr_reduction
from mr_reduction.runpeak import RunPeakNumber
from mr_reduction.simple_utils import SampleLogs, workspace_handle
from mr_reduction.types import MantidWorkspace


@dataclass
class DirectBeamOptions:
    DB_ID: int
    P0: int
    PN: int
    x_pos: float  # peak center
    x_width: float  # peak width
    y_pos: float
    y_width: float
    bg_pos: float
    bg_width: float
    dpix: float  # sample log entry "normalization_dirpix"
    tth: float  # scattered angle two-theta
    number: int  # run number
    File: str  # normalization run in the re-processed and legacy-compatible, readable by QuickNXS

    @staticmethod
    def from_workspace(input_workspace: MantidWorkspace, direct_beam_counter=1) -> Optional["DirectBeamOptions"]:
        """Create an instance of DirectBeamOptions from a workspace.

        Parameters
        ----------
        input_workspace : MantidWorkspace
            The Mantid workspace from which to create the DirectBeamOptions instance.
        direct_beam_counter : int, optional
            The counter for the direct beam, by default 1.
        """
        sample_logs = SampleLogs(input_workspace)

        normalization_run = sample_logs["normalization_run"]
        if normalization_run == "None":
            return None

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
    def as_dat(self) -> str:
        """ "Formatted string representation of the DirectBeamOptions suitable for an *_autoreduced.dat file"""
        clean_dict = {}
        for option in self.options:
            value = getattr(self, option)
            if isinstance(value, (bool, str)):
                clean_dict[option] = "%8s" % value
            else:
                clean_dict[option] = "%8g" % value

        template = "# %s\n" % "  ".join(["{%s}" % p for p in self.options])
        return template.format(**clean_dict)


@dataclass
class ReflectedBeamOptions:
    scale: float
    P0: int
    PN: int
    x_pos: float  # peak center
    x_width: float  # peak width
    y_pos: float
    y_width: float
    bg_pos: float
    bg_width: float
    fan: bool
    dpix: float
    tth: float
    number: str
    DB_ID: int
    File: str
    """two-theta offset to be applied when saving the options to a file later to be read by QuickNXS"""
    tth_offset: float = field(repr=False, default=0.0)

    @classmethod
    def dat_header(cls) -> str:
        """Header for the direct beam options in the *_autoreduced.dat file"""
        return "# [Data Runs]\n# %s\n" % "  ".join(["%8s" % field for field in cls.__dataclass_fields__])

    @staticmethod
    def filename(input_workspace: MantidWorkspace) -> str:
        """
        Generate a filename for the given Mantid workspace.

        This method retrieves the filename from the Mantid workspace's run object.
        If the filename ends with 'nxs.h5', it modifies the filename to be compatible
        with QuickNXS by replacing 'nexus' with 'data' and changing the extension to '_histo.nxs'.
        If the workspace is live data and does not have a filename, it returns 'live data'.
        """
        sample_logs = workspace_handle(input_workspace).getRun()
        if "Filename" in sample_logs:
            filename = sample_logs["Filename"]
            if filename.endswith("nxs.h5"):
                filename = filename.replace("nexus", "data")
                filename = filename.replace(".nxs.h5", "_histo.nxs")
        else:
            filename = "live data"  # For live data, we might not have a file name
        return filename

    @staticmethod
    def two_theta_offset(input_workspace: MantidWorkspace) -> float:
        """two-theta offset for compatibility with QuickNXS.

        For some reason, the tth value that QuickNXS expects is offset.
        It seems to be because that same offset is applied later in the QuickNXS calculation.
        """
        ws = workspace_handle(input_workspace)
        sample_logs = ws.getRun()
        scatt_pos = sample_logs["specular_pixel"]
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

        return -((direct_beam_pix - scatt_pos) * pixel_width) / det_distance * 180.0 / math.pi

    @classmethod
    def from_workspace(cls, input_workspace: MantidWorkspace, direct_beam_counter=1) -> "ReflectedBeamOptions":
        """Create an instance of ReflectedBeamOptions from a workspace.

        Parameters
        ----------
        input_workspace : MantidWorkspace
            The Mantid workspace from which to create the ReflectedBeamOptions instance.
        direct_beam_counter : int, optional
            The counter for the direct beam associated to this reflected beam, by default 1.
        """
        ws = workspace_handle(input_workspace)
        sample_logs = ws.getRun()

        peak_min = sample_logs["scatt_peak_min"]
        peak_max = sample_logs["scatt_peak_max"]
        bg_min = sample_logs["scatt_bg_min"]
        bg_max = sample_logs["scatt_bg_max"]
        low_res_min = sample_logs["scatt_low_res_min"]
        low_res_max = sample_logs["scatt_low_res_max"]
        dpix = sample_logs.mean("DIRPIX")
        tth = sample_logs["two_theta"]
        filename = cls.filename(input_workspace)
        constant_q_binning = sample_logs["constant_q_binning"]
        scatt_pos = sample_logs["specular_pixel"]

        options = ReflectedBeamOptions(
            scale=1,
            P0=0,
            PN=0,
            x_pos=scatt_pos,
            x_width=peak_max - peak_min + 1,
            y_pos=(low_res_max + low_res_min) / 2.0,
            y_width=low_res_max - low_res_min + 1,
            bg_pos=(bg_min + bg_max) / 2.0,
            bg_width=bg_max - bg_min + 1,
            fan=constant_q_binning,
            dpix=dpix,
            tth=tth,
            number=str(ws.getRunNumber()),
            DB_ID=direct_beam_counter,
            File=filename,
        )

        # two-theta offset for compatibility with QuickNXS
        options.tth_offset = cls.two_theta_offset(input_workspace)

        return options

    @property
    def options(self) -> List[str]:
        """List of option names"""
        return self.__dataclass_fields__

    @property
    def as_dat(self) -> str:
        """ "Formatted string representation of the DirectBeamOptions suitable for an *_autoreduced.dat file"""
        clean_dict = {}
        for option in self.options:
            value = getattr(self, option)
            if option == "tth":
                value += self.tth_offset
            if isinstance(value, str):
                clean_dict[option] = "%8s" % value
            else:
                clean_dict[option] = "%8g" % value

        template = "# %s\n" % "  ".join(["{%s}" % p for p in self.options])
        return template.format(**clean_dict)


def write_reflectivity(ws_list, output_path, cross_section) -> None:
    r"""
    Write out reflectivity output (usually from autoreduction, as file REF_M_*_autoreduce.dat).

    This function generates and writes reflectivity data (typically as a result of an autoreduction process)
    to an output file which can be loaded by QuickNXS. The output file is usually named in the format
    `REF_M_*_autoreduce.dat`.

    Parameters
    ----------
    ws_list : list
        A list of workspace objects containing reflectivity data.
    output_path : str
        The path where the output file will be written.
    cross_section : str
        The cross-section information to be included in the output file.
    """
    # Sanity check
    if not ws_list:
        return

    fd = open(output_path, "w")

    #
    # Write header
    #
    peak_number = RunPeakNumber.peak_number_log(ws_list[0])
    runpeak_list = [str(RunPeakNumber(str(ws.getRunNumber()), peak_number)) for ws in ws_list]
    fd.write(
        f"""# Datafile created by mr_reduction {mr_reduction.__version__}
# Datafile created by Mantid {mantid.__version__}
# Autoreduced
# Date: {time.strftime("%Y-%m-%d %H:%M:%S")}
# Type: Specular
# Input file indices: {','.join(runpeak_list)}
# Extracted states: {cross_section}
#
"""
    )

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
        x = ws.readX(0)
        y = ws.readY(0)
        dy = ws.readE(0)
        dx = ws.readDx(0)
        theta = reflected_beam_options.tth * math.pi / 360.0
        quicknxs_scale = quicknxs_scaling_factor(ws)
        for i in range(len(x)):
            data_block += "%12.6g  %12.6g  %12.6g  %12.6g  %12.6g\n" % (
                x[i],
                y[i] * quicknxs_scale,
                dy[i] * quicknxs_scale,
                dx[i],
                theta,
            )

    fd.write(
        """
#
# [Global Options]
# name           value
# sample_length  10
#
"""
    )

    #
    # Write sequence information from the last workspace in the list
    #
    sample_logs = SampleLogs(ws_list[-1])  # use the last workspace for the sequence information
    sequence_id = sample_logs["sequence_id"]
    sequence_number = sample_logs["sequence_number"]
    sequence_total = sample_logs["sequence_total"]
    fd.write(
        f"""
# [Sequence]
# sequence_id {sequence_id}
# sequence_number {sequence_number}
# sequence_total {sequence_total}
"""
    )

    #
    # Write scattering data
    #
    header = "  ".join([f"{item:12s}" for item in ["Qz [1/A]", "R [a.u.]", "dR [a.u.]", "dQz [1/A]", "theta [rad]"]])
    fd.write(
        f"""
#
# [Data]
# {header}
#
{data_block}
"""
    )

    fd.close()


def quicknxs_scaling_factor(input_workspace: MantidWorkspace) -> float:
    """This function calculates a scaling factor to ensure compatibility with QuickNXS.
    It retrieves various properties from the Mantid workspace's run object and uses
    them to compute the scaling factor."""
    sample_logs = SampleLogs(input_workspace)
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
