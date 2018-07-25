#pylint: disable=bare-except,dangerous-default-value, too-many-instance-attributes, too-many-arguments
"""
    Report class sed to populate the web monitor
"""
from __future__ import (absolute_import, division, print_function)
import sys
import time
import numpy as np

import plotly.offline as py
import plotly.graph_objs as go

from mantid.simpleapi import *


def process_collection(summary_content=None, report_list=[], publish=True, run_number=None):
    """
        Process a collection of reports into on final report
        :param str summary_content: html content at the top of the report
        :param list report_list: list of html contents to be appended at the bottom of the page
        :param bool publish: if True, the report will be sent to the live data server
        :param int run_number: run number to associate this report with
    """
    plot_html = ''
    script = ''

    if summary_content is not None:
        plot_html += "<div>%s</div>\n" % summary_content

    for report in report_list:
        script += report.script
        plot_html += "<div>%s</div>\n" % report.report
        plot_html += "<table style='width:100%'>\n"
        plot_html += "<tr>\n"
        for plot in report.plots:
            if plot is not None:
                plot_html += "<td>%s</td>\n" % plot
        plot_html += "</tr>\n"
        plot_html += "</table>\n"
        plot_html += "<hr>\n"

    # Send to the web monitor as needed
    if run_number is None and report_list:
        run_number = report_list[0].data_info.run_number
    if publish:
        # Depending on where we run, we might get our publisher from
        # different places, or not at all.
        _publisher_found = False
        try: # version on autoreduce
            from postprocessing.publish_plot import publish_plot
            _publisher_found = True
        except ImportError: # version on instrument computers
            from finddata import publish_plot
            _publisher_found = True
        if _publisher_found:
            publish_plot("REF_M", run_number, files={'file': plot_html})
        else:
            logger.error("Could not publish web report: %s" % sys.exc_value)

    return plot_html, script


