"""
Report class sed to populate the web monitor
"""

# standard imports
import math
import sys
import time
from typing import List, Optional, Tuple, Union

import numpy as np
import plotly.graph_objs as go
import plotly.offline as pyo
import requests

# third party imports
from plot_publisher import publish_plot
from mantid.simpleapi import GeneratePythonScript, Integration, Rebin, RefRoi, SumSpectra, Transpose, logger
from requests import Response
from requests import head as requests_head

# mr_reduction imports
from mr_reduction.data_info import DataType
from mr_reduction.simple_utils import SampleLogs


def html_wrapper(report: Union[str, None]) -> str:
    """Wraps a report (set of <dvi> elements) in a complete HTML document

    Adds the javascript engine (PlotLy.js) address, HTML head, and body tags.

    Parameters
    ----------
    report : str
        The HTML content to be wrapped. This should contain on or more <div> elements and possibly
        summary <table> elements.

    Returns
    -------
    str
        A complete HTML document as a string, with the provided report content embedded within the body.
    """
    js_version = pyo.get_plotlyjs_version()
    url = f"https://cdn.plot.ly/plotly-{js_version}.js"
    try:
        response = requests_head(url, timeout=5)
        assert response.status_code == 200
    except (requests.RequestException, AssertionError):
        logger.error(f"Plotly.js version {js_version} not found, using version 3.0.0 instead")
        url = "https://cdn.plot.ly/plotly-3.0.0.js"

    prefix = f"""<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Plotly Chart</title>
        <script src="{url}"></script>
    </head>
    <body>

    """
    suffix = """

    </body>
    </html>
    """
    report = "" if report is None else report
    return prefix + report + suffix  # allow for report being `None`


def _concatenate_reports(reports: List[str]) -> str:
    if isinstance(reports, (list, tuple)):
        composite = "\n".join([str(report) for report in reports])
    else:
        composite = str(reports)
    return composite


def save_report(html_report: Union[str, List[str]], report_file: str):
    """Save report to a local file

    If `html_report` contains more than one report, then merge them.

    Parameters
    ----------
    html_report : str, List[str]
        One or more compendium of <div> and <table> elements. Has all the information from reducing a run,
        possibly including reports from more than one peak when the run contains many peaks. This could happen
        if the experiment contained more than one sample, each reflecting at a different angle.
    report_file : str
        File path where the report will be saved as an HTML file.
    """
    report_composite = _concatenate_reports(html_report)
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(html_wrapper(report_composite))


def upload_report(html_report: Union[str, List[str]], run_number: Union[str, int]) -> Optional[Response]:
    r"""Upload report to the livedata server

    If `html_report` contains more than one report, then merge them.

    Parameters
    ----------
    html_report: str, List[str]
        one or more compendium of <div> and <table> elements. Has all the information from reducing a run,
        possibly including reports from more than one peak when the run contains many peaks. This could happen
        if the experiment contained more than one sample, each reflecting at a different angle.
    run_number: str, int
        Run number (e.g. '123435'). Required if `publish` is True
    report_file: Optional[str]
        Save the report to a file. If `None` or `False`, the report will not be saved to a file.

    Returns
    -------
    Optional[requests.Response]
        `Response` object returned by the livedata server, or `None` if the function is unable to do find the
        library to generate the `request.post()`
    """
    report_composite = _concatenate_reports(html_report)
    return publish_plot("REF_M", run_number, files={"file": report_composite})


