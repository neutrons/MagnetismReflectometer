#pylint: disable=dangerous-default-value, too-many-instance-attributes, too-many-arguments, too-many-locals, too-few-public-methods
"""
    Meta-data information for MR reduction
"""
from __future__ import (absolute_import, division, print_function)
import numpy as np
import scipy.optimize as opt

import mantid.simpleapi as api


class DataInfo(object):
    """
        Class to provide a convenient interface to the meta-data extracted
        by MRInspectData.
    """
    # Number of events under which we can't consider a direct beam file
    n_events_cutoff = 2000

    def __init__(self, ws, cross_section, use_roi=True, update_peak_range=False, use_roi_bck=False,
                 use_tight_bck=False, bck_offset=3, huber_x_cut=4.95,
                 force_peak_roi=False, peak_roi=[0,0], force_bck_roi=False, bck_roi=[0,0]):

        api.MRInspectData(Workspace=ws, UseROI=use_roi, UpdatePeakRange=update_peak_range,
                          UseROIBck=use_roi_bck, UseTightBck=use_tight_bck,
                          BckWidth=bck_offset, HuberXCut=100,
                          ForcePeakROI=force_peak_roi, PeakROI=peak_roi,
                          #ForceLowResPeakROI=False, LowResPeakROI=[0, 0],
                          ForceBckROI=force_bck_roi, BckROI=bck_roi)

        self.cross_section = cross_section
        self.run_number = ws.getRunNumber()
        self.workspace_name = str(ws)

        run_object = ws.getRun()
        self.is_direct_beam = run_object.getProperty("is_direct_beam").value.lower()=='true'
        # We now use SampleX instead of HuberX
        sample_x = run_object.getProperty("SampleX").value[0]
        self.is_direct_beam = self.is_direct_beam or sample_x > huber_x_cut

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

        peak_min = run_object.getProperty("peak_min").value
        peak_max = run_object.getProperty("peak_max").value
        self.peak_range = [peak_min, peak_max]
        self.peak_position = (peak_min+peak_max)/2.0

        background_min = max(1, run_object.getProperty("background_min").value)
        background_max = max(background_min,
                             run_object.getProperty("background_max").value)
        self.background = [background_min, background_max]

        low_res_min = run_object.getProperty("low_res_min").value
        low_res_max = run_object.getProperty("low_res_max").value
        self.low_res_range = [low_res_min, low_res_max]

        # Region of interest information
        roi_peak_min = run_object.getProperty("roi_peak_min").value
        roi_peak_max = run_object.getProperty("roi_peak_max").value
        self.roi_peak = [roi_peak_min, roi_peak_max]

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

        if np.fabs(peak_max-peak_min)>100:
            self.peak_range, self.low_res_range, self.background = self.fit_2d_peak(ws, self.roi_peak, self.roi_low_res)
            self.peak_position = (self.peak_range[0]+self.peak_range[1])/2.0

    def fit_2d_peak(self, workspace, peak=[150, 150], low_res=[100, 250]):
        n_x = int(workspace.getInstrument().getNumberParameter("number-of-x-pixels")[0])
        n_y = int(workspace.getInstrument().getNumberParameter("number-of-y-pixels")[0])

        signal = workspace.extractY()
        z=np.reshape(signal, (n_x, n_y))
        x = np.arange(0, n_x)
        y = np.arange(0, n_y)
        _x, _y = np.meshgrid(x, y)
        _x = _x.T
        _y = _y.T

        code = coord_to_code(_x, _y).ravel()
        data_to_fit = z.ravel()
        # Find a rough estimate for the background first
        step_coef, _ = opt.curve_fit(step, code, data_to_fit, p0=[10,140,0])

        x_center = np.fabs(peak[1]+peak[0])/2.0
        x_sigma = 10 #np.fabs(peak[1]-peak[0])
        y_center = np.fabs(low_res[1]+low_res[0])/2.0
        y_sigma = np.fabs(low_res[1]-low_res[0])
        #p0 = [np.max(z), step_coef[1], 10, step_coef[1], 50, step_coef[0], step_coef[1], step_coef[2]]
        p0 = [np.max(z), x_center, x_sigma, y_center, y_sigma, step_coef[0], step_coef[1], step_coef[2]]
        coef, _ = opt.curve_fit(gauss, code, data_to_fit, p0=p0)

        x_min = int(coef[1]-np.fabs(coef[2]))
        x_max = int(coef[1]+np.fabs(coef[2]))
        y_min = int(coef[3]-np.fabs(coef[4]))
        y_max = int(coef[3]+np.fabs(coef[4]))
        bck_min = int(max(0.0, x_min-10.0))
        bck_max = int(min(n_x, x_max+10.0))
        #bck_min = int(min(n_x, x_max+2.0))
        #bck_max = int(min(n_x, x_max+10.0))
        return [x_min, x_max], [y_min, y_max], [bck_min, bck_max]

def coord_to_code(x, y):
    return 1000*x + y
def code_to_coord(c):
    i_x = c/1000
    i_y = c%1000
    return i_x, i_y

def step(value, *p):
    coord = code_to_coord(value)
    low_bck, cutoff, high_bck = p
    
    values = np.zeros(len(value))
    values[coord[0]<cutoff] = low_bck
    values[coord[0]>=cutoff] = high_bck
    return values

def gauss(value, *p):
    coord = code_to_coord(value)
    A, mu_x, sigma_x, mu_y, sigma_y, low_bck, cutoff, high_bck = p
    
    values = np.zeros(len(value))
    values[coord[0]<cutoff] = low_bck
    values[coord[0]>=cutoff] = high_bck
    values_g = A*np.exp(-(coord[0]-mu_x)**2/(2.*sigma_x**2)-(coord[1]-mu_y)**2/(2.*sigma_y**2))
    return values+values_g
