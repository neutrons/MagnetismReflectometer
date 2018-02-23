#pylint: disable=bare-except,dangerous-default-value
"""
    Report class sed to populate the web monitor
"""
from __future__ import (absolute_import, division, print_function)
import sys
sys.path.insert(0,'/opt/mantidnightly/bin')
import mantid
from mantid.simpleapi import *
import numpy as np
import logging
import plotly.offline as py
import plotly.graph_objs as go


def process_collection(summary_content=None, report_list=[], publish=True, run_number=None):
    """
        Process a collection of reports into on final report
    """
    plot_html = ''
    script = ''

    if summary_content is not None:
        plot_html += "<div>%s</div>\n" % summary_content

    for r in report_list:
        script += r.script
        plot_html += "<div>%s</div>\n" % r.report
        plot_html += "<table style='width:100%'>\n"
        plot_html += "<tr>\n"
        for p in r.plots:
            plot_html += "<td>%s</td>\n" % p
        plot_html += "</tr>\n"
        plot_html += "</table>\n"

    # Send to the web monitor as needed
    if run_number is None and len(report_list)>0:
        run_number = report_list[0].data_info.run_number
    if publish:
        try:
            from postprocessing.publish_plot import publish_plot
            publish_plot("REF_M", run_number, files={'file': plot_html})
        except:
            logging.error("Could not publish web report: %s", sys.exc_value)

    return plot_html, script


