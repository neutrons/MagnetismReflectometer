#pylint: disable=dangerous-default-value
"""
    Meta-data information for MR reduction
"""
from __future__ import (absolute_import, division, print_function)
import sys
sys.path.insert(0,'/opt/mantidnightly/bin')
import mantid
from mantid.simpleapi import *


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

        MRInspectData(Workspace=ws, UseROI=use_roi, UpdatePeakRange=update_peak_range,
                      UseROIBck=use_roi_bck, UseTightBck=use_tight_bck,
                      BckWidth=bck_offset, HuberXCut=huber_x_cut,
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
        
        peak_min = run_object.getProperty("peak_min").value
        peak_max = run_object.getProperty("peak_max").value
        self.peak_range = [peak_min, peak_max]
        self.peak_position = (peak_min+peak_max)/2.0

        background_min = run_object.getProperty("background_min").value
        background_max = run_object.getProperty("background_max").value
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
