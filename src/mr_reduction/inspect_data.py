"""
module to replace Mantid algorithm MRInspectData
"""

import copy
import math
import sys
from typing import List, Optional

import numpy as np
from mantid import simpleapi as mtd
from mantid.kernel import logger
from scipy import optimize as opt
from scipy.optimize import OptimizeWarning

from mr_reduction.simple_utils import workspace_handle
from mr_reduction.types import EventWorkspace, MantidWorkspace

DEAD_PIXELS = 10
NX_PIXELS = 304
NY_PIXELS = 256


def fit_2d_peak(workspace):
    """
    Fit a 2D Gaussian peak
    :param workspace: workspace to work with
    """
    n_x = int(workspace.getInstrument().getNumberParameter("number-of-x-pixels")[0])
    n_y = int(workspace.getInstrument().getNumberParameter("number-of-y-pixels")[0])

    # Prepare data to fit
    _integrated = mtd.Integration(InputWorkspace=workspace)
    signal = _integrated.extractY()
    z = np.reshape(signal, (n_x, n_y))
    x = np.arange(0, n_x)
    y = np.arange(0, n_y)
    _x, _y = np.meshgrid(x, y)
    _x = _x.T
    _y = _y.T

    code = coord_to_code(_x, _y).ravel()
    data_to_fit = z.ravel()
    err_y = np.sqrt(np.fabs(data_to_fit))
    err_y[err_y < 1] = 1

    # Use the highest data point as a starting point for a simple Gaussian fit
    x_dist = np.sum(z, 1)
    y_dist = np.sum(z, 0)
    center_x = np.argmax(x_dist)
    center_y = np.argmax(y_dist)

    # Gaussian fit
    p0 = [np.max(z), center_x, 5, center_y, 50, 0]
    try:
        gauss_coef, _ = opt.curve_fit(gauss_simple, code, data_to_fit, p0=p0, sigma=err_y)
    except (RuntimeError, ValueError, OptimizeWarning) as e:
        logger.notice(f"Error fitting simple Gaussian: {e}")
        gauss_coef = p0

    # Keep track of the result
    th = gauss_simple(code, *gauss_coef)
    th = np.reshape(th, (n_x, n_y))
    _chi2 = chi2(th, z)
    guess_x = gauss_coef[1]
    guess_wx = 2.0 * gauss_coef[2]
    guess_y = gauss_coef[3]
    guess_wy = 2.0 * gauss_coef[4]
    guess_chi2 = _chi2

    # Fit a polynomial background, as a starting point to fitting signal + background
    try:
        step_coef, _ = opt.curve_fit(poly_bck, code, data_to_fit, p0=[0, 0, 0, center_x, 0], sigma=err_y)
    except (RuntimeError, ValueError, OptimizeWarning) as e:
        logger.notice(f"Error fitting polynomial background: {e}")
        step_coef = [0, 0, 0, center_x, 0]
    th = poly_bck(code, *step_coef)
    th = np.reshape(th, (n_x, n_y))

    # Now fit a Gaussian + background
    # A, mu_x, sigma_x, mu_y, sigma_y, poly_a, poly_b, poly_c, center, background
    coef = [np.max(z), center_x, 5, center_y, 50, step_coef[0], step_coef[1], step_coef[2], step_coef[3], step_coef[4]]
    try:
        coef, _ = opt.curve_fit(poly_bck_signal, code, data_to_fit, p0=coef, sigma=err_y)
    except (RuntimeError, ValueError, OptimizeWarning) as e:
        logger.notice(f"Error fitting polynomial + Gaussian: {e}")
    th = poly_bck_signal(code, *coef)
    th = np.reshape(th, (n_x, n_y))
    _chi2 = chi2(th, z)
    if _chi2 < guess_chi2:
        guess_x = coef[1]
        guess_wx = 2.0 * coef[2]
        guess_y = coef[3]
        guess_wy = 2.0 * coef[4]
        guess_chi2 = _chi2

    # Package the best results
    x_min = max(0, int(guess_x - np.fabs(guess_wx)))
    x_max = min(n_x - 1, int(guess_x + np.fabs(guess_wx)))
    y_min = max(0, int(guess_y - np.fabs(guess_wy)))
    y_max = min(n_y - 1, int(guess_y + np.fabs(guess_wy)))

    return [x_min, x_max], [y_min, y_max]


