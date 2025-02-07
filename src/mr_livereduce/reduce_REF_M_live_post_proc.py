# standard imports
import json
import os
import sys
import time
import traceback

import mantid
import numpy as np
from mantid import simpleapi as api
from mr_reduction import mr_reduction as refm
from mr_reduction.web_report import _plot1d, _plot2d

# autoreduce_2020-2024/ contains legacy mr_reduction module.
# To be used when CONDA_ENV = "mantid-dev"
AR_DIR = "/SNS/REF_M/shared/autoreduce/autoreduce_2020-2024"
if AR_DIR not in sys.path:
    sys.path.append(AR_DIR)
LIVE_DIR = "/SNS/REF_M/shared/livereduce"
if LIVE_DIR not in sys.path:
    sys.path.append(LIVE_DIR)


DEBUG = True
if DEBUG:
    logfile = open("/SNS/REF_M/shared/autoreduce/MR_live_outer.log", "a")
    logfile.write("Starting post-proc\n")

pol_info = ""
try:
    import polarization_analysis
except (ImportError, ModuleNotFoundError):
    pol_info = "<div>Error: %s</div>\n" % sys.exc_info()[1]


def read_configuration():
    """
    Read the reduction options from the automated reduction script.
    """
    _json_data = ""
    with open(os.path.join(AR_DIR, "reduce_REF_M.py"), "r") as fd:
        _json_started = False
        for line in fd.readlines():
            if "END_JSON" in line:
                _json_started = False
            if _json_started:
                # The assumption is that all parameters are lowercase.
                # Json only understands true/false, but not True/False.
                _json_data += line.lower()
            if "START_JSON" in line:
                _json_started = True

    if len(_json_data) > 0:
        try:
            return json.loads(_json_data)
        except json.JSONDecodeError:
            if DEBUG:
                logfile.write("Could not parse reduction options from the reduction script\n")
    return None


def call_reduction(ws, options=None):
    """
    Call automated reduction.
    Use good defaults when no configuration is available.
    """

    if options:
        if DEBUG:
            logfile.write("Using reduction options\n")
        use_const_q = options["use_const_q"] if "use_const_q" in options else False
        fit_peak_in_roi = options["fit_peak_in_roi"] if "fit_peak_in_roi" in options else False
        use_roi_bck = options["use_roi_bck"] if "use_roi_bck" in options else False
        force_peak = options["force_peak"] if "force_peak" in options else False
        peak_roi = [0, 0]
        if "peak_min" in options and "peak_max" in options:
            peak_roi = [options["peak_min"], options["peak_max"]]
        use_side_bck = options["use_side_bck"] if "use_side_bck" in options else False
        bck_width = options["bck_width"] if "bck_width" in options else 3
        use_sangle = options["use_sangle"] if "use_sangle" in options else True
        force_background = options["force_background"] if "force_background" in options else False
        bck_roi = [0, 0]
        if "bck_min" in options and "bck_max" in options:
            bck_roi = [options["bck_min"], options["bck_max"]]

        return refm.ReductionProcess(
            data_run=None,
            data_ws=ws,
            output_dir=None,
            use_sangle=use_sangle,
            const_q_binning=use_const_q,
            update_peak_range=fit_peak_in_roi,
            use_roi=True,
            debug=DEBUG,
            use_roi_bck=use_roi_bck,
            force_peak_roi=force_peak,
            peak_roi=peak_roi,
            force_bck_roi=force_background,
            bck_roi=bck_roi,
            use_tight_bck=use_side_bck,
            bck_offset=bck_width,
        )

    else:
        return refm.ReductionProcess(
            data_run=None,
            data_ws=ws,
            output_dir=None,
            use_roi=False,
            use_sangle=False,
            update_peak_range=True,
            publish=False,
            debug=True,
        )


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

    direct_summed = api.RefRoi(
        InputWorkspace=workspace,
        IntegrateY=True,
        NXPixel=n_x,
        NYPixel=n_y,
        ConvertToQ=False,
        YPixelMin=0,
        YPixelMax=n_y,
        OutputWorkspace="direct_summed",
    )
    signal = np.log10(direct_summed.extractY())
    tof_axis = direct_summed.extractX()[0] / 1000.0

    x_tof_plot = _plot2d(
        z=signal,
        y=np.arange(signal.shape[0]),
        x=tof_axis,
        x_label="TOF (ms)",
        y_label="X pixel",
        title="r%s" % run_number,
    )

    # X-Y plot
    _workspace = api.Integration(workspace)
    signal = np.log10(_workspace.extractY())
    z = np.reshape(signal, (n_x, n_y))
    xy_plot = _plot2d(z=z.T, x=np.arange(n_x), y=np.arange(n_y), title="r%s" % run_number)

    # Count per X pixel
    integrated = api.Integration(direct_summed)
    integrated = api.Transpose(integrated)
    signal_y = integrated.readY(0)
    signal_x = np.arange(len(signal_y))
    peak_pixels = _plot1d(signal_x, signal_y, x_label="X pixel", y_label="Counts", title="r%s" % run_number)

    # TOF distribution
    workspace = api.SumSpectra(workspace)
    signal_x = workspace.readX(0) / 1000.0
    signal_y = workspace.readY(0)
    tof_dist = _plot1d(
        signal_x, signal_y, x_range=None, x_label="TOF (ms)", y_label="Counts", title="r%s" % run_number
    )

    return [xy_plot, x_tof_plot, peak_pixels, tof_dist]