class Report(object):
    """
        Take the output of the reduction and generate
        diagnostics plots, and a block of meta data.
    """
    def __init__(self, workspace, data_info, direct_info, reflectivity_ws, force_plot=True, logfile=None):
        """
            :param bool force_plot: if True, a report will be generated regardless of whether there is enough data
        """
        self.data_info = data_info
        self.direct_info = direct_info
        self.logfile = logfile
        try:
            self.cross_section = workspace.getRun().getProperty("cross_section_id").value
            self.number_events = workspace.getNumberEvents()
        except:
            self.number_events = 0
            self.cross_section = ''
        self.has_reflectivity = reflectivity_ws is not None
        self.plots = []
        self.script = ''
        self.report = ''
        if force_plot or self.data_info.data_type >= 0:
            self.log("  - writing script [%s %s %s]" % (self.cross_section,
                                                        self.number_events,
                                                        self.has_reflectivity))
            self.script = self.generate_script(reflectivity_ws)
            self.report = self.generate_web_report(reflectivity_ws)
            try:
                self.plots = self.generate_plots(workspace)
            except:
                self.log("Could not generate plots: %s" % sys.exc_info()[0])
                logger.error("Could not generate plots: %s" % sys.exc_info()[0])
        else:
            logger.error("Invalid data type for report: %s" % self.data_info.data_type)

        self.log("  - report: %s %s" % (len(self.report), len(self.plots)))

    def log(self, msg):
        """ Log a message """
        if self.logfile is not None:
            self.logfile.write(msg+'\n')

    def generate_web_report(self, workspace):
        """
            Generate HTML report
        """
        if workspace is None:
            meta = "<p>\n<table style='width:80%'>"
            meta += "<tr><td>Run:</td><td><b>%s</b> [%s] (direct beam: %s)</td></td></tr>" % (self.data_info.run_number,
                                                                                              self.cross_section,
                                                                                              self.data_info.is_direct_beam)
            if not self.data_info.run_number == self.direct_info.run_number:
                meta += "<tr><td>Assigned direct beam:</td><td>%s</td></tr>" % self.direct_info.run_number
            meta += "<tr><td># events:</td><td>%s</td></tr>" % self.number_events
            meta += "<tr><td>Using ROI:</td><td>req=%s, actual=%s</td></tr>" % (self.data_info.use_roi, self.data_info.use_roi_actual)
            meta += "<tr><td>Peak range:</td><td>%s - %s</td></td></tr>" % (self.data_info.peak_range[0], self.data_info.peak_range[1])
            meta += "<tr><td>Background:</td><td>%s - %s</td></tr>" % (self.data_info.background[0], self.data_info.background[1])
            meta += "<tr><td>Low-res range:</td><td>%s - %s</td></tr>" % (self.data_info.low_res_range[0], self.data_info.low_res_range[1])
            meta += "<tr><td>ROI peak:</td><td>%s - %s</td></tr>" % (self.data_info.roi_peak[0], self.data_info.roi_peak[1])
            meta += "<tr><td>ROI bck:</td><td>%s - %s</td></tr>" % (self.data_info.roi_background[0], self.data_info.roi_background[1])
            meta += "<tr><td>Sequence:</td><td>%s: %s/%s</td></tr>" % (self.data_info.sequence_id,
                                                                       self.data_info.sequence_number,
                                                                       self.data_info.sequence_total)
            meta += "</table>\n<p>\n"
            return meta

        run_object = workspace.getRun()
        constant_q_binning = run_object['constant_q_binning'].value
        sangle = run_object['SANGLE'].getStatistics().mean
        dangle = run_object['DANGLE'].getStatistics().mean
        lambda_min = run_object['lambda_min'].value
        lambda_max = run_object['lambda_max'].value
        theta = run_object['two_theta'].value / 2
        direct_beam = run_object["normalization_run"].value

        dangle0 = run_object['DANGLE0'].getStatistics().mean
        dirpix = run_object['DIRPIX'].getStatistics().mean
        p_charge = run_object['gd_prtn_chrg'].value

        meta = "<p>\n<table style='width:80%'>"
        meta += "<tr><td>Run:</td><td><b>%s</b> [%s]</td></td><td><b>Direct beam: %s</b></td></tr>" % (int(run_object['run_number'].value),
                                                                                                       self.cross_section, direct_beam)
        meta += "<tr><td># events:</td><td>%s</td></tr>" % self.number_events
        meta += "<tr><td>Q-binning:</td><td>%s</td><td>-</td></tr>" % constant_q_binning
        meta += "<tr><td>Using ROI:</td><td>req=%s, actual=%s</td><td>req=%s, actual=%s</td></tr>" % (self.data_info.use_roi, self.data_info.use_roi_actual,
                                                                                                      self.direct_info.use_roi, self.direct_info.use_roi_actual)
        meta += "<tr><td>Specular peak:</td><td>%g</td><td>%g</td></tr>" % (self.data_info.peak_position, self.direct_info.peak_position)
        meta += "<tr><td>Peak range:</td><td>%s - %s</td></td><td>%s - %s</td></tr>" % (self.data_info.peak_range[0], self.data_info.peak_range[1],
                                                                                        self.direct_info.peak_range[0], self.direct_info.peak_range[1])
        meta += "<tr><td>Background:</td><td>%s - %s</td><td>%s - %s</td></tr>" % (self.data_info.background[0], self.data_info.background[1],
                                                                                   self.direct_info.background[0], self.direct_info.background[1])
        meta += "<tr><td>Low-res range:</td><td>%s - %s</td><td>%s - %s</td></tr>" % (self.data_info.low_res_range[0], self.data_info.low_res_range[1],
                                                                                      self.direct_info.low_res_range[0], self.direct_info.low_res_range[1])
        meta += "<tr><td>ROI peak:</td><td>%s - %s</td><td>%s - %s</td></tr>" % (self.data_info.roi_peak[0], self.data_info.roi_peak[1],
                                                                                 self.direct_info.roi_peak[0], self.direct_info.roi_peak[1])
        meta += "<tr><td>ROI bck:</td><td>%s - %s</td><td>%s - %s</td></tr>" % (self.data_info.roi_background[0], self.data_info.roi_background[1],
                                                                                self.direct_info.roi_background[0], self.direct_info.roi_background[1])
        meta += "<tr><td>Sequence:</td><td>%s: %s/%s</td></tr>" % (self.data_info.sequence_id,
                                                                   self.data_info.sequence_number,
                                                                   self.data_info.sequence_total)
        meta += "<tr><td>Report time:</td><td>%s</td></tr>" % time.ctime()
        meta += "</table>\n"

        meta += "<p><table style='width:100%'>"
        meta += "<tr><th>Theta (actual)</th><th>DANGLE [DANGLE0]</th><th>SANGLE</th><th>DIRPIX</th><th>Wavelength</th><th>p-charge [uAh]</th></tr>"
        meta += "<tr><td>%6.4g</td><td>%6.4g [%6.4g]</td><td>%6.4g</td><td>%6.4g</td><td>%6.4g - %6.4g</td><td>%6.4g</td></tr>\n" % (theta, dangle, dangle0,
                                                                                                                                     sangle, dirpix, lambda_min,
                                                                                                                                     lambda_max, p_charge)
        meta += "</table>\n<p>\n"
        return meta

    def generate_script(self, workspace):
        """
            Generate a Mantid script for the reflectivity reduction
        """
        if workspace is None:
            return ''
        cross_section = workspace.getRun().getProperty("cross_section_id").value
        script = '# Run:%s    Cross-section: %s\n' % (self.data_info.run_number, cross_section)
        if workspace is not None:
            script_text = GeneratePythonScript(workspace)
            script += script_text.replace(', ',',\n                                ')
        else:
            script += "#   No data in this cross-section"
        script += '\n'
        return script

    def generate_plots(self, workspace):
        """
            Generate diagnostics plots
        """
        self.log("  - generating plots [%s]" % self.number_events)
        cross_section = workspace.getRun().getProperty("cross_section_id").value
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
            #integrated = Integration(workspace)
            signal = np.log10(workspace.extractY())
            z=np.reshape(signal, (n_x, n_y))
            xy_plot = _plot2d(z=z.T, x=range(n_x), y=range(n_y),
                              x_range=scatt_peak, y_range=scatt_low_res, x_bck_range=self.data_info.background,
                              title="r%s [%s]" % (self.data_info.run_number, cross_section))
        except:
            self.log("  - Could not generate XY plot")

        self.log("  - generating X-TOF plot")
        # X-TOF plot
        x_tof_plot = None
        try:
            tof_min = workspace.getTofMin()
            tof_max = workspace.getTofMax()
            workspace = Rebin(workspace, params="%s, 50, %s" % (tof_min, tof_max))
    
            direct_summed = RefRoi(InputWorkspace=workspace, IntegrateY=True,
                                   NXPixel=n_x, NYPixel=n_y,
                                   ConvertToQ=False, YPixelMin=0, YPixelMax=n_y,
                                   OutputWorkspace="direct_summed")
            signal = np.log10(direct_summed.extractY())
            tof_axis = direct_summed.extractX()[0]/1000.0
    
            x_tof_plot = _plot2d(z=signal, y=range(signal.shape[0]), x=tof_axis,
                                 x_range=None, y_range=scatt_peak, y_bck_range=self.data_info.background,
                                 x_label="TOF (ms)", y_label="X pixel",
                                 title="r%s [%s]" % (self.data_info.run_number, cross_section))
        except:
            self.log("  - Could not generate X-TOF plot")

        self.log("  - generating X count distribution")
        # Count per X pixel
        peak_pixels = None
        try:
            integrated = Integration(direct_summed)
            integrated = Transpose(integrated)
            signal_y = integrated.readY(0)
            signal_x = range(len(signal_y))
            peak_pixels = _plot1d(signal_x,signal_y, x_range=scatt_peak, bck_range=self.data_info.background,
                                  x_label="X pixel", y_label="Counts",
                                  title="r%s [%s]" % (self.data_info.run_number, cross_section))
        except:
            self.log("  - Could not generate X count distribution")

        # TOF distribution
        tof_dist = None
        try:
            workspace = SumSpectra(workspace)
            signal_x = workspace.readX(0)/1000.0
            signal_y = workspace.readY(0)
            tof_dist = _plot1d(signal_x,signal_y, x_range=None,
                               x_label="TOF (ms)", y_label="Counts",
                               title="r%s [%s]" % (self.data_info.run_number, cross_section))
        except:
            self.log("  - Could not generate TOF distribution")

        return [xy_plot, x_tof_plot, peak_pixels, tof_dist]