def coord_to_code(x, y):
    """Utility function to encode pixel coordinates so we can unravel our distribution in a 1D array"""
    return 1000 * x + y


def code_to_coord(c):
    """Utility function to decode encoded coordinates"""
    i_x = c / 1000
    i_y = c % 1000
    return i_x, i_y


def poly_bck(value, *p):
    """
    Polynomial function for background fit

    f = a + b*(x-center) + c*(x-center)**2 + bck

    where bck is a minimum threshold that is zero when the polynomial
    has a value greater than it.
    """
    coord = code_to_coord(value)
    poly_a, poly_b, poly_c, center, background = p
    values = poly_a + poly_b * (coord[0] - center) + poly_c * (coord[0] - center) ** 2
    values[values < background] = background
    values[coord[0] < DEAD_PIXELS] = 0
    values[coord[0] >= NX_PIXELS - DEAD_PIXELS] = 0
    values[coord[1] < DEAD_PIXELS] = 0
    values[coord[1] >= NY_PIXELS - DEAD_PIXELS] = 0
    return values


def poly_bck_signal(value, *p):
    """
    Function for a polynomial + Gaussian signal

    f = a + b*(x-center) + c*(x-center)**2 + Gaussian(x) + bck

    where bck is a minimum threshold that is zero when the polynomial+Gaussian
    has a value greater than it.
    """
    coord = code_to_coord(value)
    A, mu_x, sigma_x, mu_y, sigma_y, poly_a, poly_b, poly_c, center, background = p
    if A < 0 or sigma_x > 50:
        return np.zeros(len(value))

    values = poly_a + poly_b * (coord[0] - center) + poly_c * (coord[0] - center) ** 2
    values_g = A * np.exp(-((coord[0] - mu_x) ** 2) / (2.0 * sigma_x**2) - (coord[1] - mu_y) ** 2 / (2.0 * sigma_y**2))
    values += values_g
    values[values < background] = background
    values[coord[0] < DEAD_PIXELS] = 0
    values[coord[0] >= NX_PIXELS - DEAD_PIXELS] = 0
    values[coord[1] < DEAD_PIXELS] = 0
    values[coord[1] >= NY_PIXELS - DEAD_PIXELS] = 0
    return values


def gauss_simple(value, *p):
    """
    Gaussian function with threshold background

    f = Gaussian(x) + bck

    where bck is a minimum threshold that is zero when the Gaussian
    has a value greater than it.
    """
    coord = code_to_coord(value)
    A, mu_x, sigma_x, mu_y, sigma_y, background = p
    if A < 0 or sigma_x > 50:
        return np.zeros(len(value))
    values = A * np.exp(-((coord[0] - mu_x) ** 2) / (2.0 * sigma_x**2) - (coord[1] - mu_y) ** 2 / (2.0 * sigma_y**2))
    values[values < background] = background
    values[coord[0] < DEAD_PIXELS] = 0
    values[coord[0] >= NX_PIXELS - DEAD_PIXELS] = 0
    values[coord[1] < DEAD_PIXELS] = 0
    values[coord[1] >= NY_PIXELS - DEAD_PIXELS] = 0
    return values


def chi2(data, model):
    """Returns the chi^2 for a data set and model pair"""
    err = np.fabs(data.ravel())
    err[err <= 0] = 1
    return np.sum((data.ravel() - model.ravel()) ** 2 / err) / len(data.ravel())


def _as_ints(a):
    return [int(a[0]), int(a[1])]