# Get reduction options
options = read_configuration()

try:
    run_number = input.getRunNumber()
except Exception:  # noqa BLE001
    run_number = 0

try:
    plots = generate_plots(run_number, input)
except RuntimeError:
    if DEBUG:
        logfile.write("%s\n" % sys.exc_info()[1])
    plots = []
    pol_info += "<div>Error generating plots</div>\n"
    mantid.logger.error(str(sys.exc_info()[1]))

info = ""
try:
    n_evts = input.getNumberEvents()
    seq_number = input.getRun()["sequence_number"].value[0]
    seq_total = input.getRun()["sequence_total"].value[0]
    info = "<div>Events: %s</div>\n" % n_evts
    info += "<div>Sequence: %s of %s</div>\n" % (seq_number, seq_total)
    info += "<div>Report time: %s</div>\n" % time.ctime()
except RuntimeError:
    info = "<div>Error: %s</div>\n" % sys.exc_info()[1]

pol_info += "<table style='width:100%'>\n"
ws = None
try:
    tof_min = input.getTofMin()
    tof_max = input.getTofMax()
    ws = api.Rebin(input, params="%s, 50, %s" % (tof_min, tof_max), PreserveEvents=True)
    ws_list, ratio1, ratio2, asym1, labels = polarization_analysis.calculate_ratios(
        ws, delta_wl=0.05, slow_filter=True
    )  # , roi=[60,110,80,140])
    pol_info += "<tr><td>Number of polarization states: %s</td></tr>\n" % len(ws_list)
    if True:
        if ratio1 is not None:
            signal_x = ratio1.readX(0)
            signal_y = ratio1.readY(0)
            div_r1 = _plot1d(
                signal_x,
                signal_y,
                x_range=None,
                x_label="Wavelength",
                y_label=labels[0],
                title="",
                x_log=False,
                y_log=False,
            )
            pol_info += "<td>%s</td>\n" % div_r1
            pol_info += "</tr>\n"
        if ratio2 is not None:
            signal_x = ratio2.readX(0)
            signal_y = ratio2.readY(0)
            div_r1 = _plot1d(
                signal_x,
                signal_y,
                x_range=None,
                x_label="Wavelength",
                y_label=labels[1],
                title="",
                x_log=False,
                y_log=False,
            )
            pol_info += "<td>%s</td>\n" % div_r1
            pol_info += "</tr>\n"
        if asym1 is not None:
            signal_x = asym1.readX(0)
            signal_y = asym1.readY(0)
            div_r1 = _plot1d(
                signal_x,
                signal_y,
                x_range=None,
                x_label="Wavelength",
                y_label=labels[2],
                title="",
                x_log=False,
                y_log=False,
            )
            pol_info += "<td>%s</td>\n" % div_r1
            pol_info += "</tr>\n"
    else:
        pol_info += "<tr>\n"
        div_r1 = api.SavePlot1D(InputWorkspace=ratio1, OutputType="plotly")
        pol_info += "<td>%s</td>\n" % div_r1
        pol_info += "</tr>\n"
except RuntimeError:
    pol_info += "<div>Error: %s</div>\n" % sys.exc_info()[1]
pol_info += "</table>\n"

# Try to reduce the data
reduction_info = ""
if run_number > 0 and ws is not None:
    try:
        ws = api.Rebin(input, params="%s, 50, %s" % (tof_min, tof_max), PreserveEvents=True)
        red = call_reduction(ws, options=options)
        red.pol_state = "SF1"
        red.pol_veto = "SF1_Veto"
        red.ana_state = "SF2"
        red.ana_veto = "SF2_Veto"
        red.use_slow_flipper_log = True
        reduction_info = red.reduce()
    except RuntimeError:
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
    logfile.write("\nhtml ready\n")
    # logfile.write(plot_html)
try:
    mantid.logger.information("Posting plot of run %s" % run_number)
    try:  # version on autoreduce
        from postprocessing.publish_plot import publish_plot
    except ImportError:  # version on instrument computers
        from finddata import publish_plot
    request = publish_plot("REF_M", run_number, files={"file": plot_html})
except Exception as e:  # noqa: BLE001
    if DEBUG:
        logfile.write("\n" + str(e) + "\n")
        for line in traceback.format_exception(type(e), e, e.__traceback__):
            logfile.write(line)
if DEBUG:
    logfile.write("DONE\n")
    logfile.close()