def process_collection(summary_content=None, report_list=None) -> Tuple[str, str]:
    r"""Process a collection of HTML reports into on final HTML report

    Parameters
    ----------
        summary_content: str
            HTML content to be displayed at the top of the report
        report_list: List[mr_reduction.web_report.Report]
            List of HTML contents to be appended at the bottom of the page
        run_number: str
            run number to associate this report with

    Returns
    -------
    Tuple[str, str]
        plot_html str: HTML
        script str: python script
    """
    if report_list is None:
        report_list = []
    logger.notice("Processing... %s" % len(report_list))
    plot_html = "<div></div>"
    script = ""

    if summary_content is not None:
        plot_html += "<div>%s</div>\n" % summary_content

    if report_list:
        plot_html += report_list[0].report
    for report in report_list:
        script += report.script
        plot_html += "<div>%s</div>\n" % report.cross_section_info
        plot_html += "<table style='width:100%'>\n"
        plot_html += "<tr>\n"
        for plot in report.plots:
            if plot is not None:
                plot_html += "<td>%s</td>\n" % plot
        plot_html += "</tr>\n"
        plot_html += "</table>\n"
        plot_html += "<hr>\n"

    return plot_html, script


class Report:
    """
    Take the output of the reduction and generate diagnostics plots, and a block of meta data.
    """

    def __init__(self, workspace, data_info, direct_info, reflectivity_ws, force_plot=True, logfile=None):
        """
        :param bool force_plot: if True, a report will be generated regardless of whether there is enough data
        """
        logger.notice("  - Data type: %s; Reflectivity ws: %s" % (data_info.data_type.name, str(reflectivity_ws)))
        self.data_info = data_info
        self.direct_info = direct_info
        self.logfile = logfile
        try:
            self.cross_section = SampleLogs(workspace)["cross_section_id"]
            self.number_events = workspace.getNumberEvents()
        except:  # noqa E722
            self.number_events = 0
            self.cross_section = ""
        self.has_reflectivity = reflectivity_ws is not None
        self.plots = []
        self.script = ""
        self.report = ""
        self.cross_section_info = ""
        if force_plot or (self.data_info.data_type != DataType.UNKNOWN):
            self.log("  - writing script [%s %s %s]" % (self.cross_section, self.number_events, self.has_reflectivity))
            self.script: str = self.generate_script(reflectivity_ws)
            self.report: str = self.generate_web_report(reflectivity_ws)
            self.cross_section_info = self.generate_cross_section_info(reflectivity_ws)
            try:
                self.plots = self.generate_plots(workspace)
            except:  # noqa E722
                self.log("Could not generate plots: %s" % sys.exc_info()[0])
                logger.error("Could not generate plots: %s" % sys.exc_info()[0])
        else:
            logger.error("Invalid data type for report: %s" % self.data_info.data_type.name)

        self.log("  - report: %s %s" % (len(self.report), len(self.plots)))

    def log(self, msg):
        """Log a message"""
        if self.logfile is not None:
            self.logfile.write(msg + "\n")
        logger.notice(msg)

    def generate_cross_section_info(self, workspace) -> str:
        r"""Generate and HTML table containing cross section information  (event count and proton charge)

        Parameters
        ----------
        workspace : mantid.api.Workspace
            workspace resulting from reduction of one cross-section

        Returns
        -------
        str
        """
        self.log("  - generating cross-section report")
        meta = "<p>\n<table style='width:80%'>"
        meta += "<tr><td>Cross-section:</td><td><b>%s</b></tr>" % self.cross_section
        meta += "<tr><td># events:</td><td>%s</td></tr>" % self.number_events

        if workspace:
            p_charge = SampleLogs(workspace)["gd_prtn_chrg"]
            meta += "<tr><td>p-charge [uAh]:</td><td>%6.4g</td></tr>" % p_charge
        meta += "</table>\n<p>\n"
        return meta

    def generate_web_report(self, workspace) -> str:
        r"""Generate HTML report from a reduced workspace (or the data info object when no workspace is passed)

        Parameters
        ----------
        workspace : mantid.api.Workspace
            workspace resulting from reduction of one cross-section

        Returns
        -------
        str
            Reduction configuration in the form of an HTML table
        """
        self.log("  - generating report")
        if workspace is None:
            self.log("  - simple report")
            meta = "<table style='width:80%'>"
            meta += "<tr><td>Run:</td><td><b>%s</b> (direct beam: %s)</td></td></tr>" % (
                self.data_info.run_number,
                self.data_info.is_direct_beam,
            )
            if not self.data_info.run_number == self.direct_info.run_number:
                meta += "<tr><td>Assigned direct beam:</td><td>%s</td></tr>" % self.direct_info.run_number
            meta += "<tr><td>Using ROI:</td><td>req=%s, actual=%s</td></tr>" % (
                self.data_info.use_roi,
                self.data_info.use_roi_actual,
            )
            meta += "<tr><td>Peak range:</td><td>%s - %s</td></td></tr>" % (
                self.data_info.peak_range[0],
                self.data_info.peak_range[1],
            )
            meta += "<tr><td>Background:</td><td>%s - %s</td></tr>" % (
                self.data_info.background[0],
                self.data_info.background[1],
            )
            meta += "<tr><td>Low-res range:</td><td>%s - %s</td></tr>" % (
                self.data_info.low_res_range[0],
                self.data_info.low_res_range[1],
            )
            meta += "<tr><td>ROI peak:</td><td>%s - %s</td></tr>" % (
                self.data_info.roi_peak[0],
                self.data_info.roi_peak[1],
            )
            meta += "<tr><td>ROI bck:</td><td>%s - %s</td></tr>" % (
                self.data_info.roi_background[0],
                self.data_info.roi_background[1],
            )
            meta += "<tr><td>Sequence:</td><td>%s: %s/%s</td></tr>" % (
                self.data_info.sequence_id,
                self.data_info.sequence_number,
                self.data_info.sequence_total,
            )
            meta += "</table>\n<p>\n"
            return meta

        sample_logs = SampleLogs(workspace)
        constant_q_binning = sample_logs["constant_q_binning"]
        sangle = sample_logs.mean("SANGLE")
        dangle = sample_logs.mean("DANGLE")
        lambda_min = sample_logs["lambda_min"]
        lambda_max = sample_logs["lambda_max"]
        theta = sample_logs["two_theta"] / 2
        direct_beam = sample_logs["normalization_run"]
        dangle0 = sample_logs.mean("DANGLE0")
        dirpix = sample_logs.mean("DIRPIX")

        meta = "<table style='width:80%'>"
        meta += "<tr><td>Run:</td><td><b>%s</b> </td></td><td><b>Direct beam: %s</b></td></tr>" % (
            int(sample_logs["run_number"]),
            direct_beam,
        )
        meta += "<tr><td>Q-binning:</td><td>%s</td><td>-</td></tr>" % constant_q_binning
        meta += "<tr><td>Using ROI:</td><td>req=%s, actual=%s</td><td>req=%s, actual=%s</td></tr>" % (
            self.data_info.use_roi,
            self.data_info.use_roi_actual,
            self.direct_info.use_roi,
            self.direct_info.use_roi_actual,
        )
        meta += "<tr><td>Specular peak:</td><td>%g</td><td>%g</td></tr>" % (
            self.data_info.peak_position,
            self.direct_info.peak_position,
        )
        meta += "<tr><td>Peak range:</td><td>%s - %s</td></td><td>%s - %s</td></tr>" % (
            self.data_info.peak_range[0],
            self.data_info.peak_range[1],
            self.direct_info.peak_range[0],
            self.direct_info.peak_range[1],
        )
        meta += "<tr><td>Background:</td><td>%s - %s</td><td>%s - %s</td></tr>" % (
            self.data_info.background[0],
            self.data_info.background[1],
            self.direct_info.background[0],
            self.direct_info.background[1],
        )
        meta += "<tr><td>Low-res range:</td><td>%s - %s</td><td>%s - %s</td></tr>" % (
            self.data_info.low_res_range[0],
            self.data_info.low_res_range[1],
            self.direct_info.low_res_range[0],
            self.direct_info.low_res_range[1],
        )
        meta += "<tr><td>ROI peak:</td><td>%s - %s</td><td>%s - %s</td></tr>" % (
            self.data_info.roi_peak[0],
            self.data_info.roi_peak[1],
            self.direct_info.roi_peak[0],
            self.direct_info.roi_peak[1],
        )
        meta += "<tr><td>ROI bck:</td><td>%s - %s</td><td>%s - %s</td></tr>" % (
            self.data_info.roi_background[0],
            self.data_info.roi_background[1],
            self.direct_info.roi_background[0],
            self.direct_info.roi_background[1],
        )
        meta += "<tr><td>Sequence:</td><td>%s: %s/%s</td></tr>" % (
            self.data_info.sequence_id,
            self.data_info.sequence_number,
            self.data_info.sequence_total,
        )
        meta += "<tr><td>Report time:</td><td>%s</td></tr>" % time.ctime()
        meta += "</table>\n"

        meta += "<p><table style='width:100%'>"
        meta += "<tr><th>Theta (actual)</th><th>DANGLE [DANGLE0]</th><th>SANGLE</th><th>DIRPIX</th><th>Wavelength</th></tr>"  # noqa E501
        meta += "<tr><td>%6.4g</td><td>%6.4g [%6.4g]</td><td>%6.4g</td><td>%6.4g</td><td>%6.4g - %6.4g</td></tr>\n" % (
            theta,
            dangle,
            dangle0,
            sangle,
            dirpix,
            lambda_min,
            lambda_max,
        )
        meta += "</table>\n<p>\n"
        return meta

    def generate_script(self, workspace) -> str:
        r"""Generate a Mantid script for the reflectivity reduction by retrieving the history of the workspace.

        The history of a workspace is nothing but the sequence of calls to different Mantid algorithms

        Parameters
        ----------
        workspace: mantid.api.Workspace
            Mantid workspace resulting of running algoritm MagnetismReflectometryReduction (among others)

        Returns
        -------
        str
            the sequence of Mantid algorithms calls as one would write them in a Python script
        """
        if workspace is None:
            return ""
        cross_section = SampleLogs(workspace)["cross_section_id"]
        script = "# Run:%s    Cross-section: %s\n" % (self.data_info.run_number, cross_section)
        if workspace is not None:
            script_text = GeneratePythonScript(workspace)
            script += script_text.replace(", ", ",\n                                ")
        else:
            script += "#   No data in this cross-section"
        script += "\n"
        return script

    def generate_plots(self, workspace):
        """
        Generate diagnostics plots
        """
        self.log("  - generating plots [%s]" % self.number_events)
        cross_section = SampleLogs(workspace)["cross_section_id"]
        if self.number_events < 10:
            logger.notice("No events for workspace %s" % str(workspace))
            return []

        n_x = int(workspace.getInstrument().getNumberParameter("number-of-x-pixels")[0])
        n_y = int(workspace.getInstrument().getNumberParameter("number-of-y-pixels")[0])

        scatt_peak = self.data_info.peak_range
        scatt_low_res = self.data_info.low_res_range

        # X-Y plot
        xy_plot = None
        try:
            integrated = Integration(workspace)
            signal = np.log10(integrated.extractY())
            z = np.reshape(signal, (n_x, n_y))
            xy_plot = _plot2d(
                z=z.T,
                x=list(range(n_x)),
                y=list(range(n_y)),
                x_range=scatt_peak,
                y_range=scatt_low_res,
                x_bck_range=self.data_info.background,
                title="r%s [%s]" % (self.data_info.run_number, cross_section),
            )
        except:  # noqa E722
            self.log("  - Could not generate XY plot")
            xy_plot = _plotText("Could not generate XY plot", "r%s [%s]" % (self.data_info.run_number, cross_section))

        self.log("  - generating X-TOF plot")
        # X-TOF plot
        x_tof_plot = None
        try:
            tof_min = workspace.getTofMin()
            tof_max = workspace.getTofMax()
            workspace = Rebin(workspace, params="%s, 50, %s" % (tof_min, tof_max))
            # algorithm RefRoi sums up the intensities in a region of interest on a 2D detector
            # returns a MatrixWorkspace
            direct_summed = RefRoi(
                InputWorkspace=workspace,
                IntegrateY=True,
                NXPixel=n_x,
                NYPixel=n_y,
                ConvertToQ=False,
                YPixelMin=0,
                YPixelMax=n_y,
                OutputWorkspace="direct_summed",
            )
            signal = np.transpose(np.log10(direct_summed.extractY()))
            tof_axis = direct_summed.extractX()[0] / 1000.0
            tof_axis = (tof_axis[:-1] + tof_axis[1:]) / 2.0  # average TOF values

            x_tof_plot = _plot2d(
                z=signal,
                y=tof_axis,
                x=list(range(signal.shape[1])),
                x_range=scatt_peak,
                x_bck_range=self.data_info.background,
                y_range=None,
                x_label="X pixel",
                y_label="TOF (ms)",
                title="r%s [%s]" % (self.data_info.run_number, cross_section),
                swap_axes=False,
            )
        except:  # noqa E722
            self.log("  - Could not generate X-TOF plot")
            x_tof_plot = _plotText(
                "Could not generate X-TOF plot", "r%s [%s]" % (self.data_info.run_number, cross_section)
            )

        self.log("  - generating X count distribution")
        # Count per X pixel
        peak_pixels = None
        try:
            integrated = Integration(direct_summed)
            integrated = Transpose(integrated)
            signal_y = integrated.readY(0)
            signal_x = list(range(len(signal_y)))
            peak_pixels = _plot1d(
                signal_x,
                signal_y,
                x_range=scatt_peak,
                bck_range=self.data_info.background,
                x_label="X pixel",
                y_label="Counts",
                title="r%s [%s]" % (self.data_info.run_number, cross_section),
            )
        except:  # noqa E722
            self.log("  - Could not generate X count distribution")
            peak_pixels = _plotText(
                "Could not generate X count distribution", "r%s [%s]" % (self.data_info.run_number, cross_section)
            )

        self.log("  - generating Y count distribution")
        # Count per Y pixel
        low_res_profile = None
        try:
            direct_summed = RefRoi(
                InputWorkspace=workspace,
                IntegrateY=False,
                NXPixel=n_x,
                NYPixel=n_y,
                ConvertToQ=False,
                OutputWorkspace="direct_summed",
            )
            integrated = Integration(direct_summed)
            integrated = Transpose(integrated)
            signal_x = integrated.readY(0)
            signal_y = np.arange(len(signal_x))
            low_res_profile = _plot1d(
                signal_x,
                signal_y,
                x_log=True,
                y_log=False,
                y_range=scatt_low_res,
                x_label="Counts",
                y_label="Y pixel",
                title="r%s [%s]" % (self.data_info.run_number, cross_section),
            )
        except:  # noqa E722
            self.log("  - Could not generate Y count distribution")
            low_res_profile = _plotText(
                "Could not generate Y count distribution", "r%s [%s]" % (self.data_info.run_number, cross_section)
            )

        # TOF distribution
        tof_dist = None
        try:
            workspace = SumSpectra(workspace)
            signal_x = workspace.readX(0) / 1000.0
            signal_y = workspace.readY(0)
            tof_dist = _plot1d(
                signal_x,
                signal_y,
                x_range=None,
                x_label="TOF (ms)",
                y_label="Counts",
                title="r%s [%s]" % (self.data_info.run_number, cross_section),
            )
        except:  # noqa E722
            self.log("  - Could not generate TOF distribution")
            tof_dist = _plotText(
                "Could not generate TOF distribution", "r%s [%s]" % (self.data_info.run_number, cross_section)
            )

        return [xy_plot, x_tof_plot, peak_pixels, low_res_profile, tof_dist]


