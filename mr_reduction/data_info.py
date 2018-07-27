#pylint: disable=dangerous-default-value, too-many-instance-attributes, too-many-arguments, too-many-locals, too-few-public-methods
"""
    Meta-data information for MR reduction
"""
from __future__ import (absolute_import, division, print_function)
import numpy as np
import scipy.optimize as opt
import mantid.simpleapi as api

# Number of pixels to exclude on the edges of the detector
DEAD_PIXELS = 10


class DataInfo(object):
    """
        Class to provide a convenient interface to the meta-data extracted
        by MRInspectData.
    """
    # Number of events under which we can't consider a direct beam file
    n_events_cutoff = 2000

    def __init__(self, ws, cross_section, use_roi=True, update_peak_range=False, use_roi_bck=False,
                 use_tight_bck=False, bck_offset=3,
                 force_peak_roi=False, peak_roi=[0,0], force_bck_roi=False, bck_roi=[0,0]):

        api.MRInspectData(Workspace=ws, UseROI=use_roi, UpdatePeakRange=update_peak_range,
                          UseROIBck=use_roi_bck, UseTightBck=use_tight_bck,
                          BckWidth=bck_offset,
                          ForcePeakROI=force_peak_roi, PeakROI=peak_roi,
                          #ForceLowResPeakROI=False, LowResPeakROI=[0, 0],
                          ForceBckROI=force_bck_roi, BckROI=bck_roi)

        self.cross_section = cross_section
        self.run_number = ws.getRunNumber()
        self.workspace_name = str(ws)

        run_object = ws.getRun()
        self.is_direct_beam = run_object.getProperty("is_direct_beam").value.lower()=='true'

        self.data_type = 0 if self.is_direct_beam else 1
        if ws.getNumberEvents() < self.n_events_cutoff:
            self.data_type = -1

        # Processing options
        # Use the ROI rather than finding the ranges
        self.use_roi = use_roi
        self.use_roi_actual = run_object.getProperty("use_roi_actual").value.lower()=='true'

        self.calculated_scattering_angle = run_object.getProperty("calculated_scatt_angle").value

        tof_min = run_object.getProperty("tof_range_min").value
        tof_max = run_object.getProperty("tof_range_max").value
        self.tof_range = [tof_min, tof_max]

        # Region of interest information
        roi_peak_min = run_object.getProperty("roi_peak_min").value
        roi_peak_max = run_object.getProperty("roi_peak_max").value
        self.roi_peak = [roi_peak_min, roi_peak_max]

        peak_min = run_object.getProperty("peak_min").value
        peak_max = run_object.getProperty("peak_max").value
        if self.use_roi and not update_peak_range:
            peak_min = roi_peak_min
            peak_max = roi_peak_max
        self.peak_range = [peak_min, peak_max]
        self.peak_position = (peak_min+peak_max)/2.0

        #background_min = max(1, run_object.getProperty("background_min").value)
        #background_max = max(background_min,
        #                     run_object.getProperty("background_max").value)
        #self.background = [background_min, background_max]
        bck_max = min(20, self.peak_position)
        self.background = [max(0, bck_max-10), bck_max]

        low_res_min = run_object.getProperty("low_res_min").value
        low_res_max = run_object.getProperty("low_res_max").value
        self.low_res_range = [low_res_min, low_res_max]

        roi_low_res_min = run_object.getProperty("roi_low_res_min").value
        roi_low_res_max = run_object.getProperty("roi_low_res_max").value
        self.roi_low_res = [roi_low_res_min, roi_low_res_max]

        roi_background_min = run_object.getProperty("roi_background_min").value
        roi_background_max = run_object.getProperty("roi_background_max").value
        self.roi_background = [roi_background_min, roi_background_max]

        # Get sequence info if available
        try:
            self.sequence_id = run_object.getProperty("sequence_id").value[0]
            self.sequence_number = run_object.getProperty("sequence_number").value[0]
            self.sequence_total = run_object.getProperty("sequence_total").value[0]
        except:
            self.sequence_id = 'N/A'
            self.sequence_number = 'N/A'
            self.sequence_total = 'N/A'

        if False and not self.use_roi_actual:
            try:
                self.peak_range, self.low_res_range, self.background = fit_2d_peak(ws)
                self.peak_position = (self.peak_range[0]+self.peak_range[1])/2.0
            except:
                api.logger.error("Could not find peak")