class Report(object):
    """
        Take the output of the reduction and generate 
        diagnostics plots, and a block of meta data.
            
    """
    def __init__(self, ws, data_info, direct_info, reflectivity_ws):
        self.data_info = data_info
        self.direct_info = direct_info
        self.has_reflectivity = reflectivity_ws is not None
        self.plots = []
        self.script = ''
        self.report = ''
        if self.data_info.data_type >= 0:
            self.plots = self.generate_plots(ws)
            self.script = self.generate_script(reflectivity_ws)
            self.report = self.generate_web_report(reflectivity_ws)
        else:
            logging.error("Invalid data type for report: %s", self.data_info.data_type)

    def generate_web_report(self, ws):
        """
            Generate HTML report
        """
        if ws is None:
            meta = "<p>\n<table style='width:80%'>"
            meta += "<tr><td>Run:</td><td><b>%s</b> (direct beam: %s)</td></td></tr>" % (self.data_info.run_number, self.data_info.is_direct_beam)
            meta += "<tr><td>Using ROI:</td><td>req=%s, actual=%s</td></tr>" % (self.data_info.use_roi, self.data_info.use_roi_actual)
            meta += "<tr><td>Peak range:</td><td>%s - %s</td></td></tr>" % (self.data_info.peak_range[0], self.data_info.peak_range[1])
            meta += "<tr><td>Background:</td><td>%s - %s</td></tr>" % (self.data_info.background[0], self.data_info.background[1])
            meta += "<tr><td>Low-res range:</td><td>%s - %s</td></tr>" % (self.data_info.low_res_range[0], self.data_info.low_res_range[1])
            meta += "<tr><td>ROI peak:</td><td>%s - %s</td></tr>" % (self.data_info.roi_peak[0], self.data_info.roi_peak[1])
            meta += "<tr><td>ROI bck:</td><td>%s - %s</td></tr>" % (self.data_info.roi_background[0], self.data_info.roi_background[1])
            meta += "</table>\n<p>\n"
            return meta

        run_object = ws.getRun()
        constant_q_binning = run_object['constant_q_binning'].value
        sangle = run_object['SANGLE'].getStatistics().mean
        dangle = run_object['DANGLE'].getStatistics().mean
        lambda_min = run_object['lambda_min'].value
        lambda_max = run_object['lambda_max'].value
        theta = run_object['two_theta'].value / 2
        huber_x = run_object["HuberX"].getStatistics().mean
        direct_beam = run_object["normalization_run"].value

        dangle0 = run_object['DANGLE0'].getStatistics().mean
        dirpix = run_object['DIRPIX'].getStatistics().mean
        p_charge = run_object['gd_prtn_chrg'].value

        meta = "<p>\n<table style='width:80%'>"
        meta += "<tr><td>Run:</td><td><b>%s</b></td></td><td><b>Direct beam: %s</b></td></tr>" % (run_object['run_number'].value, direct_beam)
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
        meta += "</table>\n"
        
        meta += "<p><table style='width:100%'>"
        meta += "<tr><th>Theta (actual)</th><th>DANGLE [DANGLE0]</th><th>SANGLE</th><th>DIRPIX</th><th>Wavelength</th><th>Huber X</th><th>p-charge [uAh]</th></tr>"
        meta += "<tr><td>%s</td><td>%s [%s]</td><td>%s</td><td>%s</td><td>%s - %s</td><td>%s</td><td>%s</td></tr>\n" % (theta, dangle, dangle0, sangle, dirpix, lambda_min, lambda_max, huber_x, p_charge)
        meta += "</table>\n<p>\n"
        return meta

    def generate_script(self, ws):
        """
            Generate a Mantid script for the reflectivity reduction
        """
        script = '# Run:%s    Cross-section: %s\n' % (self.data_info.run_number, self.data_info.cross_section)
        if ws is not None:
            script_text = GeneratePythonScript(ws)
            script += script_text.replace(', ',',\n                                ')
        else:
            script += "#   No data in this cross-section"
        script += '\n'
        return script

    def generate_plots(self, ws):
        """
            Generate diagnostics plots
        """
        n_x = int(ws.getInstrument().getNumberParameter("number-of-x-pixels")[0])
        n_y = int(ws.getInstrument().getNumberParameter("number-of-y-pixels")[0])

        scatt_peak = self.data_info.peak_range
        scatt_low_res = self.data_info.low_res_range
          
        # X-Y plot
        signal = np.log10(ws.extractY())
        z=np.reshape(signal, (n_x, n_y))
        xy_plot = _plot2d(z=z.T, x=range(n_x), y=range(n_y),
                          x_range=scatt_peak, y_range=scatt_low_res, x_bck_range=self.data_info.background,
                          title="r%s [%s]" % (self.data_info.run_number, self.data_info.cross_section))

        # X-TOF plot
        tof_min = ws.getTofMin()
        tof_max = ws.getTofMax()
        ws = Rebin(ws, params="%s, 50, %s" % (tof_min, tof_max))

        direct_summed = RefRoi(InputWorkspace=ws, IntegrateY=True,
                               NXPixel=n_x, NYPixel=n_y,
                               ConvertToQ=False, YPixelMin=0, YPixelMax=n_y,
                               OutputWorkspace="direct_summed")
        signal = np.log10(direct_summed.extractY())
        tof_axis = direct_summed.extractX()[0]/1000.0

        x_tof_plot = _plot2d(z=signal, y=range(signal.shape[0]), x=tof_axis,
                             x_range=None, y_range=scatt_peak, y_bck_range=self.data_info.background,
                             x_label="TOF (ms)", y_label="X pixel",
                             title="r%s [%s]" % (self.data_info.run_number, self.data_info.cross_section))
                             
        # Count per X pixel
        integrated = Integration(direct_summed)
        integrated = Transpose(integrated)
        signal_y = integrated.readY(0)
        signal_x = range(len(signal_y))
        peak_pixels = _plot1d(signal_x,signal_y, x_range=scatt_peak, bck_range=self.data_info.background,
                              x_label="X pixel", y_label="Counts",
                              title="r%s [%s]" % (self.data_info.run_number, self.data_info.cross_section))

        # TOF distribution
        ws = SumSpectra(ws)
        signal_x = ws.readX(0)/1000.0
        signal_y = ws.readY(0)
        tof_dist = _plot1d(signal_x,signal_y, x_range=None,
                           x_label="TOF (ms)", y_label="Counts",
                           title="r%s [%s]" % (self.data_info.run_number, self.data_info.cross_section))

        return [xy_plot, x_tof_plot, peak_pixels, tof_dist]

def _plot2d(x, y, z, x_range, y_range, x_label="X pixel", y_label="Y pixel", title='', x_bck_range=None, y_bck_range=None):
    colorscale=[[0, "rgb(0,0,131)"], [0.125, "rgb(0,60,170)"], [0.375, "rgb(5,255,255)"],
                [0.625, "rgb(255,255,0)"], [0.875, "rgb(250,0,0)"], [1, "rgb(128,0,0)"]]

    hm = go.Heatmap(x=x, y=y, z=z, autocolorscale=False, type='heatmap', showscale=False,
                     hoverinfo="none", colorscale=colorscale)

    data = [hm]
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
