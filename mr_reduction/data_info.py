#pylint: disable=dangerous-default-value, too-many-instance-attributes, bare-except, too-many-arguments, attribute-defined-outside-init, too-many-locals, too-few-public-methods
"""
    Meta-data information for MR reduction
"""
from __future__ import (absolute_import, division, print_function)
import numpy as np
import scipy.optimize as opt
import mantid.simpleapi as api

from scipy import ndimage
import scipy.signal
from .peak_finding import find_peaks, peak_prominences, peak_widths
import warnings
from scipy.optimize import OptimizeWarning

warnings.simplefilter("ignore", OptimizeWarning)

def get_cross_section_label(ws, cross_section):
    """
        Return the proper cross-section label.
    """
    cross_section = str(cross_section)
    pol_is_on = cross_section.lower().startswith('on')
    ana_is_on = cross_section.lower().endswith('on')

    pol_label = ''
    ana_label = ''

    # Look for log that define whether OFF or ON is +
    if 'PolarizerLabel' in ws.getRun():
        pol_id = ws.getRun().getProperty("PolarizerLabel").value
        if isinstance(pol_id, np.ndarray):
            pol_id = int(pol_id[0])
        if pol_id == 1:
            pol_label = '+' if pol_is_on else '-'
        elif pol_id == 0:
            pol_label = '-' if pol_is_on else '+'

    if 'AnalyzerLabel' in ws.getRun():
        ana_id = ws.getRun().getProperty("AnalyzerLabel").value
        if isinstance(ana_id, np.ndarray):
            ana_id = int(ana_id[0])
        if ana_id == 1:
            ana_label = '+' if ana_is_on else '-'
        elif ana_id == 0:
            ana_label = '-' if ana_is_on else '-'

    cross_section = cross_section.replace('_', '-')
    if ana_label == '' and pol_label == '':
        return cross_section
    else:
        return '%s%s' % (pol_label, ana_label)


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
                          ForceBckROI=force_bck_roi, BckROI=bck_roi)

        self.cross_section = cross_section
        self.run_number = ws.getRunNumber()
        self.workspace_name = str(ws)

        run_object = ws.getRun()
        try:
            self.is_direct_beam = run_object.getProperty("data_type").value[0] == 1
            self.data_type = 0 if self.is_direct_beam else 1
        except:
            self.is_direct_beam = False
            self.data_type = 1

        if ws.getNumberEvents() < self.n_events_cutoff:
            self.data_type = -1

        # Determine proper cross-section label
        self.cross_section_label = get_cross_section_label(ws, cross_section)

        # Processing options
        # Use the ROI rather than finding the ranges
        self.use_roi = use_roi
        self.use_roi_actual = self.use_roi and not update_peak_range

        self.calculated_scattering_angle = run_object.getProperty("calculated_scatt_angle").value

        tof_min = run_object.getProperty("tof_range_min").value
        tof_max = run_object.getProperty("tof_range_max").value
        self.tof_range = [tof_min, tof_max]

        # Region of interest information
        roi_peak_min = run_object.getProperty("roi_peak_min").value
        roi_peak_max = run_object.getProperty("roi_peak_max").value
        self.roi_peak = [roi_peak_min, roi_peak_max]

        improved_peaks = True
        if improved_peaks:
            fitter = Fitter2(ws)
            #fitter = Fitter(ws, True)
            [peak_min, peak_max], [low_res_min, low_res_max] = fitter.fit_2d_peak()
            #[low_res_min, low_res_max] = fitter.fit_beam_width()
            api.logger.notice("New peak: %s %s" % (peak_min, peak_max))
            if np.abs(peak_max-peak_min)<=1:
                    peak_min = peak_min-2
                    peak_max = peak_max+2
            if np.abs(low_res_min-low_res_max)<=50:
                low_res_min = run_object.getProperty("low_res_min").value
                low_res_max = run_object.getProperty("low_res_max").value
                low_res_min = max(fitter.DEAD_PIXELS, low_res_min)
                low_res_max = min(fitter.n_y-fitter.DEAD_PIXELS, low_res_max)
        else:
            peak_min = run_object.getProperty("peak_min").value
            peak_max = run_object.getProperty("peak_max").value
            low_res_min = run_object.getProperty("low_res_min").value
            low_res_max = run_object.getProperty("low_res_max").value
            self.use_roi_actual = run_object.getProperty("use_roi_actual").value.lower()=='true'

        if self.use_roi and not update_peak_range:
            if force_peak_roi:
                peak_min = peak_roi[0]
                peak_max = peak_roi[1]
            else:
                peak_min = roi_peak_min
                peak_max = roi_peak_max
        self.peak_range = [peak_min, peak_max]
        self.peak_position = (peak_min+peak_max)/2.0

        self.low_res_range = [low_res_min, low_res_max]

        background_min = max(1, run_object.getProperty("background_min").value)
        background_max = max(background_min,
                             run_object.getProperty("background_max").value)
        self.background = [background_min, background_max]
        if use_tight_bck:
            bck_min = max(0, peak_min-bck_offset)
            bck_max = min(303, peak_max+bck_offset)
            self.background = [bck_min, bck_max]

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