def _plot2d(x, y, z, x_range=None, y_range=None, x_label="X pixel", y_label="Y pixel", title='', x_bck_range=None, y_bck_range=None):
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
    colorscale=[[0, "rgb(0,0,131)"], [0.125, "rgb(0,60,170)"], [0.375, "rgb(5,255,255)"],
                [0.625, "rgb(255,255,0)"], [0.875, "rgb(250,0,0)"], [1, "rgb(128,0,0)"]]

    heatmap = go.Heatmap(x=x, y=y, z=z, autocolorscale=False, type='heatmap', showscale=False,
                         hoverinfo="x+y+z", colorscale=colorscale)

    data = [heatmap]
    if x_range is not None:
        x_left=go.Scatter(name='', x=[x_range[0], x_range[0]], y=[min(y), max(y)],
                          marker = dict(color = 'rgba(152, 0, 0, .8)',))
        x_right=go.Scatter(name='', x=[x_range[1], x_range[1]], y=[min(y), max(y)],
                           marker = dict(color = 'rgba(152, 0, 0, .8)',))
        data.append(x_left)
        data.append(x_right)

    if x_bck_range is not None:
        x_left=go.Scatter(name='', x=[x_bck_range[0], x_bck_range[0]], y=[min(y), max(y)],
                          marker = dict(color = 'rgba(152, 152, 152, .8)',))
        x_right=go.Scatter(name='', x=[x_bck_range[1], x_bck_range[1]], y=[min(y), max(y)],
                           marker = dict(color = 'rgba(152, 152, 152, .8)',))
        data.append(x_left)
        data.append(x_right)

    if y_range is not None:
        y_left=go.Scatter(name='', y=[y_range[0], y_range[0]], x=[min(x), max(x)],
                          marker = dict(color = 'rgba(152, 0, 0, .8)',))
        y_right=go.Scatter(name='', y=[y_range[1], y_range[1]], x=[min(x), max(x)],
                           marker = dict(color = 'rgba(152, 0, 0, .8)',))
        data.append(y_left)
        data.append(y_right)

    if y_bck_range is not None:
        y_left=go.Scatter(name='', y=[y_bck_range[0], y_bck_range[0]], x=[min(x), max(x)],
                          marker = dict(color = 'rgba(152, 152, 152, .8)',))
        y_right=go.Scatter(name='', y=[y_bck_range[1], y_bck_range[1]], x=[min(x), max(x)],
                           marker = dict(color = 'rgba(152, 152, 152, .8)',))
        data.append(y_left)
        data.append(y_right)

    x_layout = dict(title=x_label, zeroline=False, exponentformat="power",
                    showexponent="all", showgrid=True,
                    showline=True, mirror="all", ticks="inside")
    y_layout = dict(title=y_label, zeroline=False, exponentformat="power",
                    showexponent="all", showgrid=True,
                    showline=True, mirror="all", ticks="inside")
    layout = go.Layout(
        title=title,
        showlegend=False,
        autosize=True,
        width=300,
        height=300,
        margin=dict(t=40, b=40, l=40, r=20),
        hovermode='closest',
        bargap=0,
        xaxis=x_layout,
        yaxis=y_layout
    )
    fig = go.Figure(data=data, layout=layout)
    return py.plot(fig, output_type='div', include_plotlyjs=False, show_link=False)

