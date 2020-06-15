#pylint: disable=bare-except
import sys
import traceback
import time
import numpy as np
import mantid
from mantid import simpleapi as api

AR_DIR = "/SNS/REF_M/shared/autoreduce"
if AR_DIR not in sys.path:
    sys.path.append(AR_DIR)
LIVE_DIR = "/SNS/REF_M/shared/livereduce"
if LIVE_DIR not in sys.path:
    sys.path.append(LIVE_DIR)
from mr_reduction import mr_reduction as refm
from mr_reduction.web_report import _plot1d
from mr_reduction.web_report import _plot2d

DEBUG = False
if DEBUG:
    logfile = open("/SNS/REF_M/shared/autoreduce/MR_live_outer.log", 'a')
    logfile.write("Starting post-proc\n")

pol_info = ''
try:
    import polarization_analysis
except:
    pol_info = "<div>Error: %s</div>\n" % sys.exc_info()[1]

def generate_plots(run_number, workspace):
    """
        Generate diagnostics plots
    """
    n_x = int(workspace.getInstrument().getNumberParameter("number-of-x-pixels")[0])
    n_y = int(workspace.getInstrument().getNumberParameter("number-of-y-pixels")[0])

    # X-TOF plot
    tof_min = workspace.getTofMin()
    tof_max = workspace.getTofMax()
    workspace = api.Rebin(workspace, params="%s, 50, %s" % (tof_min, tof_max))

    direct_summed = api.RefRoi(InputWorkspace=workspace, IntegrateY=True,
                           NXPixel=n_x, NYPixel=n_y,
                           ConvertToQ=False, YPixelMin=0, YPixelMax=n_y,
                           OutputWorkspace="direct_summed")
    signal = np.log10(direct_summed.extractY())
    tof_axis = direct_summed.extractX()[0]/1000.0

    x_tof_plot = _plot2d(z=signal, y=range(signal.shape[0]), x=tof_axis,
                         x_label="TOF (ms)", y_label="X pixel",
                         title="r%s" % run_number)

    # X-Y plot
    _workspace = api.Integration(workspace)
    signal = np.log10(_workspace.extractY())
    z=np.reshape(signal, (n_x, n_y))
    xy_plot = _plot2d(z=z.T, x=np.arange(n_x), y=np.arange(n_y),
                      title="r%s" % run_number)

    # Count per X pixel
    integrated = api.Integration(direct_summed)
    integrated = api.Transpose(integrated)
    signal_y = integrated.readY(0)
    signal_x = range(len(signal_y))
    peak_pixels = _plot1d(signal_x,signal_y,
                          x_label="X pixel", y_label="Counts",
                          title="r%s" % run_number)

    # TOF distribution
    workspace = api.SumSpectra(workspace)
    signal_x = workspace.readX(0)/1000.0
    signal_y = workspace.readY(0)
    tof_dist = _plot1d(signal_x,signal_y, x_range=None,
                       x_label="TOF (ms)", y_label="Counts",
                       title="r%s" % run_number)

    return [xy_plot, x_tof_plot, peak_pixels, tof_dist]

try:
    run_number = input.getRunNumber()
except:
    run_number = 0

try:
    plots = generate_plots(run_number, input)
except:
    plots = []
    pol_info += "<div>Error generating plots</div>\n"
    mantid.logger.error(str(sys.exc_info()[1]))

info = ''
try:
    n_evts = input.getNumberEvents()
    seq_number = input.getRun()['sequence_number'].value[0]
    seq_total = input.getRun()['sequence_total'].value[0]
    info = "<div>Events: %s</div>\n" % n_evts
    info += "<div>Sequence: %s of %s</div>\n" % (seq_number, seq_total) 
    info += "<div>Report time: %s</div>\n" % time.ctime()
except:
    info = "<div>Error: %s</div>\n" % sys.exc_info()[1]