def _plot2d(
    x,
    y,
    z,
    x_range=None,
    y_range=None,
    x_label="X pixel",
    y_label="Y pixel",
    title="",
    x_bck_range=None,
    y_bck_range=None,
    swap_axes=False,
):
    """
    Generate a 2D plot
    :param array x: x-axis values
    :param array y: y-axis values
    :param array z: z-axis counts
    :param str x_label: x-axis label
    :param str y_label: y-axis label
    :param str title: plot title
    :param array x_bck_range: array of length 2 to specify a background region in x
    :param array y_bck_range: array of length 2 to specify a background region in y
    """
    colorscale = [
        [0, "rgb(0,0,131)"],
        [0.125, "rgb(0,60,170)"],
        [0.375, "rgb(5,255,255)"],
        [0.625, "rgb(255,255,0)"],
        [0.875, "rgb(250,0,0)"],
        [1, "rgb(128,0,0)"],
    ]

    if swap_axes:
        x, y = y, x
        z = z.T
        x_range, y_range = y_range, x_range
        x_bck_range, y_bck_range = y_bck_range, x_bck_range
        x_label, y_label = y_label, x_label

    # Eliminate items in array Z that are not finite and below a certain threshold
    x_grid, y_grid = np.meshgrid(x, y)
    x_flat, y_flat, z_flat = x_grid.flatten(), y_grid.flatten(), z.flatten()
    threshold = 0.01 * np.max(z_flat)
    mask = np.isfinite(z_flat) & (z_flat > threshold)  # Keep only significant values (exclude NaN, -inf, inf)
    x_sparse, y_sparse, z_sparse = x_flat[mask], y_flat[mask], z_flat[mask]

    # Round the remaining values to a certain number of decimal places, for instance 0.003455245 to 0.0034.
    # This will later save disk space when writing the figure to file
    def leading_decimal_places(x: float):
        """Calculate the number of leading decimal places for a number between 0 and 1."""
        if x <= 0 or x >= 1:
            raise ValueError("x must be between 0 and 1")
        return abs(math.floor(math.log10(x)))

    z_sparse = np.round(z_sparse, 1 + leading_decimal_places(threshold))

    heatmap = go.Heatmap(
        x=x_sparse,
        y=y_sparse,
        z=z_sparse,
        autocolorscale=False,
        type="heatmap",
        showscale=False,
        hoverinfo="x+y+z",
        colorscale=colorscale,
    )

    x_range_color = "rgba(152, 0, 0, .8)"
    y_range_color = "rgba(0, 128, 0, 1)"
    if swap_axes:
        x_range_color = "rgba(0, 128, 0, 1)"
        y_range_color = "rgba(152, 0, 0, .8)"

    # Set the color scale limits
    data = [heatmap]
    if x_range is not None:
        x_left = go.Scatter(
            name="",
            x=[x_range[0], x_range[0]],
            y=[min(y), max(y)],
            marker=dict(
                color=x_range_color,
            ),
        )
        x_right = go.Scatter(
            name="",
            x=[x_range[1], x_range[1]],
            y=[min(y), max(y)],
            marker=dict(
                color=x_range_color,
            ),
        )
        data.append(x_left)
        data.append(x_right)

    if x_bck_range is not None:
        x_left = go.Scatter(
            name="",
            x=[x_bck_range[0], x_bck_range[0]],
            y=[min(y), max(y)],
            marker=dict(
                color="rgba(152, 152, 152, .8)",
            ),
        )
        x_right = go.Scatter(
            name="",
            x=[x_bck_range[1], x_bck_range[1]],
            y=[min(y), max(y)],
            marker=dict(
                color="rgba(152, 152, 152, .8)",
            ),
        )
        data.append(x_left)
        data.append(x_right)

    if y_range is not None:
        y_left = go.Scatter(
            name="",
            y=[y_range[0], y_range[0]],
            x=[min(x), max(x)],
            marker=dict(
                color=y_range_color,
            ),
        )
        y_right = go.Scatter(
            name="",
            y=[y_range[1], y_range[1]],
            x=[min(x), max(x)],
            marker=dict(
                color=y_range_color,
            ),
        )
        data.append(y_left)
        data.append(y_right)

    if y_bck_range is not None:
        y_left = go.Scatter(
            name="",
            y=[y_bck_range[0], y_bck_range[0]],
            x=[min(x), max(x)],
            marker=dict(
                color="rgba(152, 152, 152, .8)",
            ),
        )
        y_right = go.Scatter(
            name="",
            y=[y_bck_range[1], y_bck_range[1]],
            x=[min(x), max(x)],
            marker=dict(
                color="rgba(152, 152, 152, .8)",
            ),
        )
        data.append(y_left)
        data.append(y_right)

    x_layout = dict(
        title=x_label,
        zeroline=False,
        exponentformat="power",
        showexponent="all",
        showgrid=True,
        showline=True,
        mirror="all",
        ticks="inside",
    )
    y_layout = dict(
        title=y_label,
        zeroline=False,
        exponentformat="power",
        showexponent="all",
        showgrid=True,
        showline=True,
        mirror="all",
        ticks="inside",
    )
    layout = go.Layout(
        title=title,
        showlegend=False,
        autosize=True,
        width=300,
        height=300,
        margin=dict(t=40, b=40, l=40, r=20),
        hovermode="closest",
        bargap=0,
        xaxis=x_layout,
        yaxis=y_layout,
    )
    fig = go.Figure(data=data, layout=layout)
    return pyo.plot(fig, output_type="div", include_plotlyjs=False, show_link=False)