def _plot1d(x, y, x_range=None, x_label='', y_label="Counts", title='', bck_range=None):
    """
        Generate a simple 1D plot
        :param array x: x-axis values
        :param array y: y-axis values
        :param str x_label: x-axis label
        :param str y_label: y-axis label
        :param str title: plot title
        :param array bck_range: array of length 2 to specify a background region in x
    """
    data = [go.Scatter(name='', x=x, y=y)]

    if x_range is not None:
        min_y = min([v for v in y if v>0])
        x_left=go.Scatter(name='', x=[x_range[0], x_range[0]], y=[min_y, max(y)],
                          marker = dict(color = 'rgba(152, 0, 0, .8)',))
        x_right=go.Scatter(name='', x=[x_range[1], x_range[1]], y=[min_y, max(y)],
                           marker = dict(color = 'rgba(152, 0, 0, .8)',))
        data.append(x_left)
        data.append(x_right)

    if bck_range is not None:
        min_y = min([v for v in y if v>0])
        x_left=go.Scatter(name='', x=[bck_range[0], bck_range[0]], y=[min_y, max(y)],
                          marker = dict(color = 'rgba(152, 152, 152, .8)',))
        x_right=go.Scatter(name='', x=[bck_range[1], bck_range[1]], y=[min_y, max(y)],
                           marker = dict(color = 'rgba(152, 152, 152, .8)',))
        data.append(x_left)
        data.append(x_right)

    x_layout = dict(title=x_label, zeroline=False, exponentformat="power",
                    showexponent="all", showgrid=True,
                    showline=True, mirror="all", ticks="inside")

    y_layout = dict(title=y_label, zeroline=False, exponentformat="power",
                    showexponent="all", showgrid=True, type='log',
                    showline=True, mirror="all", ticks="inside")

    layout = go.Layout(
        title=title,
        showlegend=False,
        autosize=True,
        width=300,
        height=300,
        margin=dict(t=40, b=40, l=40, r=20),
        hovermode='closest',
        bargap=0,
        xaxis=x_layout,
        yaxis=y_layout
    )

    fig = go.Figure(data=data, layout=layout)
    return py.plot(fig, output_type='div', include_plotlyjs=False, show_link=False)