class DataInspector(object):
    """
    Class to hold the relevant information from a run (scattering or direct beam).

    Parameters
    ----------
    peak_number : int, optional
    The peak number to process. This determines which process-variable (PV)
    ROIs to use for peak and background calculations. Default is 1.
    """

    peak_range_offset = 0
    tolerance = 0.02

    def __init__(
        self,
        input_workspace: MantidWorkspace,
        peak_number: Optional[int] = 1,
        cross_section="",
        event_threshold=10000,
        dirpix_overwrite=None,
        dangle0_overwrite=None,
        # peak-related options
        use_roi=True,  # use process-variable ROI1* (or ROI3* if peak_number=2)
        force_peak_roi=False,
        update_peak_range=False,
        peak_roi=[0, 0],  # pixel range along horizontal (X) axis defining the reflectivity peak
        force_low_res_roi=False,
        low_res_roi=[0, 0],  # pixel range along vertical (Y) axis defining the low-resolution peak
        # background-related options
        use_roi_bck=False,  # use process-variable ROI2*
        force_bck_roi=False,
        bck_roi=[0, 0],  # pixel range along horizontal (X) axis defining the background
        use_tight_bck=False,
        bck_offset=3,
    ):
        ws = workspace_handle(input_workspace)  # a reference to the workspace instance
        self.cross_section = cross_section
        self.run_number = ws.getRunNumber()
        self.is_direct_beam = False
        self.data_type = 1
        self.peak_position = 0
        self.peak_range = [0, 0]
        self.low_res_range = [0, 0]
        self.background = [0, 0]
        self.n_events_cutoff = event_threshold
        self.dangle0_overwrite = dangle0_overwrite
        self.dirpix_overwrite = dirpix_overwrite

        # peak ROI information
        self.roi_peak = [0, 0]
        self.roi_low_res = [0, 0]
        self.roi_background = [0, 0]

        # Options to override the peak ROI
        self.force_peak_roi = force_peak_roi
        self.forced_peak_roi = _as_ints(peak_roi)
        self.force_low_res_roi = force_low_res_roi
        self.forced_low_res_roi = _as_ints(low_res_roi)
        self.force_bck_roi = force_bck_roi
        self.forced_bck_roi = _as_ints(bck_roi)

        # Peak found before fitting for the central position
        self.found_peak = [0, 0]
        self.found_low_res = [0, 0]

        # Processing options
        # Use the ROI rather than finding the ranges
        self.use_roi = use_roi
        self.use_roi_actual = False

        # Use the 2nd ROI as the background, if available
        self.use_roi_bck = use_roi_bck

        # Use background as a region on each side of the peak
        self.use_tight_bck = use_tight_bck
        # Width of the background on each side of the peak
        self.bck_offset = bck_offset

        # Update the specular peak range after finding the peak within the ROI
        self.update_peak_range = update_peak_range

        self.tof_range = self.get_tof_range(ws)
        self.calculated_scattering_angle = 0.0
        self.theta_d = 0.0
        self.determine_data_type(ws, peak_number=peak_number)

    def log(self):
        """
        Log useful diagnostics
        """
        logger.notice("| Run: %s [direct beam: %s]" % (self.run_number, self.is_direct_beam))
        logger.notice("|   Peak position: %s" % self.peak_position)
        logger.notice("|   Reflectivity peak: %s" % str(self.peak_range))
        logger.notice("|   Low-resolution pixel range: %s" % str(self.low_res_range))

    def get_tof_range(self, ws):
        """
        Determine TOF range from the data
        :param workspace ws: workspace to work with
        """
        run_object = ws.getRun()
        sample_detector_distance = run_object["SampleDetDis"].getStatistics().mean
        source_sample_distance = run_object["ModeratorSamDis"].getStatistics().mean
        # Check units
        if run_object["SampleDetDis"].units not in ["m", "meter"]:
            sample_detector_distance /= 1000.0
        if run_object["ModeratorSamDis"].units not in ["m", "meter"]:
            source_sample_distance /= 1000.0

        source_detector_distance = source_sample_distance + sample_detector_distance

        h = 6.626e-34  # m^2 kg s^-1
        m = 1.675e-27  # kg
        wl = run_object.getProperty("LambdaRequest").value[0]
        chopper_speed = run_object.getProperty("SpeedRequest1").value[0]
        wl_offset = 0
        cst = source_detector_distance / h * m
        tof_min = cst * (wl + wl_offset * 60.0 / chopper_speed - 1.4 * 60.0 / chopper_speed) * 1e-4
        tof_max = cst * (wl + wl_offset * 60.0 / chopper_speed + 1.4 * 60.0 / chopper_speed) * 1e-4

        self.tof_range = [tof_min, tof_max]
        return [tof_min, tof_max]

    def process_pv_roi(self, ws: EventWorkspace, peak_number: Optional[int] = 1):
        """
        Processes the regions of interest (ROIs) processing variables (PV) from the given event workspace
        and computes the peak and background ROI dimensions along specified axes.

        This method retrieves run-specific information from the workspace's metadata, including ROI start
        positions, sizes, and endpoints, to calculate the boundaries of peak and background
        ROIs. It initializes peak and background ROIs as empty regions and updates them based
        on the conditions evaluated from input data. The calculated ROIs are subsequently
        assigned to class attributes.

        Parameters
        ----------
        ws : EventWorkspace
            An event workspace object from which the ROI information is extracted. Provides
            access to run details and associated parameter statistics.
        peak_number: int, optional
            The peak number to be processed determines which PV to look for.
            PVs ROI1* and ROI2* are used for peak_number=1, and PVs ROI3* and ROI4* are used for
            peak_number=2, and so on. The default is 1.
        Attributes
        ----------
        roi_peak : list of int
            The calculated ROI along the X-axis for the peak. Stored as a two-element list
            [xmin, xmax] where `xmin` is the starting position and `xmax` is the end position
            of the peak ROI along the X-axis.
        roi_low_res : list of int
            The calculated ROI along the Y-axis for the peak. Stored as a two-element list
            [ymin, ymax], determining the starting and ending positions along the Y-axis.
        roi_background : list of int
            The calculated background ROI along the X-axis. Stored as a two-element list
            [xmin, xmax], where the calculated region precedes the peak ROI when
            sanity constraints are satisfied.
        """
        run = ws.getRun()

        # initialize the ROI information
        peak_roi_x = [0, 0]
        peak_roi_y = [0, 0]
        background_roi_x = [0, 0]

        peak_number = 1 if peak_number is None else peak_number  # backwards compatibility
        peak_prefix = f"ROI{2 * peak_number - 1}"  # ROI1 for peak_number=1, ROI3 for peak_number=2, etc.

        if f"{peak_prefix}StartX" in run:
            peak_roi_xmin = run[f"{peak_prefix}StartX"].getStatistics().mean
            peak_roi_ymin = run[f"{peak_prefix}StartY"].getStatistics().mean
            if f"{peak_prefix}SizeX" in run:
                size_x = run[f"{peak_prefix}SizeX"].getStatistics().mean
                size_y = run[f"{peak_prefix}SizeY"].getStatistics().mean
                peak_roi_xmax = peak_roi_xmin + size_x
                peak_roi_ymax = peak_roi_ymin + size_y
            else:
                peak_roi_xmax = run[f"{peak_prefix}EndX"].getStatistics().mean
                peak_roi_ymax = run[f"{peak_prefix}EndY"].getStatistics().mean

            if peak_roi_xmax > peak_roi_xmin and peak_roi_ymax > peak_roi_ymin:
                peak_roi_x = [int(peak_roi_xmin), int(peak_roi_xmax)]
                peak_roi_y = [int(peak_roi_ymin), int(peak_roi_ymax)]

            back_prefix = f"ROI{2 * peak_number}"  # ROI2 for peak_number=1, ROI4 for peak_number=2, etc.

            if f"{back_prefix}StartX" in run:
                background_roi_xmin = run[f"{back_prefix}StartX"].getStatistics().mean
                if f"{back_prefix}SizeX" in run:
                    size_x = run[f"{back_prefix}SizeX"].getStatistics().mean
                    background_roi_xmax = background_roi_xmin + size_x
                else:
                    background_roi_xmax = run[f"{back_prefix}EndX"].getStatistics().mean

                # case 1: Along the X-axis, the background occurs at lower values than the peak
                case1 = background_roi_xmax < peak_roi_xmin
                # case 2: Along the X-axis, the peak region is inside the background region
                case2 = background_roi_xmin < peak_roi_xmin and background_roi_xmax > peak_roi_xmax
                if case1 or case2:
                    background_roi_x = [int(background_roi_xmin), int(background_roi_xmax)]
                else:
                    logger.warning(
                        "Background region is not before the peak region "
                        "or the peak region is not inside the background region!"
                    )

        # Update the ROI attributes
        self.roi_peak = peak_roi_x
        self.roi_low_res = peak_roi_y
        self.roi_background = background_roi_x

    def check_direct_beam(self, ws, peak_position=None):
        """
        Determine whether this data is a direct beam
        :param workspace ws: Workspace to inspect
        :param float peak_position: reflectivity peak position
        """
        self.theta_d = 180.0 / math.pi * mtd.MRGetTheta(ws, SpecularPixel=peak_position, UseSANGLE=False)
        return not self.theta_d > self.tolerance

    def determine_data_type(self, ws, peak_number: Optional[int] = 1):
        """
        Inspect and determine the type of data (direct-beam or scattering)
        based on the peak locations and other characteristics.

        Parameters
        ----------
        ws : EventWorkspace
            The workspace to inspect. This contains the data and metadata needed
            to determine the data type.
        peak_number : int, optional
            The peak number to process. This determines which process-variable (PV)
            ROIs to use for peak and background calculations. Default is 1.
        """
        # Skip empty data entries
        if ws.getNumberEvents() < self.n_events_cutoff:
            self.data_type = -1
            logger.notice("No data for %s %s" % (self.run_number, self.cross_section))
            return

        # Find reflectivity peak and low resolution ranges
        peak, low_res = fit_2d_peak(ws)
        if self.use_tight_bck:
            bck_range = [int(max(0.0, peak[0] - self.bck_offset)), int(min(NX_PIXELS, peak[1] + self.bck_offset))]
        else:
            bck_range = [int(max(0.0, peak[0] - 2 * self.bck_offset)), int(max(0.0, peak[0] - self.bck_offset))]
        self.found_peak = copy.copy(peak)
        self.found_low_res = copy.copy(low_res)
        logger.notice("Run %s [%s]: Peak found %s" % (self.run_number, self.cross_section, peak))
        logger.notice("Run %s [%s]: Low-res found %s" % (self.run_number, self.cross_section, str(low_res)))

        # Inspect the ROI* process variables to initialize the peak and background ranges
        self.process_pv_roi(ws, peak_number=peak_number)
        # Is User overriding any of the ROI regions?
        if self.force_peak_roi:
            logger.notice("Forcing peak ROI: %s" % self.forced_peak_roi)
            self.roi_peak = self.forced_peak_roi
        if self.force_low_res_roi:
            logger.notice("Forcing low-res ROI: %s" % self.forced_low_res_roi)
            self.roi_low_res = self.forced_low_res_roi
        if self.force_bck_roi:
            logger.notice("Forcing background ROI: %s" % self.forced_bck_roi)
            self.roi_background = self.forced_bck_roi

        # Keep track of whether we actually used the ROI
        self.use_roi_actual = False

        if self.use_roi and (self.roi_peak != [0, 0]):
            if self.update_peak_range is False:
                logger.notice("Using ROI peak range: [%s %s]" % (self.roi_peak[0], self.roi_peak[1]))
                self.use_roi_actual = True
                peak = copy.copy(self.roi_peak)
                if not self.roi_low_res == [0, 0]:
                    low_res = copy.copy(self.roi_low_res)
                if not self.roi_background == [0, 0]:
                    bck_range = copy.copy(self.roi_background)
            else:
                logger.notice("Using fit peak range: [%s %s]" % (peak[0], peak[1]))
                if not self.roi_low_res == [0, 0]:
                    low_res = copy.copy(self.roi_low_res)
                if not self.roi_background == [0, 0]:
                    bck_range = copy.copy(self.roi_background)

        # Store the information we found
        self.peak_position = (peak[1] + peak[0]) / 2.0
        self.peak_range = [int(max(0, peak[0])), int(min(peak[1], NX_PIXELS))]
        self.low_res_range = [int(max(0, low_res[0])), int(min(low_res[1], NY_PIXELS))]
        self.background = [int(max(0, bck_range[0])), int(min(bck_range[1], NY_PIXELS))]

        # Computed scattering angle
        self.calculated_scattering_angle = mtd.MRGetTheta(
            ws,
            SpecularPixel=self.peak_position,
            DirectPixelOverwrite=self.dirpix_overwrite,
            DAngle0Overwrite=self.dangle0_overwrite,
        )
        self.calculated_scattering_angle *= 180.0 / math.pi

        # Determine whether we have a direct beam
        self.is_direct_beam = self.check_direct_beam(ws, self.peak_position)

        # Convenient data type
        self.data_type = 0 if self.is_direct_beam else 1

        # Write to logs
        self.log()


