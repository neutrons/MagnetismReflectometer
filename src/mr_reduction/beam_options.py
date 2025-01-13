# standard imports
import math
from dataclasses import dataclass, field
from typing import List, Optional

# mr_reduction imports
from mr_reduction.simple_utils import SampleLogs, workspace_handle
from mr_reduction.types import MantidWorkspace


@dataclass
class DirectBeamOptions:
    """
    Dataclass storing information about the direct beam run, later to be saved to file.
    """

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
    def option_names() -> List[str]:
        """List of option names in the order expected for a QuickNXS output file"""
        return [
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

    @classmethod
    def dat_header(cls) -> str:
        """Header for the direct beam options in the *_autoreduced.dat file"""
        return "# [Direct Beam Runs]\n# %s\n" % "  ".join(["%8s" % name for name in cls.option_names()])

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

    @property
    def as_dat(self) -> str:
        """ "Formatted string representation of the DirectBeamOptions suitable for an *_autoreduced.dat file"""
        clean_dict = {}
        for name in self.option_names():
            value = getattr(self, name)
            if isinstance(value, (bool, str)):
                clean_dict[name] = "%8s" % value
            else:
                clean_dict[name] = "%8g" % value

        template = "# %s\n" % "  ".join(["{%s}" % p for p in self.option_names()])
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
    """two-theta offset to be applied when saving the options to a file to be read later by QuickNXS"""
    tth_offset: float = field(repr=False, default=0.0)

    @staticmethod
    def option_names() -> List[str]:
        """List of option names, excluding the two-theta offset, in the order expected for a QuickNXS output file"""
        return [
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

    @classmethod
    def dat_header(cls) -> str:
        """Header for the direct beam options in the *_autoreduced.dat file"""
        return "# [Data Runs]\n# %s\n" % "  ".join(["%8s" % name for name in cls.option_names()])

    @staticmethod
    def filename(input_workspace: MantidWorkspace) -> str:
        """
        Generate a filename for the given Mantid workspace.

        This method retrieves the filename from the Mantid workspace's run object.
        If the filename ends with 'nxs.h5', it modifies the filename to be compatible
        with QuickNXS by replacing 'nexus' with 'data' and changing the extension to '_histo.nxs'.
        If the workspace is live data and does not have a filename, it returns 'live data'.
        """
        sample_logs = SampleLogs(input_workspace)
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
        sample_logs = SampleLogs(input_workspace)
        scatt_pos = sample_logs["specular_pixel"]  # position in pixel units
        det_distance = sample_logs.mean("SampleDetDis")
        # Check units
        if sample_logs.property("SampleDetDis").units not in ["m", "meter"]:
            det_distance /= 1000.0
        direct_beam_pix = sample_logs.mean("DIRPIX")  # height (pixel units) where  direct beam impings on detector
        # Get pixel size from instrument properties
        if ws.getInstrument().hasParameter("pixel-width"):
            pixel_width = float(ws.getInstrument().getNumberParameter("pixel-width")[0]) / 1000.0  # from mm to m
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
        sample_logs = SampleLogs(input_workspace)

        peak_min = sample_logs["scatt_peak_min"]
        peak_max = sample_logs["scatt_peak_max"]
        bg_min = sample_logs["scatt_bg_min"]
        bg_max = sample_logs["scatt_bg_max"]
        low_res_min = sample_logs["scatt_low_res_min"]
        low_res_max = sample_logs["scatt_low_res_max"]
        filename = cls.filename(input_workspace)
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
            fan=sample_logs["constant_q_binning"],
            dpix=sample_logs.mean("DIRPIX"),  # height (pixel units) where the direct beam impings on the detector
            tth=sample_logs["two_theta"],
            number=sample_logs["run_number"],
            DB_ID=direct_beam_counter,
            File=filename,
        )

        # two-theta offset for compatibility with QuickNXS
        options.tth_offset = cls.two_theta_offset(input_workspace)

        return options

    @property
    def as_dat(self) -> str:
        """Formatted string representation of the ReflectedBeamOptions suitable for an *_autoreduced.dat file"""
        clean_dict = {}
        for name in self.option_names():
            value = getattr(self, name)
            if name == "tth":
                value += self.tth_offset
            if isinstance(value, str):
                clean_dict[name] = "%8s" % value
            else:
                clean_dict[name] = "%8g" % value

        template = "# %s\n" % "  ".join(["{%s}" % p for p in self.option_names()])
        return template.format(**clean_dict)