def fit_2d_peak(workspace):
    n_x = int(workspace.getInstrument().getNumberParameter("number-of-x-pixels")[0])
    n_y = int(workspace.getInstrument().getNumberParameter("number-of-y-pixels")[0])

    # Prepare data to fit
    _integrated = api.Integration(InputWorkspace=workspace)
    signal = _integrated.extractY()
    z=np.reshape(signal, (n_x, n_y))
    x = np.arange(0, n_x)
    y = np.arange(0, n_y)
    _x, _y = np.meshgrid(x, y)
    _x = _x.T
    _y = _y.T

    code = coord_to_code(_x, _y).ravel()
    data_to_fit = z.ravel()
    err_y = np.sqrt(np.fabs(data_to_fit))
    err_y[err_y<1] = 1

    # Use the highest data point as a starting point for a simple Gaussian fit
    x_dist = np.sum(z, 1)
    y_dist = np.sum(z, 0)
    center_x = np.argmax(x_dist)
    center_y = np.argmax(y_dist)

    # Gaussian fit
    p0 = [np.max(z), center_x, 5, center_y, 50, 0]
    gauss_coef, _ = opt.curve_fit(gauss_simple, code, data_to_fit, p0=p0, sigma=err_y)

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
    step_coef, _ = opt.curve_fit(poly_bck, code, data_to_fit, p0=[0, 0, 0, center_x, 0], sigma=err_y)
    th = poly_bck(code, *step_coef)
    th = np.reshape(th, (n_x, n_y))

    # Now fit a Gaussian + background
    # A, mu_x, sigma_x, mu_y, sigma_y, poly_a, poly_b, poly_c, center, background
    coef = [np.max(z), center_x, 5, center_y, 50,
            step_coef[0], step_coef[1], step_coef[2], step_coef[3], step_coef[4]]
    coef, _ = opt.curve_fit(poly_bck_signal, code, data_to_fit, p0=coef, sigma=err_y)
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
    x_min = max(0, int(guess_x-np.fabs(guess_wx)))
    x_max = min(n_x-1, int(guess_x+np.fabs(guess_wx)))
    y_min = max(0, int(guess_y-np.fabs(guess_wy)))
    y_max = min(n_y-1, int(guess_y+np.fabs(guess_wy)))
    bck_min = int(max(0.0, x_min-10.0))
    bck_max = int(min(n_x, x_max+10.0))

    return [x_min, x_max], [y_min, y_max], [bck_min, bck_max]

def coord_to_code(x, y):
    return 1000*x + y

def code_to_coord(c):
    i_x = c/1000
    i_y = c%1000
    return i_x, i_y

def poly_bck(value, *p):
    coord = code_to_coord(value)
    poly_a, poly_b, poly_c, center, background = p
    values = poly_a + poly_b*(coord[0]-center) + poly_c*(coord[0]-center)**2
    values[values<background] = background
    values[coord[0]<DEAD_PIXELS] = 0
    values[coord[0]>304-DEAD_PIXELS] = 0
    values[coord[1]<DEAD_PIXELS] = 0
    values[coord[1]>256-DEAD_PIXELS] = 0
    return values

def poly_bck_signal(value, *p):
    coord = code_to_coord(value)
    A, mu_x, sigma_x, mu_y, sigma_y, poly_a, poly_b, poly_c, center, background = p
    if A<0 or sigma_x>50:
        return np.zeros(len(value))

    values = poly_a + poly_b*(coord[0]-center) + poly_c*(coord[0]-center)**2
    values_g = A*np.exp(-(coord[0]-mu_x)**2/(2.*sigma_x**2)-(coord[1]-mu_y)**2/(2.*sigma_y**2))
    values += values_g
    values[values<background] = background
    values[coord[0]<DEAD_PIXELS] = 0
    values[coord[0]>304-DEAD_PIXELS] = 0
    values[coord[1]<DEAD_PIXELS] = 0
    values[coord[1]>256-DEAD_PIXELS] = 0
    return values

def gauss_simple(value, *p):
    coord = code_to_coord(value)
    A, mu_x, sigma_x, mu_y, sigma_y, background = p
    if A<0 or sigma_x>50:
        return np.zeros(len(value))
    values =  A*np.exp(-(coord[0]-mu_x)**2/(2.*sigma_x**2)-(coord[1]-mu_y)**2/(2.*sigma_y**2))
    values[values<background] = background
    values[coord[0]<DEAD_PIXELS] = 0
    values[coord[0]>304-DEAD_PIXELS] = 0
    values[coord[1]<DEAD_PIXELS] = 0
    values[coord[1]>256-DEAD_PIXELS] = 0
    return values

def chi2(data, model):
    err = np.fabs(data.ravel())
    err[err<=0] = 1
    return np.sum((data.ravel()-model.ravel())**2/err)/len(data.ravel())