def _plot1d(
    x, y, x_range=None, y_range=None, x_label="", y_label="Counts", title="", bck_range=None, x_log=False, y_log=True
) -> str:
    r"""Generate a simple 1D plot as an HTML snippet containing a Plotly graph embedded within a web page

    Parameters
    ----------
    x: np.ndarray
        x-axis values
    y: np.ndarray
    x_label: str
        x-axis label
    y_label: str
        y-axis label
    title: str
        plot title
    bck_range: np.ndarray, list
        array of length 2 to specify a background region in x
    x_log: bool
        if true, the x-axis will be a log scale
    y_log: bool
        if true, the y-axis will be a log scale

    Returns
    -------
    str
    """
    data = [go.Scatter(name="", x=x, y=y)]

    if x_range is not None:
        min_y = min([v for v in y if v > 0])
        x_left = go.Scatter(
            name="",
            x=[x_range[0], x_range[0]],
            y=[min_y, max(y)],
            marker=dict(
                color="rgba(152, 0, 0, .8)",
            ),
        )
        x_right = go.Scatter(
            name="",
            x=[x_range[1], x_range[1]],
            y=[min_y, max(y)],
            marker=dict(
                color="rgba(152, 0, 0, .8)",
            ),
        )
        data.append(x_left)
        data.append(x_right)

    if y_range is not None:
        min_x = min([v for v in x if v > 0])
        y_left = go.Scatter(
            name="",
            y=[y_range[0], y_range[0]],
            x=[min_x, max(x)],
            marker=dict(
                color="rgba(0, 128, 0, 1)",
            ),
        )
        y_right = go.Scatter(
            name="",
            y=[y_range[1], y_range[1]],
            x=[min_x, max(x)],
            marker=dict(
                color="rgba(0, 128, 0, 1)",
            ),
        )
        data.append(y_left)
        data.append(y_right)

    if bck_range is not None:
        min_y = min([v for v in y if v > 0])
        x_left = go.Scatter(
            name="",
            x=[bck_range[0], bck_range[0]],
            y=[min_y, max(y)],
            marker=dict(
                color="rgba(152, 152, 152, .8)",
            ),
        )
        x_right = go.Scatter(
            name="",
            x=[bck_range[1], bck_range[1]],
            y=[min_y, max(y)],
            marker=dict(
                color="rgba(152, 152, 152, .8)",
            ),
        )
        data.append(x_left)
        data.append(x_right)

    x_layout = dict(
        title=x_label,
        zeroline=False,
        exponentformat="power",
        showexponent="all",
        showgrid=True,
        showline=True,
        mirror="all",
        ticks="inside",
    )
    if x_log:
        x_layout["type"] = "log"

    y_layout = dict(
        title=y_label,
        zeroline=False,
        exponentformat="power",
        showexponent="all",
        showgrid=True,
        showline=True,
        mirror="all",
        ticks="inside",
    )
    if y_log:
        y_layout["type"] = "log"

    layout = go.Layout(
        title=title,
        showlegend=False,
        autosize=True,
        width=300,
        height=300,
        margin=dict(t=40, b=40, l=40, r=20),
        hovermode="closest",
        bargap=0,
        xaxis=x_layout,
        yaxis=y_layout,
    )

    fig = go.Figure(data=data, layout=layout)
    return pyo.plot(fig, output_type="div", include_plotlyjs=False, show_link=False)