def plot1d(run_number, data_list, data_names=None, x_title='', y_title='',
           x_log=False, y_log=False, instrument='', show_dx=True, title = '', publish=True):
    """
        Produce a 1D plot in the style of the autoreduction output.
        The function signature is meant to match the autoreduction publisher.
        @param data_list: list of traces [ [x1, y1], [x2, y2], ...]
        @param data_names: name for each trace, for the legend
    """
    # Create traces
    if not isinstance(data_list, list):
        raise RuntimeError("plot1d: data_list parameter is expected to be a list")

    # Catch the case where the list is in the format [x y]
    data = []
    show_legend = False
    if len(data_list) == 2 and not isinstance(data_list[0], list):
        label = ''
        if isinstance(data_names, list) and len(data_names) == 1:
            label = data_names[0]
            show_legend = True
        data = [go.Scatter(name=label, x=data_list[0], y=data_list[1])]
    else:
        for i in range(len(data_list)):
            label = ''
            if isinstance(data_names, list) and len(data_names) == len(data_list):
                label = data_names[i]
                show_legend = True
            err_x = {}
            err_y = {}
            if len(data_list[i]) >= 3:
                err_y = dict(type='data', array=data_list[i][2], visible=True)
            if len(data_list[i]) >= 4:
                err_x = dict(type='data', array=data_list[i][3], visible=True)
                if show_dx is False:
                    err_x['thickness'] = 0
            data.append(go.Scatter(name=label, x=data_list[i][0], y=data_list[i][1],
                                   error_x=err_x, error_y=err_y))

    x_layout = dict(title=x_title, zeroline=False, exponentformat="power",
                    showexponent="all", showgrid=True,
                    showline=True, mirror="all", ticks="inside")
    if x_log:
        x_layout['type'] = 'log'
    y_layout = dict(title=y_title, zeroline=False, exponentformat="power",
                    showexponent="all", showgrid=True,
                    showline=True, mirror="all", ticks="inside")
    if y_log:
        y_layout['type'] = 'log'

    layout = go.Layout(
        showlegend=show_legend,
        autosize=True,
        width=600,
        height=400,
        margin=dict(t=40, b=40, l=80, r=40),
        hovermode='closest',
        bargap=0,
        xaxis=x_layout,
        yaxis=y_layout,
        title=title
    )

    fig = go.Figure(data=data, layout=layout)
    plot_div = py.plot(fig, output_type='div', include_plotlyjs=False, show_link=False)
    return plot_div