def inspect_data(
    Workspace: str,
    peak_number: Optional[int] = 1,
    UseROI: bool = True,
    UpdatePeakRange: bool = False,
    UseROIBck: bool = False,
    UseTightBck: bool = False,
    BckWidth: int = 10,
    ForcePeakROI: bool = False,
    PeakROI: List[int] = [0, 0],
    ForceLowResPeakROI: bool = False,
    LowResPeakROI: List[int] = [0, 0],
    ForceBckROI: bool = False,
    BckROI: List[int] = [0, 0],
    EventThreshold: int = 10000,
    DirectPixelOverwrite: Optional[float] = None,
    DAngle0Overwrite: Optional[float] = None,
) -> None:
    """
    Inspect data with the given parameters.

    Parameters
    ----------
    Workspace : str
        Input workspace.
    peak_number : int, optional
        The peak number to process. This determines which process-variable (PV)
        ROIs to use for peak and background calculations. Default is 1.
    UseROI : bool, optional
        If True, use the meta-data ROI rather than finding the ranges. Default is True.
    UpdatePeakRange : bool, optional
        If True, a fit will be performed, and the peak ranges will be updated. Default is False.
    UseROIBck : bool, optional
        If True, use the 2nd ROI in the meta-data for the background. Default is False.
    UseTightBck : bool, optional
        If True, use the area on each side of the peak to compute the background. Default is False.
    BckWidth : int, optional
        Width of the background on each side of the peak if UseTightBck is True. Default is 10.
    ForcePeakROI : bool, optional
        If True, use the PeakROI property as the ROI. Default is False.
    PeakROI : List[int], optional
        Pixel range defining the reflectivity peak. Default is [0, 0].
    ForceLowResPeakROI : bool, optional
        If True, use the LowResPeakROI property as the ROI. Default is False.
    LowResPeakROI : List[int], optional
        Pixel range defining the low-resolution peak. Default is [0, 0].
    ForceBckROI : bool, optional
        If True, use the BckROI property as the ROI. Default is False.
    BckROI : List[int], optional
        Pixel range defining the background. Default is [0, 0].
    EventThreshold : int, optional
        Minimum number of events needed to call a data set a valid direct beam. Default is 10000.
    DirectPixelOverwrite : Optional[float], optional
        DIRPIX overwrite value. Default is None.
    DAngle0Overwrite : Optional[float], optional
        DANGLE0 overwrite value (degrees). Default is None.

    Returns
    -------
    None
    """
    nxs_data = Workspace
    nxs_data_name = str(Workspace)
    data_info = DataInspector(
        nxs_data,
        peak_number=peak_number,
        cross_section=nxs_data_name,
        use_roi=UseROI,
        update_peak_range=UpdatePeakRange,
        use_roi_bck=UseROIBck,
        use_tight_bck=UseTightBck,
        bck_offset=BckWidth,
        force_peak_roi=ForcePeakROI,
        peak_roi=PeakROI,
        force_low_res_roi=ForceLowResPeakROI,
        low_res_roi=LowResPeakROI,
        force_bck_roi=ForceBckROI,
        bck_roi=BckROI,
        event_threshold=EventThreshold,
        dirpix_overwrite=DirectPixelOverwrite,
        dangle0_overwrite=DAngle0Overwrite,
    )
    # Store information in logs
    mtd.AddSampleLog(
        Workspace=nxs_data,
        LogName="calculated_scatt_angle",
        LogText=str(data_info.calculated_scattering_angle),
        LogType="Number",
        LogUnit="degree",
    )
    mtd.AddSampleLog(Workspace=nxs_data, LogName="cross_section", LogText=nxs_data_name)
    mtd.AddSampleLog(Workspace=nxs_data, LogName="use_roi_actual", LogText=str(data_info.use_roi_actual))
    mtd.AddSampleLog(Workspace=nxs_data, LogName="is_direct_beam", LogText=str(data_info.is_direct_beam))
    mtd.AddSampleLog(
        Workspace=nxs_data,
        LogName="tof_range_min",
        LogText=str(data_info.tof_range[0]),
        LogType="Number",
        LogUnit="usec",
    )
    mtd.AddSampleLog(
        Workspace=nxs_data,
        LogName="tof_range_max",
        LogText=str(data_info.tof_range[1]),
        LogType="Number",
        LogUnit="usec",
    )
    mtd.AddSampleLog(
        Workspace=nxs_data, LogName="peak_min", LogText=str(data_info.peak_range[0]), LogType="Number", LogUnit="pixel"
    )
    mtd.AddSampleLog(
        Workspace=nxs_data, LogName="peak_max", LogText=str(data_info.peak_range[1]), LogType="Number", LogUnit="pixel"
    )
    mtd.AddSampleLog(
        Workspace=nxs_data,
        LogName="background_min",
        LogText=str(data_info.background[0]),
        LogType="Number",
        LogUnit="pixel",
    )
    mtd.AddSampleLog(
        Workspace=nxs_data,
        LogName="background_max",
        LogText=str(data_info.background[1]),
        LogType="Number",
        LogUnit="pixel",
    )
    mtd.AddSampleLog(
        Workspace=nxs_data,
        LogName="low_res_min",
        LogText=str(data_info.low_res_range[0]),
        LogType="Number",
        LogUnit="pixel",
    )
    mtd.AddSampleLog(
        Workspace=nxs_data,
        LogName="low_res_max",
        LogText=str(data_info.low_res_range[1]),
        LogType="Number",
        LogUnit="pixel",
    )
    # Add process ROI information
    mtd.AddSampleLog(
        Workspace=nxs_data,
        LogName="roi_peak_min",
        LogText=str(data_info.roi_peak[0]),
        LogType="Number",
        LogUnit="pixel",
    )
    mtd.AddSampleLog(
        Workspace=nxs_data,
        LogName="roi_peak_max",
        LogText=str(data_info.roi_peak[1]),
        LogType="Number",
        LogUnit="pixel",
    )

    mtd.AddSampleLog(
        Workspace=nxs_data,
        LogName="roi_low_res_min",
        LogText=str(data_info.roi_low_res[0]),
        LogType="Number",
        LogUnit="pixel",
    )
    mtd.AddSampleLog(
        Workspace=nxs_data,
        LogName="roi_low_res_max",
        LogText=str(data_info.roi_low_res[1]),
        LogType="Number",
        LogUnit="pixel",
    )

    mtd.AddSampleLog(
        Workspace=nxs_data,
        LogName="roi_background_min",
        LogText=str(data_info.roi_background[0]),
        LogType="Number",
        LogUnit="pixel",
    )
    mtd.AddSampleLog(
        Workspace=nxs_data,
        LogName="roi_background_max",
        LogText=str(data_info.roi_background[1]),
        LogType="Number",
        LogUnit="pixel",
    )