def plot1d(
    run_number,  # noqa ARG001
    data_list,
    data_names=None,
    x_title="",
    y_title="",
    x_log=False,
    y_log=False,
    instrument="",  # noqa ARG001
    show_dx=True,
    title="",
    publish=False,  # noqa ARG001
):
    r"""
    Produce a 1D plot in the style of the autoreduction output.
    The function signature is meant to match the autoreduction publisher.
    @param data_list: list of traces [ [x1, y1], [x2, y2], ...]
    @param data_names: name for each trace, for the legend

    Arguments run_number, instrument, and publish are unused because this function is not meant to upload
    anything to the livedata server.
    """
    # Create traces
    if not isinstance(data_list, list):
        raise RuntimeError("plot1d: data_list parameter is expected to be a list")

    # Catch the case where the list is in the format [x y]
    data = []
    show_legend = False
    if len(data_list) == 2 and not isinstance(data_list[0], list):
        label = ""
        if isinstance(data_names, list) and len(data_names) == 1:
            label = data_names[0]
            show_legend = True
        data = [go.Scatter(name=label, x=data_list[0], y=data_list[1])]
    else:
        for i in range(len(data_list)):
            label = ""
            if isinstance(data_names, list) and len(data_names) == len(data_list):
                label = data_names[i]
                show_legend = True
            err_x = {}
            err_y = {}
            if len(data_list[i]) >= 3:
                err_y = dict(type="data", array=data_list[i][2], visible=True)
            if len(data_list[i]) >= 4:
                err_x = dict(type="data", array=data_list[i][3], visible=True)
                if show_dx is False:
                    err_x["thickness"] = 0
            data.append(go.Scatter(name=label, x=data_list[i][0], y=data_list[i][1], error_x=err_x, error_y=err_y))

    x_layout = dict(
        title=x_title,
        zeroline=False,
        exponentformat="power",
        showexponent="all",
        showgrid=True,
        showline=True,
        mirror="all",
        ticks="inside",
    )
    if x_log:
        x_layout["type"] = "log"
    y_layout = dict(
        title=y_title,
        zeroline=False,
        exponentformat="power",
        showexponent="all",
        showgrid=True,
        showline=True,
        mirror="all",
        ticks="inside",
    )
    if y_log:
        y_layout["type"] = "log"

    layout = go.Layout(
        showlegend=show_legend,
        autosize=True,
        width=600,
        height=400,
        margin=dict(t=40, b=40, l=80, r=40),
        hovermode="closest",
        bargap=0,
        xaxis=x_layout,
        yaxis=y_layout,
        title=title,
    )

    fig = go.Figure(data=data, layout=layout)
    plot_div = pyo.plot(fig, output_type="div", include_plotlyjs=False, show_link=False)
    return plot_div


def _plotText(text, title=""):
    r"""
    Displays an informative message as a plot

    :param: text: str, the text to be displayed
    :param: title: str, the title of the plot
    :return: py.plot, the plot
    """

    layout = go.Layout(
        annotations=[
            dict(
                text=text,
                font=dict(size=13, color="red"),
                xref="paper",  # `paper` sets relative coordinates
                yref="paper",
                align="center",
                x=0.5,
                y=0.5,
                showarrow=False,
            )
        ],
        autosize=True,
        title=title,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        showlegend=False,
    )

    fig = go.Figure(layout=layout)
    plot = pyo.plot(fig, output_type="div", include_plotlyjs=False, show_link=False)

    return plot