def coord_to_code(x, y):
    """ Utility function to encode pixel coordinates so we can unravel our distribution in a 1D array """
    return 1000 * x + y


def code_to_coord(c):
    """ Utility function to decode encoded coordinates """
    i_x = c / 1000
    i_y = c % 1000
    return i_x, i_y


def chi2(data, model):
    """ Returns the chi^2 for a data set and model pair """
    err = np.fabs(data.ravel())
    err[err<=0] = 1
    return np.sum((data.ravel() - model.ravel())**2 / err) / len(data.ravel())


class Fitter(object):
    """
        Peak finder for MR data
    """
    DEAD_PIXELS = 10
    DEFAULT_PEAK_WIDTH = 3

    def __init__(self, workspace, prepare_plot_data=False):
        self.workspace = workspace
        self.prepare_plot_data = prepare_plot_data
        self._prepare_data()
        api.logger.notice("Numpy version: %s" % np.__version__)

    def _prepare_data(self):
        """
            Read in the data and create arrays for fitting
        """
        # Prepare data to fit
        self.n_x = int(self.workspace.getInstrument().getNumberParameter("number-of-x-pixels")[0])
        self.n_y = int(self.workspace.getInstrument().getNumberParameter("number-of-y-pixels")[0])
        self.dirpix = self.workspace.getRun()['DIRPIX'].value[0]

        _integrated = api.Integration(InputWorkspace=self.workspace)
        signal = _integrated.extractY()
        self.z=np.reshape(signal, (self.n_x, self.n_y))
        self.x = np.arange(0, self.n_x)
        self.y = np.arange(0, self.n_y)
        _x, _y = np.meshgrid(self.x, self.y)
        _x = _x.T
        _y = _y.T

        # 2D data x vs y pixels
        self.coded_pixels = coord_to_code(_x, _y).ravel()
        self.data_to_fit = self.z.ravel()
        self.data_to_fit_err = np.sqrt(np.fabs(self.data_to_fit))
        self.data_to_fit_err[self.data_to_fit_err<1] = 1

        # 1D data x/y vs counts
        self.x_vs_counts = np.sum(self.z, 1)
        self.y_vs_counts = np.sum(self.z, 0)

        # Use the highest data point as a starting point for a simple Gaussian fit
        self.center_x = np.argmax(self.x_vs_counts)
        self.center_y = np.argmax(self.y_vs_counts)

        self.guess_x = self.center_x
        self.guess_wx = 6
        self.guess_y = self.center_y
        self.guess_wy = 100
        self.guess_chi2 = np.inf

        # Plots [optional]
        self.plot_list = []
        self.plot_labels = []
        if self.prepare_plot_data:
            self.plot_list = [[self.x, self.x_vs_counts],]
            self.plot_labels = ['Data',]

    def _perform_beam_fit(self, y_d, derivative, derivative_err, y_r=None, signal_r=None, gaussian_first=False):
        if gaussian_first:
            _running_err = np.sqrt(signal_r)
            _gauss, _ = opt.curve_fit(self.gaussian_1d, y_r,
                                      signal_r, p0=[np.max(signal_r), 140, 50, 0], sigma=_running_err)
            p0 = [np.max(derivative), _gauss[1], 2.0*_gauss[2], 5, 0]
        else:
            p0 = [np.max(derivative), 140, 60, 5, 0]

        #p = A, center_x, width_x, edge_width, background
        _coef, _ = opt.curve_fit(self.peak_derivative, y_d, derivative, p0=p0, sigma=derivative_err)
        return _coef

    def fit_beam_width(self):
        """
            Fit the data distribution in y and get its range.
        """
        _y0 = np.arange(len(self.y_vs_counts))[self.DEAD_PIXELS:-self.DEAD_PIXELS]
        _signal = self.y_vs_counts[self.DEAD_PIXELS:-self.DEAD_PIXELS]

        _integral = [np.sum(_signal[:i]) for i in range(len(_signal))]
        _running = 0.1*np.convolve(_signal, np.ones(10), mode='valid')
        _deriv = np.asarray([_running[i+1]-_running[i] for i in range(len(_running)-1)])
        _deriv_err = np.sqrt(_running)[:-1]
        _y = _y0[5:-5]

        try:
            _coef = self._perform_beam_fit(_y, _deriv, _deriv_err, gaussian_first=False)
            peak_min = _coef[1] - _coef[2]/2.0 - 2.0*_coef[3]
            peak_max = _coef[1] + _coef[2]/2.0 + 2.0*_coef[3]
            if peak_max - peak_min < 10:
                _y_running = _y0[5:-4]
                _coef = self._perform_beam_fit(_y, _deriv, _deriv_err, _y_running, _running, gaussian_first=True)
        except:
            return [int(self.guess_y-self.guess_wy/2.0), int(self.guess_y+self.guess_wy/2.0)]

        return [int(peak_min), int(peak_max)]

    def get_roi(self, region):
        """
            Select are region of interest and prepare the data for fitting.
            :param region: Length 2 list of min/max pixels defining the ROI
        """
        _roi = np.asarray([x_i>region[0] and x_i<=region[1] for x_i in self.x])
        x_roi = self.x[_roi]
        z_roi = self.z[_roi]

        _x_roi, _y_roi = np.meshgrid(x_roi, self.y)
        _x_roi = _x_roi.T
        _y_roi = _y_roi.T
        code_roi = coord_to_code(_x_roi, _y_roi).ravel()
        data_to_fit_roi = z_roi.ravel()
        err_roi = np.sqrt(np.fabs(data_to_fit_roi))
        err_roi[err_roi<1] = 1

        return code_roi, data_to_fit_roi, err_roi

    def _scan_peaks(self):
        """
            Perform a quick scan of the count distribution in x to find obvious peaks.
            We first convolute the distribution with a step function to get rid of
            noise, then we compute the first derivative. We identify a peak when the
            difference in the slop between two consecutive points is greater than
            half the total counts.
        """
        found_peaks = []
        # Derivative
        _convo_narrow = np.zeros(len(self.x_vs_counts))
        _width = 2
        total_counts = np.sum(self.x_vs_counts)

        for i, _ in enumerate(_convo_narrow):
            _step = [1 if abs(i-j)<=_width else 0 for j in range(len(self.x_vs_counts))]
            _convo_narrow[i] = np.sum(_step*self.x_vs_counts)
        _deriv = [ _convo_narrow[i+1] - _convo_narrow[i] for i in range(len(_convo_narrow)-1) ]

        _up = None
        _i_value = 0
        for i in range(len(_deriv)-1):
            if i==0:
                _up = _deriv[i+1] > _deriv[i]
                _i_value = i + 1
            elif _up:
                if _deriv[i+1] > _deriv[i]:
                    _i_value = i + 1
                else:
                    _up = False
            else:
                if _deriv[i+1] > _deriv[i]:
                    if _deriv[_i_value] - _deriv[i+1] > np.sqrt(total_counts)/2 \
                    and _i_value>self.DEAD_PIXELS and _i_value<self.n_x-self.DEAD_PIXELS:
                        found_peaks.append(int((_i_value + i) / 2.0))
                    _up = True
                    _i_value = i + 1

        # Too many peaks is not good, because it means that we haven't correctly
        # identified the reflected beam and the direct beam.
        if len(found_peaks)>2:
            return []

        if found_peaks:
            self.guess_x = found_peaks[0] - self.DEFAULT_PEAK_WIDTH
            self.guess_wx = found_peaks[0] + self.DEFAULT_PEAK_WIDTH

        return found_peaks

    def _fit_gaussian(self):
        """
            Fit a simple Gaussian and constant background
        """
        if self.peaks:
            center_x = self.peaks[0]
        else:
            center_x = self.center_x

        # Scale, mu_x, sigma_x, mu_y, sigma_y, background
        p0 = [np.max(self.z), center_x, 5, self.center_y, 50, 0]
        try:
            gauss_coef, _ = opt.curve_fit(self.gaussian,
                                          self.coded_pixels,
                                          self.data_to_fit, p0=p0,
                                          sigma=self.data_to_fit_err)
        except:
            api.logger.notice("Could not fit simple Gaussian")
            gauss_coef = p0

        # Keep track of the result
        theory = self.gaussian(self.coded_pixels, *gauss_coef)
        theory = np.reshape(theory, (self.n_x, self.n_y))
        _chi2 = chi2(theory, self.z)

        # Fitting a Gaussian tends to give a narrower peak than we
        # really need, so we're multiplying the width by two.
        if _chi2 < self.guess_chi2:
            self.guess_x = gauss_coef[1]
            self.guess_wx = 2.0 * gauss_coef[2]
            self.guess_y = gauss_coef[3]
            self.guess_wy = 2.0 * gauss_coef[4]
            self.guess_chi2 = _chi2

        if self.prepare_plot_data:
            th_x = np.sum(theory, 1)
            self.plot_list.append([self.x, th_x])
            self.plot_labels.append('Gaussian')
            api.logger.notice("Chi2[Gaussian] = %s" % _chi2)
            api.logger.notice("    %g +- %g" % (gauss_coef[1], gauss_coef[2]))

    def _fit_gaussian_and_poly(self):
        """
            Fit a Gaussian with a polynomial background. First fit the background,
            then keep it constant and add a Gaussian.
        """
        if self.peaks:
            center_x = self.peaks[0]
        else:
            center_x = self.center_x

        try:
            poly_bck_coef, _ = opt.curve_fit(self.poly_bck, self.coded_pixels, self.data_to_fit,
                                             p0=[np.max(self.z), 0, 0, center_x, 0], sigma=self.data_to_fit_err)
        except:
            api.logger.notice("Could not fit polynomial background")
            poly_bck_coef = [0, 0, 0, self.center_x, 0]
        theory = self.poly_bck(self.coded_pixels, *poly_bck_coef)
        theory = np.reshape(theory, (self.n_x, self.n_y))
        _chi2 = None

        if self.prepare_plot_data:
            _chi2 = chi2(theory, self.z)
            th_x = np.sum(theory, 1)
            self.plot_list.append([self.x, th_x])
            self.plot_labels.append('Polynomial')
            api.logger.notice("Chi2[Polynomial] = %g" % _chi2)

        # Now fit a Gaussian + background
        # A, mu_x, sigma_x, mu_y, sigma_y, background
        self.poly_bck_coef = poly_bck_coef
        coef = [np.max(self.z), self.center_x, 5, self.center_y, 50, 0]
        try:
            coef, _ = opt.curve_fit(self.gaussian_and_fixed_poly_bck, self.coded_pixels, self.data_to_fit,
                                    p0=coef, sigma=self.data_to_fit_err)
            theory = self.gaussian_and_fixed_poly_bck(self.coded_pixels, *coef)
            theory = np.reshape(theory, (self.n_x, self.n_y))
            _chi2 = chi2(theory, self.z)
        except:
            api.logger.notice("Could not fit Gaussian + polynomial")

        # Fitting a Gaussian tends to give a narrower peak than we
        # really need, so we're multiplying the width by two.
        if _chi2 and _chi2 < self.guess_chi2:
            self.guess_x = coef[1]
            self.guess_wx = 2.0 * coef[2]
            self.guess_y = coef[3]
            self.guess_wy = 2.0 * coef[4]
            self.guess_chi2 = _chi2

        if _chi2 and self.prepare_plot_data:
            th_x = np.sum(theory, 1)
            self.plot_list.append([self.x, th_x])
            self.plot_labels.append('Gaussian + polynomial')
            api.logger.notice("Chi2[Gaussian + polynomial] = %g" % _chi2)
            api.logger.notice("    %g +- %g" % (coef[1], coef[2]))

    def _fit_lorentz_2d(self, peak=True):
        """
            Fit a Lorentzian peak, usually to fit the direct beam
        """
        # Find good starting point according to whether we are fitting a
        # reflected peak or a direct beam peak.
        dirpix= self.center_x
        if self.peaks and len(self.peaks) < 3:
            dirpix = self.peaks[0]
        if not peak:
            if len(self.peaks) > 1 and len(self.peaks) < 3:
                dirpix = self.peaks[1]
            else:
                dirpix = self.dirpix

        # Scale, mu_x, fwhm, mu_y, sigma_y, background
        p0 = [np.max(self.z), dirpix, 10, 128, 100, 0]
        try:
            lorentz_coef, _ = opt.curve_fit(self.lorentzian,
                                            self.coded_pixels,
                                            self.data_to_fit, p0=p0,
                                            sigma=self.data_to_fit_err)
        except:
            api.logger.notice("Could not fit Lorentzian")
            lorentz_coef = p0

        # Keep track of the result
        theory = self.lorentzian(self.coded_pixels, *lorentz_coef)
        theory = np.reshape(theory, (self.n_x, self.n_y))
        _chi2 = chi2(theory, self.z)

        if self.prepare_plot_data:
            th_x = np.sum(theory, 1)
            self.plot_list.append([self.x, th_x])
            self.plot_labels.append('Lorentz 2D')
            api.logger.notice("Chi2[Lorentz 2D] = %s" % _chi2)
            api.logger.notice("    %g +- %g" % (lorentz_coef[1], lorentz_coef[2]))
        return lorentz_coef

    def _gaussian_and_lorentzian(self, region):
        """
            Fit a Gaussian on top of a lorentzian background.
            First fit the Lorentzian, then keep it constant to fit a Gaussian on top.
            :param list region: Length 2 list defining the x region to fit in
        """
        if len(self.peaks) > 1:
            center_x = self.peaks[0]
        elif len(self.peaks) == 1:
            center_x = self.peaks[0]
        else:
            center_x = self.center_x

        # Fit the Lorentzian background first
        self.lorentz_coef = self._fit_lorentz_2d(peak=False)

        # Extract the region we want to fit over
        code_roi, data_to_fit_roi, err_roi = self.get_roi(region)

        #A, mu_x, sigma_x, mu_y, sigma_y, poly_a, poly_b, poly_c, center, background
        p0 = [np.max(data_to_fit_roi), center_x, 5, self.center_y, 50, 0, 0, 0, center_x, 0]
        try:
            lorentz_coef, _ = opt.curve_fit(self.gaussian_and_fixed_lorentzian,
                                            code_roi,
                                            data_to_fit_roi, p0=p0,
                                            sigma=err_roi)
        except:
            api.logger.notice("Could not fit G+L")
            lorentz_coef = p0

        api.logger.notice("G+L params: %s" % str(lorentz_coef))
        # Keep track of the result
        theory = self.gaussian_and_fixed_lorentzian(self.coded_pixels, *lorentz_coef)
        theory = np.reshape(theory, (self.n_x, self.n_y))
        _chi2 = chi2(theory, self.z)

        # If we decided to fit two peaks, we should take the results regardless
        # of goodness of fit because the models are imprecise.
        # Nonetheless, log an entry if the chi^2 is larger
        if _chi2 > self.guess_chi2:
            api.logger.notice("Fitting with two peaks resulted in a larger chi^2: %g > %g" % (_chi2, self.guess_chi2))

        # Unless we have a crazy peak
        if lorentz_coef[1] > self.peaks[0]-10 and lorentz_coef[1] < self.peaks[0]+10:
            # Fitting a Gaussian tends to give a narrower peak than we
            # really need, so we're multiplying the width by two.
            self.guess_x = lorentz_coef[1]
            self.guess_wx = 2.0 * lorentz_coef[2]
            self.guess_y = lorentz_coef[3]
            self.guess_wy = 2.0 * lorentz_coef[4]
            self.guess_chi2 = _chi2

        if self.prepare_plot_data:
            th_x = np.sum(theory, 1)
            self.plot_list.append([self.x, th_x])
            self.plot_labels.append('G + Lorentz 2D')
            api.logger.notice("Chi2[G + Lorentz] = %s" % _chi2)
            api.logger.notice("    %g +- %g" % (lorentz_coef[1], lorentz_coef[2]))
        return lorentz_coef

    def fit_2d_peak(self, region=None):
        """
            Fit a 2D Gaussian peak
            :param region: region of interest for the reflected peak
        """
        self.peaks = self._scan_peaks()
        api.logger.notice("Peaks (rough scan): %s" % self.peaks)

        # Gaussian fit
        self._fit_gaussian()

        # Fit a polynomial background, as a starting point to fitting signal + background
        self._fit_gaussian_and_poly()

        if len(self.peaks) > 1:
            if region is None:
                region = [self.peaks[0]-20, self.peaks[0]+20]
            self._gaussian_and_lorentzian(region)

        # Package the best results
        x_min = max(0, int(self.guess_x-np.fabs(self.guess_wx)))
        x_max = min(self.n_x-1, int(self.guess_x+np.fabs(self.guess_wx)))
        y_min = max(0, int(self.guess_y-np.fabs(self.guess_wy)))
        y_max = min(self.n_y-1, int(self.guess_y+np.fabs(self.guess_wy)))

        return [x_min, x_max], [y_min, y_max]

    # Fit function definitions #####################################################
    def _crop_detector_edges(self, coord, values):
        """
            Crop the edges of the detector and fill them with zeros.
        """
        values[coord[0]<self.DEAD_PIXELS] = 0
        values[coord[0]>self.n_x-self.DEAD_PIXELS] = 0
        values[coord[1]<self.DEAD_PIXELS] = 0
        values[coord[1]>self.n_y-self.DEAD_PIXELS] = 0
        return values

    def poly_bck(self, value, *p):
        """
            Polynomial function for background fit

            f = a + b*(x-center) + c*(x-center)**2 + bck

            where bck is a minimum threshold that is zero when the polynomial
            has a value greater than it.
        """
        coord = code_to_coord(value)
        poly_a, poly_b, poly_c, center, background = p
        values = poly_a + poly_b*(coord[0]-center) + poly_c*(coord[0]-center)**2
        values[values<background] = background
        return self._crop_detector_edges(coord, values)

    def gaussian(self, value, *p):
        """
            Gaussian function with constant background
        """
        coord = code_to_coord(value)
        A, mu_x, sigma_x, mu_y, sigma_y, background = p
        if sigma_x > 30:
            return np.ones(len(coord)) * np.inf
        values =  abs(A) * np.exp(-(coord[0] - mu_x)**2 / (2. * sigma_x**2) - (coord[1] - mu_y)**2 / (2. * sigma_y**2)) + abs(background)
        return self._crop_detector_edges(coord, values)

    def gaussian_and_poly_bck(self, value, *p):
        """
            Function for a polynomial + Gaussian signal
        """
        coord = code_to_coord(value)
        A, mu_x, sigma_x, mu_y, sigma_y, poly_a, poly_b, poly_c, center, background = p
        poly_coef = [poly_a, poly_b, poly_c, center, background]
        values = self.poly_bck(value, *poly_coef)
        gauss_coef = [A, mu_x, sigma_x, mu_y, sigma_y, 0]
        values += self.gaussian(value, *gauss_coef)
        return self._crop_detector_edges(coord, values)

    def gaussian_and_fixed_poly_bck(self, value, *p):
        """
            Use result of bck fit and add a Gaussian
        """
        coord = code_to_coord(value)
        values = self.poly_bck(value, *self.poly_bck_coef)
        values += self.gaussian(value, *p)
        return self._crop_detector_edges(coord, values)

    def lorentzian(self, value, *p):
        """
            Peak function in 2D. The main axis (x) is a Lorentzian and the other axis (y) is a Gaussian.
        """
        coord = code_to_coord(value)
        A, mu_x, sigma_x, mu_y, sigma_y, background = p
        values =  abs(A)/(1+((coord[0]-mu_x)/sigma_x)**2) * np.exp(-(coord[1]-mu_y)**2/(2.*sigma_y**2)) + abs(background)
        return self._crop_detector_edges(coord, values)

    def gaussian_and_fixed_lorentzian(self, value, *p):
        """
            Gaussian and polynomial on top of a fixed Lorentzian.
        """
        coord = code_to_coord(value)
        values = self.lorentzian(value, *self.lorentz_coef)
        values += self.gaussian_and_poly_bck(value, *p)
        return self._crop_detector_edges(coord, values)

    def gaussian_1d(self, value, *p):
        """
            1D Gaussian
        """
        A, center_x, width_x, background = p
        A = np.abs(A)
        values = A*np.exp(-(value-center_x)**2/(2.*width_x**2))
        values += background
        return values

    def peak_derivative(self, value, *p):
        """
            Double Gaussian to fit the first derivative of a plateau/peak.
        """
        A, center_x, width_x, edge_width, background = p
        mu_right = center_x + width_x / 2.0
        mu_left = center_x - width_x / 2.0
        A = np.abs(A)
        values = A*np.exp(-(value-mu_left)**2/(2.*edge_width**2)) - A*np.exp(-(value-mu_right)**2/(2.*edge_width**2))
        values += background
        return values