pol_info += "<table style='width:100%'>\n"
ws = None
try:
    tof_min = input.getTofMin()
    tof_max = input.getTofMax()
    ws = api.Rebin(input, params="%s, 50, %s" % (tof_min, tof_max), PreserveEvents=True)
    ws_list, ratio1, ratio2, asym1, labels = polarization_analysis.calculate_ratios(ws, delta_wl=0.05, slow_filter=True)#, roi=[60,110,80,140])
    pol_info += "<tr><td>Number of polarization states: %s</td></tr>\n" % len(ws_list)
    if True:
        if ratio1 is not None:
            signal_x = ratio1.readX(0)
            signal_y = ratio1.readY(0)
            div_r1 = _plot1d(signal_x,signal_y, x_range=None,
                             x_label="Wavelength", y_label=labels[0],
                             title="", x_log=False, y_log=False)
            pol_info += "<td>%s</td>\n" % div_r1
            pol_info += "</tr>\n"
        if ratio2 is not None:
            signal_x = ratio2.readX(0)
            signal_y = ratio2.readY(0)
            div_r1 = _plot1d(signal_x,signal_y, x_range=None,
                             x_label="Wavelength", y_label=labels[1],
                             title="", x_log=False, y_log=False)
            pol_info += "<td>%s</td>\n" % div_r1
            pol_info += "</tr>\n"
        if asym1 is not None:
            signal_x = asym1.readX(0)
            signal_y = asym1.readY(0)
            div_r1 = _plot1d(signal_x,signal_y, x_range=None,
                               x_label="Wavelength", y_label=labels[2],
                               title="", x_log=False, y_log=False)
            pol_info += "<td>%s</td>\n" % div_r1
            pol_info += "</tr>\n"
    else:
        pol_info += "<tr>\n"
        div_r1 = api.SavePlot1D(InputWorkspace=ratio1, OutputType='plotly')
        pol_info += "<td>%s</td>\n" % div_r1
        pol_info += "</tr>\n"
except:
    pol_info += "<div>Error: %s</div>\n" % sys.exc_info()[1]
pol_info += "</table>\n"

# Try to reduce the data
reduction_info = ''
if run_number>0 and ws is not None:
    try:
        ws = api.Rebin(input, params="%s, 50, %s" % (tof_min, tof_max), PreserveEvents=True)
        red = refm.ReductionProcess(data_run=None, data_ws=ws, output_dir=None, use_roi=False,
                                    update_peak_range=True, publish=False, debug=True)
        red.pol_state = "SF1"
        red.pol_veto = "SF1_Veto"
        red.ana_state = "SF2"
        red.ana_veto = "SF2_Veto"
        red.use_slow_flipper_log = True
        reduction_info=red.reduce()
    except:
        reduction_info += "<div>Could not reduce the data</div>\n"
        reduction_info += "<div>%s</div>\n" % sys.exc_info()[0]
        if DEBUG:
            logfile.write(str(sys.exc_info()[1]))

output = input

plot_html = "<div>Live data</div>\n"
plot_html += info
plot_html += reduction_info
plot_html += "<table style='width:100%'>\n"
plot_html += "<tr>\n"
for plot in plots:
    plot_html += "<td>%s</td>\n" % plot
plot_html += "</tr>\n"
plot_html += "</table>\n"
plot_html += "<hr>\n"
plot_html += pol_info

if DEBUG:
    logfile.write("html ready\n")

try:
    mantid.logger.information('Posting plot of run %s' % run_number)
    try: # version on autoreduce
        from postprocessing.publish_plot import publish_plot
    except ImportError: # version on instrument computers
        from finddata import publish_plot
    request = publish_plot('REF_M', run_number, files={'file':plot_html})
except:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    if DEBUG:
        for line in traceback.format_exception(exc_type, exc_value, exc_traceback):
            logfile.write(line)
if DEBUG:
    logfile.write("DONE\n")
    logfile.close()
