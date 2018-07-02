#pylint: disable=bare-except
import sys
import numpy as np
import mantid
from mantid import simpleapi as api

AR_DIR = "/SNS/REF_M/shared/autoreduce"
if AR_DIR not in sys.path:
    sys.path.append(AR_DIR)
from mr_reduction import mr_reduction as refm
from mr_reduction.web_report import _plot1d
from mr_reduction.web_report import _plot2d

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
    
plots = generate_plots(run_number, input)
plot_html = "<div>Live data</div>\n"
plot_html += "<table style='width:100%'>\n"
plot_html += "<tr>\n"
for plot in plots:
    plot_html += "<td>%s</td>\n" % plot
plot_html += "</tr>\n"
plot_html += "</table>\n"
plot_html += "<hr>\n"

mantid.logger.information('Posting plot of run %s' % run_number)
try: # version on autoreduce
    from postprocessing.publish_plot import publish_plot
except ImportError: # version on instrument computers
    from finddata import publish_plot
request = publish_plot('REF_M', run_number, files={'file':plot_html})
mantid.logger.information("post returned %d" % request.status_code)
return 0
