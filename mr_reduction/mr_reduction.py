#pylint: disable=bare-except, dangerous-default-value
"""
    Reduction for MR
"""
from __future__ import (absolute_import, division, print_function)
import sys
import os
sys.path.insert(0,'/opt/mantidnightly/bin')
import mantid
from mantid.simpleapi import *
import math
import json
import logging

from .reflectivity_output import write_reflectivity
from .data_info import DataInfo
from .web_report import Report, process_collection


class ReductionProcess(object):
    """
        MR automated reduction
    """
    tolerance=0.02
    pol_state = "PolarizerState"
    pol_veto = "PolarizerVeto"
    ana_state = "AnalyzerState"
    ana_veto = "AnalyzerVeto"

    def __init__(self, data_run, output_dir=None, const_q_binning=False, const_q_cutoff=0.02,
                 update_peak_range=False, use_roi_bck=False, use_tight_bck=False, bck_offset=3,
                 huber_x_cut=4.95, use_sangle=True, use_roi=True,
                 force_peak_roi=False, peak_roi=[0,0],
                 force_bck_roi=False, bck_roi=[0,0]):
        """
            The automated reduction is initializable such that most of what we need can be
            changed at initialization time. That way the post-processing framework only
            needs to create the object and execute the reduction.

            @param data_run: run number or file path
        """
        try:
            int(data_run)
            self.run_number = data_run
            self.file_path = "REF_M_%s" % data_run
        except:
            self.run_number = None
            self.file_path = data_run
        self.ipts = None
        self.output_dir = output_dir
        self.const_q_binning = const_q_binning
        # Q-value below which const-q binning will not be used [NOT CURRENTLY IMPLEMENTED]
        self.const_q_cutoff = const_q_cutoff

        # Options
        self.use_roi = use_roi
        self.use_sangle = use_sangle
        self.update_peak_range = update_peak_range
        self.use_roi_bck = use_roi_bck
        self.use_tight_bck = use_tight_bck
        self.bck_offset = bck_offset

        # Options to override the ROI
        self.force_peak_roi = force_peak_roi
        self.forced_peak_roi = peak_roi
        self.force_bck_roi = force_bck_roi
        self.forced_bck_roi = bck_roi

        self.huber_x_cut = huber_x_cut

        # Script for re-running the reduction
        self.script = ''

    def _extract_data_info(self, xs_list):
        """
            Extract data info for the cross-section with the most events
            :param list xs_list: workspace group
        """
        n_max_events = 0
        i_main = 0
        for i in range(len(xs_list)):
            n_events = xs_list[i].getNumberEvents()
            if n_events > n_max_events:
                n_max_events = n_events
                i_main = i

        entry = xs_list[i_main].getRun().getProperty("cross_section_id").value
        data_info = DataInfo(xs_list[i_main], entry,
                     use_roi=self.use_roi,
                     update_peak_range=self.update_peak_range,
                     use_roi_bck=self.use_roi_bck,
                     use_tight_bck=self.use_tight_bck,
                     huber_x_cut=self.huber_x_cut,
                     bck_offset=self.bck_offset,
                     force_peak_roi=self.force_peak_roi, peak_roi=self.forced_peak_roi,
                     force_bck_roi=self.force_bck_roi, bck_roi=self.forced_bck_roi)
        return data_info

    def reduce(self):
        """
            Perform the reduction
        """
        report_list = []

        # Load cross-sections
        xs_list = MRFilterCrossSections(Filename=self.file_path,
                                        PolState=self.pol_state,
                                        AnaState=self.ana_state,
                                        PolVeto=self.pol_veto,
                                        AnaVeto=self.ana_veto)

        # Extract data info (find peaks, etc...)
        data_info = self._extract_data_info(xs_list) # set to None for re-extraction with each cross-section

        # Reduce each cross-section
        for ws in xs_list:
            try:
                self.run_number = ws.getRunNumber()
                report = self.reduce_cross_section(self.run_number, ws=ws, data_info=data_info)
                report_list.append(report)
            except:
                # No data for this cross-section, skip to the next
                logging.info("Cross section: %s", str(sys.exc_value))

        # Generate stitched plot
        ref_plot = None
        try:
            from .reflectivity_merge import combined_curves, plot_combined

            ipts_number = self.ipts.split('-')[1]
            matched_runs, scaling_factors = combined_curves(run=int(self.run_number), ipts=ipts_number)
            ref_plot = plot_combined(matched_runs, scaling_factors, ipts_number, publish=False)
        except:
            logging.error(str(sys.exc_value))

        # Generate report and script
        logging.info("Processing collection of %s reports", len(report_list))
        html_report, script = process_collection(summary_content=ref_plot, report_list=report_list, publish=True, run_number=self.run_number)

        try:
            if self.output_dir is None:
                self.output_dir = "/SNS/REF_M/%s/shared/autoreduce/" % self.ipts
            fd = open(os.path.join(self.output_dir, 'REF_M_%s_autoreduce.py' % self.run_number), 'w')
            fd.write(script)
            fd.close()
        except:
            logging.error("Could not write reduction script: %s", sys.exc_value)
        return html_report

    def reduce_cross_section(self, run_number, ws, data_info=None):
        """
            Reduce a given cross-section of a data run
            Returns a reflectivity workspace and an information value
            
            Type info:
                -1: too few counts
                 0: direct beam run
                 1: scattering run
        """
        # Find reflectivity peak of scattering run
        entry = ws.getRun().getProperty("cross_section_id").value

        self.ipts = ws.getRun().getProperty("experiment_identifier").value

        # Determine peak position and ranges
        if data_info is None:
            data_info = DataInfo(ws, entry,
                                 use_roi=self.use_roi,
                                 update_peak_range=self.update_peak_range,
                                 use_roi_bck=self.use_roi_bck,
                                 use_tight_bck=self.use_tight_bck,
                                 huber_x_cut=self.huber_x_cut,
                                 bck_offset=self.bck_offset,
                                 force_peak_roi=self.force_peak_roi, peak_roi=self.forced_peak_roi,
                                 force_bck_roi=self.force_bck_roi, bck_roi=self.forced_bck_roi)

        if data_info.data_type < 1:
            return Report(ws, data_info, data_info, None)

        # Find direct beam run
        norm_run = self.find_direct_beam(ws)
        if norm_run is None:
            logging.warning("Run %s [%s]: Could not find direct beam with matching slit, trying with wl only", run_number, entry)
            norm_run = self.find_direct_beam(ws, skip_slits=True)

        apply_norm = True
        direct_info = None
        if norm_run is None:
            logging.warning("Run %s [%s]: Could not find direct beam run: skipping", run_number, entry)
            apply_norm = False
        else:
            logging.info("Run %s [%s]: Direct beam run: %s", run_number, entry, norm_run)

            # Find peak in direct beam run
            for norm_entry in ['entry', 'entry-Off_Off', 'entry-On_Off', 'entry-Off_On', 'entry-On_On']:
                try:
                    ws_direct = LoadEventNexus(Filename="REF_M_%s" % norm_run,
                                               NXentryName=norm_entry,
                                               OutputWorkspace="MR_%s" % norm_run)
                    if ws_direct.getNumberEvents() > 10000:
                        logging.info("Found direct beam entry: %s [%s]", norm_run, norm_entry)
                        direct_info = DataInfo(ws_direct, norm_entry,
                                               use_roi=self.use_roi,
                                               update_peak_range=self.update_peak_range,
                                               use_roi_bck=self.use_roi_bck,
                                               use_tight_bck=self.use_tight_bck,
                                               huber_x_cut=self.huber_x_cut,
                                               bck_offset=self.bck_offset)
                        break
                except:
                    # No data in this cross-section
                    logging.debug("Direct beam %s: %s", norm_entry, sys.exc_value)

        if direct_info is None:
            direct_info = data_info

        MagnetismReflectometryReduction(#RunNumbers=[run_number,],
                                        InputWorkspace=ws,
                                        NormalizationRunNumber=norm_run,
                                        SignalPeakPixelRange=data_info.peak_range,
                                        SubtractSignalBackground=True,
                                        SignalBackgroundPixelRange=data_info.background,
                                        ApplyNormalization=apply_norm,
                                        NormPeakPixelRange=direct_info.peak_range,
                                        SubtractNormBackground=True,
                                        NormBackgroundPixelRange=direct_info.background,
                                        CutLowResDataAxis=True,
                                        LowResDataAxisPixelRange=data_info.low_res_range,
                                        CutLowResNormAxis=True,
                                        LowResNormAxisPixelRange=direct_info.low_res_range,
                                        CutTimeAxis=True,
                                        QMin=0.001,
                                        QStep=-0.01,
                                        UseWLTimeAxis=False,
                                        TimeAxisStep=40,
                                        UseSANGLE=self.use_sangle,
                                        TimeAxisRange=data_info.tof_range,
                                        SpecularPixel=data_info.peak_position,
                                        ConstantQBinning=self.const_q_binning,
                                        EntryName='entry-%s' % entry,
                                        OutputWorkspace="r_%s_%s" % (run_number, entry))

        # Write output file
        reflectivity = mtd["r_%s_%s" % (run_number, entry)]
        if self.output_dir is None:
            self.output_dir = "/SNS/REF_M/%s/shared/autoreduce/" % self.ipts
        write_reflectivity([mtd["r_%s_%s" % (run_number, entry)]],
                           os.path.join(self.output_dir, 'REF_M_%s_%s_autoreduce.dat' % (run_number, entry)), entry)

        return Report(ws, data_info, direct_info, mtd["r_%s_%s" % (run_number, entry)])

    def find_direct_beam(self, scatt_ws, skip_slits=False, allow_later_runs=False):
        """
            Find the appropriate direct beam run
            #TODO: refactor this
        """
        data_dir = "/SNS/REF_M/%s/data" % self.ipts
        ar_dir = "/SNS/REF_M/%s/shared/autoreduce" % self.ipts
        db_dir = "/SNS/REF_M/shared/autoreduce/direct_beams/"

        wl_ = scatt_ws.getRun().getProperty("LambdaRequest").getStatistics().mean
        s1_ = scatt_ws.getRun().getProperty("S1HWidth").getStatistics().mean
        s2_ = scatt_ws.getRun().getProperty("S2HWidth").getStatistics().mean
        s3_ = scatt_ws.getRun().getProperty("S3HWidth").getStatistics().mean
        run_ = int(scatt_ws.getRunNumber())
        #dangle_ = abs(scatt_ws.getRun().getProperty("DANGLE").getStatistics().mean)

        closest = None
        if not os.path.isdir(data_dir):
            data_dir = db_dir
        for item in os.listdir(data_dir):
            if item.endswith("_event.nxs") or item.endswith("h5"):
                summary_path = os.path.join(ar_dir, item+'.json')
                if not os.path.isfile(summary_path):
                    is_valid = False
                    for entry in ['entry', 'entry-Off_Off', 'entry-On_Off', 'entry-Off_On', 'entry-On_On']:
                        try:
                            ws = LoadEventNexus(Filename=os.path.join(data_dir, item),
                                                NXentryName=entry,
                                                MetaDataOnly=False,
                                                OutputWorkspace="meta_data")
                            if ws.getNumberEvents() > 1000:
                                is_valid = True
                                break
                        except:
                            # If there's no data in the entry, LoadEventNexus will fail.
                            # This is expected so we just need to proceed with the next entry.
                            logging.debug("Finding direct beam: %s [%s]: %s", item, entry, sys.exc_value)

                    if not is_valid:
                        meta_data = dict(run=0, invalid=True)
                        fd = open(summary_path, 'w')
                        fd.write(json.dumps(meta_data))
                        fd.close()
                        continue

                    run_number = int(ws.getRunNumber())
                    sangle = ws.getRun().getProperty("SANGLE").getStatistics().mean
                    dangle = ws.getRun().getProperty("DANGLE").getStatistics().mean
                    dangle0 = ws.getRun().getProperty("DANGLE0").getStatistics().mean
                    direct_beam_pix = ws.getRun().getProperty("DIRPIX").getStatistics().mean
                    det_distance = ws.getRun().getProperty("SampleDetDis").getStatistics().mean / 1000.0
                    pixel_width = 0.0007

                    huber_x = ws.getRun().getProperty("HuberX").getStatistics().mean
                    wl = ws.getRun().getProperty("LambdaRequest").getStatistics().mean
                    s1 = ws.getRun().getProperty("S1HWidth").getStatistics().mean
                    s2 = ws.getRun().getProperty("S2HWidth").getStatistics().mean
                    s3 = ws.getRun().getProperty("S3HWidth").getStatistics().mean
                    try:
                        data_info = DataInfo(ws, entry,
                                             use_roi=self.use_roi,
                                             update_peak_range=self.update_peak_range,
                                             use_roi_bck=self.use_roi_bck,
                                             use_tight_bck=self.use_tight_bck,
                                             huber_x_cut=self.huber_x_cut,
                                             bck_offset=self.bck_offset,
                                             force_peak_roi=self.force_peak_roi, peak_roi=self.forced_peak_roi,
                                             force_bck_roi=self.force_bck_roi, bck_roi=self.forced_bck_roi)

                        peak_pos = data_info.peak_position if data_info.peak_position is not None else direct_beam_pix
                    except:
                        data_info = None
                        peak_pos = direct_beam_pix
                    theta_d = (dangle - dangle0) / 2.0
                    theta_d += ((direct_beam_pix - peak_pos) * pixel_width) * 180.0 / math.pi / (2.0 * det_distance)

                    meta_data = dict(theta_d=theta_d, run=run_number, wl=wl, s1=s1, s2=s2, s3=s3, dangle=dangle, sangle=sangle, huber_x=huber_x)
                    fd = open(summary_path, 'w')
                    fd.write(json.dumps(meta_data))
                    fd.close()
                    if data_info is not None and data_info.data_type == 0:
                        standard_path = os.path.join(db_dir, item+'.json')
                        fd = open(standard_path, 'w')
                        fd.write(json.dumps(meta_data))
                        fd.close()
                else:
                    fd = open(summary_path, 'r')
                    meta_data = json.loads(fd.read())
                    fd.close()
                    if 'invalid' in meta_data.keys():
                        continue
                    run_number = meta_data['run']
                    dangle = meta_data['dangle']
                    theta_d = meta_data['theta_d'] if 'theta_d' in meta_data else 0
                    sangle = meta_data['sangle'] if 'sangle' in meta_data else 0

                    wl = meta_data['wl']
                    s1 = meta_data['s1']
                    s2 = meta_data['s2']
                    s3 = meta_data['s3']
                    if 'huber_x' in meta_data:
                        huber_x = meta_data['huber_x']
                    else:
                        huber_x = 0
                #if run_number == run_ or (dangle > self.tolerance and huber_x < 9) :
                if run_number == run_ or ((theta_d > self.tolerance or sangle > self.tolerance) and huber_x < self.huber_x_cut):
                    continue
                # If we don't allow runs taken later than the run we are processing...
                if not allow_later_runs and run_number > run_:
                    continue

                if math.fabs(wl-wl_) < self.tolerance \
                    and (skip_slits is True or \
                    (math.fabs(s1-s1_) < self.tolerance \
                    and math.fabs(s2-s2_) < self.tolerance \
                    and math.fabs(s3-s3_) < self.tolerance)):
                    if closest is None:
                        closest = run_number
                    elif abs(run_number-run_) < abs(closest-run_):
                        closest = run_number

        if closest is None and os.path.isdir(ar_dir):
            for item in os.listdir(ar_dir):
                if item.endswith(".json"):
                    summary_path = os.path.join(ar_dir, item)
                    fd = open(summary_path, 'r')
                    meta_data = json.loads(fd.read())
                    fd.close()
                    if 'invalid' in meta_data.keys():
                        continue
                    run_number = meta_data['run']
                    dangle = meta_data['dangle']
                    theta_d = meta_data['theta_d'] if 'theta_d' in meta_data else 0
                    sangle = meta_data['sangle'] if 'sangle' in meta_data else 0

                    wl = meta_data['wl']
                    s1 = meta_data['s1']
                    s2 = meta_data['s2']
                    s3 = meta_data['s3']
                    if 'huber_x' in meta_data:
                        huber_x = meta_data['huber_x']
                    else:
                        huber_x = 0
                    #if run_number == run_ or (dangle > self.tolerance and huber_x < 9) :
                    if run_number == run_ or ((theta_d > self.tolerance or sangle > self.tolerance) and huber_x < self.huber_x_cut):
                        continue
                    # If we don't allow runs taken later than the run we are processing...
                    if not allow_later_runs and run_number > run_:
                        continue

                    if math.fabs(wl-wl_) < self.tolerance \
                        and (skip_slits is True or \
                        (math.fabs(s1-s1_) < self.tolerance \
                        and math.fabs(s2-s2_) < self.tolerance \
                        and math.fabs(s3-s3_) < self.tolerance)):
                        if closest is None:
                            closest = run_number
                        elif abs(run_number-run_) < abs(closest-run_):
                            closest = run_number

        if closest is None:
            for item in os.listdir(db_dir):
                if item.endswith(".json"):
                    summary_path = os.path.join(db_dir, item)
                    fd = open(summary_path, 'r')
                    meta_data = json.loads(fd.read())
                    fd.close()
                    if 'invalid' in meta_data.keys():
                        continue
                    run_number = meta_data['run']
                    dangle = meta_data['dangle']
                    theta_d = meta_data['theta_d'] if 'theta_d' in meta_data else 0
                    sangle = meta_data['sangle'] if 'sangle' in meta_data else 0

                    wl = meta_data['wl']
                    s1 = meta_data['s1']
                    s2 = meta_data['s2']
                    s3 = meta_data['s3']
                    if 'huber_x' in meta_data:
                        huber_x = meta_data['huber_x']
                    else:
                        huber_x = 0
                    #if run_number == run_ or (dangle > self.tolerance and huber_x < 9) :
                    if run_number == run_ or ((theta_d > self.tolerance or sangle > self.tolerance) and huber_x < self.huber_x_cut):
                        continue
                    # If we don't allow runs taken later than the run we are processing...
                    if not allow_later_runs and run_number > run_:
                        continue

                    if math.fabs(wl-wl_) < self.tolerance \
                        and (skip_slits is True or \
                        (math.fabs(s1-s1_) < self.tolerance \
                        and math.fabs(s2-s2_) < self.tolerance \
                        and math.fabs(s3-s3_) < self.tolerance)):
                        if closest is None:
                            closest = run_number
                        elif abs(run_number-run_) < abs(closest-run_):
                            closest = run_number

        return closest