class Fitter2(object):
    DEAD_PIXELS = 10

    def __init__(self, workspace):
        self.workspace = workspace
        self._prepare_data()

    def _prepare_data(self):
        """
            Read in the data and create arrays for fitting
        """
        # Prepare data to fit
        self.n_x = int(self.workspace.getInstrument().getNumberParameter("number-of-x-pixels")[0])
        self.n_y = int(self.workspace.getInstrument().getNumberParameter("number-of-y-pixels")[0])

        _integrated = api.Integration(InputWorkspace=self.workspace)
        signal = _integrated.extractY()
        self.z=np.reshape(signal, (self.n_x, self.n_y))
        self.y = np.arange(0, self.n_y)[self.DEAD_PIXELS:-self.DEAD_PIXELS]
        # 1D data x/y vs counts
        self.x_vs_counts = np.sum(self.z, 1)
        self.y_vs_counts = np.sum(self.z, 0)

        self.guess_x = np.argmax(self.x_vs_counts)
        self.guess_wx = 6.

    def _scan_peaks(self):
        f1 = ndimage.gaussian_filter(self.x_vs_counts, 3)
        peaks, _ = find_peaks(f1)
        prom, _, _ = peak_prominences(f1, peaks)
        peaks_w, _, _, _ = peak_widths(f1, peaks)

        # The quality factor is the size of the peak (height*width) multiply by
        # a factor that peaks in the middle of the detector, where the peak usually is.
        nx = 304.
        delta = 100.
        mid_point = 150.
        quality_pos = np.exp(-(mid_point-peaks)**2./2000.)
        low_peaks = peaks<delta
        high_peaks = peaks>nx-delta
        quality_pos[low_peaks] = quality_pos[low_peaks]  * (1 - np.abs(delta-peaks[low_peaks])/delta)**3
        quality_pos[high_peaks] = quality_pos[high_peaks] * (1 - np.abs(nx-delta-peaks[high_peaks])/delta)**3
        quality = -peaks_w * prom * quality_pos

        zipped = zip(peaks, peaks_w, quality, prom)
        ordered = sorted(zipped, key=lambda a:a[2])
        found_peaks = [p[0] for p in ordered]

        if found_peaks:
        #    self.guess_x = ordered[0][0]
        #    self.guess_ws = ordered[0][1]
            i_final = 0
            if len(ordered)>1 and (ordered[0][2] - ordered[1][2])/ordered[0][2] < 0.75 and ordered[1][0] < ordered[0][0]:
                i_final = 1
            self.guess_x = ordered[i_final][0]
            self.guess_ws = ordered[i_final][1]

        return found_peaks

    def fit_2d_peak(self):
        """ Backward compatibility """
        spec_peak = self.fit_peak()
        beam_peak = self.fit_beam_width()
        return spec_peak, beam_peak

    def fit_peak(self):
        self.peaks = self._scan_peaks()

        # Package the best results
        x_min = int(max(0, int(self.guess_x-np.fabs(self.guess_wx))))
        x_max = int(min(self.n_x-1, int(self.guess_x+np.fabs(self.guess_wx))))

        return [x_min, x_max]

    def gaussian_1d(self, value, *p):
        """
            1D Gaussian
        """
        A, center_x, width_x, background = p
        A = np.abs(A)
        values = A*np.exp(-(value-center_x)**2/(2.*width_x**2))
        values += background
        return values

    def peak_derivative(self, value, *p):
        """
            Double Gaussian to fit the first derivative of a plateau/peak.
        """
        A, center_x, width_x, edge_width, background = p
        mu_right = center_x + width_x / 2.0
        mu_left = center_x - width_x / 2.0
        A = np.abs(A)
        values = A*np.exp(-(value-mu_left)**2/(2.*edge_width**2)) - A*np.exp(-(value-mu_right)**2/(2.*edge_width**2))
        values += background
        return values

    def _perform_beam_fit(self, y_d, derivative, derivative_err, y_r=None, signal_r=None, gaussian_first=False):
        if gaussian_first:
            _running_err = np.sqrt(signal_r)
            _gauss, _ = opt.curve_fit(self.gaussian_1d, y_r,
                                      signal_r, p0=[np.max(signal_r), 140, 50, 0], sigma=_running_err)
            p0 = [np.max(derivative), _gauss[1], 2.0*_gauss[2], 5, 0]
        else:
            p0 = [np.max(derivative), 140, 60, 5, 0]

        #p = A, center_x, width_x, edge_width, background
        _coef, _ = opt.curve_fit(self.peak_derivative, y_d, derivative, p0=p0, sigma=derivative_err)
        return _coef

    def fit_beam_width(self):
        """
            Fit the data distribution in y and get its range.
        """
        peak_min = 0
        peak_max = int(self.n_x)
        try:
            _integral = [np.sum(self.y_vs_counts[:i]) for i in range(len(self.y_vs_counts))]
            _running = 0.1*np.convolve(self.y_vs_counts, np.ones(10), mode='valid')
            _deriv = np.asarray([_running[i+1]-_running[i] for i in range(len(_running)-1)])
            _deriv_err = np.sqrt(_running)[:-1]
            _deriv_err[_deriv_err<1] = 1
            _y = np.arange(len(self.y_vs_counts))[5:-5]
    
            _coef = self._perform_beam_fit(_y, _deriv, _deriv_err, gaussian_first=False)
            peak_min = _coef[1] - np.abs(_coef[2])/2.0 - 2.0 * np.abs(_coef[3])
            peak_max = _coef[1] + np.abs(_coef[2])/2.0 + 2.0 * np.abs(_coef[3])
            if peak_max - peak_min < 10:
                api.logger.notice("Low statisting: trying again")
                _y_running = self.y[5:-4]
                _coef = self._perform_beam_fit(_y, _deriv, _deriv_err, _y_running, _running, gaussian_first=True)
    
            self.guess_y = _coef[1]
            self.guess_wy = (peak_max - peak_min) / 2.0
            peak_min = int(max(peak_min, self.DEAD_PIXELS))
            peak_max = int(min(peak_max, self.n_x-self.DEAD_PIXELS))
        except:
            api.logger.notice("Could not fit the beam width")
        return [peak_min, peak_max]
