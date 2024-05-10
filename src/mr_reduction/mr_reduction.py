#pylint: disable=bare-except, dangerous-default-value, wrong-import-position, wrong-import-order, too-many-arguments, too-many-instance-attributes
"""
    Reduction for MR
"""
from __future__ import (absolute_import, division, print_function)
import sys
import os
import time

# from .settings import MANTID_PATH
# sys.path.insert(0, MANTID_PATH)
import mantid
from mantid.simpleapi import *

from .settings import POL_STATE, ANA_STATE, POL_VETO, ANA_VETO
from .settings import AR_OUT_DIR_TEMPLATE, GLOBAL_AR_DIR
from .reflectivity_output import write_reflectivity
from .data_info import DataInfo
from .web_report import Report, process_collection
from .mr_direct_beam_finder import DirectBeamFinder
from .script_output import write_partial_script


DIRECT_BEAM_EVTS_MIN = 1000

class ReductionProcess(object):
    """
        MR automated reduction
    """
    tolerance=0.02
    # Minimum number of events needed to go ahead with the reduction
    min_number_events=200
    pol_state = POL_STATE
    pol_veto = POL_VETO
    ana_state = ANA_STATE
    ana_veto = ANA_VETO

    def __init__(self, data_run, data_ws=None, output_dir=None, const_q_binning=False, const_q_cutoff=0.02,
                 update_peak_range=False, use_roi_bck=False, use_tight_bck=False, bck_offset=3,
                 use_sangle=True, use_roi=True, q_step=-0.02,
                 force_peak_roi=False, peak_roi=[0,0],
                 force_bck_roi=False, bck_roi=[0,0], publish=True, debug=False, live=False):
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
        self.data_ws = data_ws
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
        self.q_step = q_step

        # Options to override the ROI
        self.force_peak_roi = force_peak_roi
        self.forced_peak_roi = peak_roi
        self.force_bck_roi = force_bck_roi
        self.forced_bck_roi = bck_roi

        self.use_slow_flipper_log = False
        self.publish = publish
        self.live = live
        self.json_info = None

        # Script for re-running the reduction
        self.script = ''
        self.logfile = None
        if debug:
            self.logfile = open(os.path.join(GLOBAL_AR_DIR, "MR_live.log"), 'a')
        self.plot_2d = False

    def log(self, msg):
        """ Debug logging """
        if self.logfile:
            self.logfile.write(msg+'\n')
        logger.notice(msg)

    def _extract_data_info(self, xs_list):
        """
            Extract data info for the cross-section with the most events
            :param list xs_list: workspace group
        """
        # Find the cross-section with the most events
        n_max_events = 0
        i_main = 0
        for i in range(len(xs_list)):
            n_events = xs_list[i].getNumberEvents()
            if n_events > n_max_events:
                n_max_events = n_events
                i_main = i

        self.ipts = xs_list[i_main].getRun().getProperty("experiment_identifier").value
        entry = xs_list[i_main].getRun().getProperty("cross_section_id").value
        data_info = DataInfo(xs_list[i_main], entry,
                             use_roi=self.use_roi,
                             update_peak_range=self.update_peak_range,
                             use_roi_bck=self.use_roi_bck,
                             use_tight_bck=self.use_tight_bck,
                             bck_offset=self.bck_offset,
                             force_peak_roi=self.force_peak_roi, peak_roi=self.forced_peak_roi,
                             force_bck_roi=self.force_bck_roi, bck_roi=self.forced_bck_roi)
        # Find direct beam information
        norm_run = None
        direct_info = data_info
        apply_norm = False
        if not data_info.is_direct_beam:
            apply_norm, norm_run, direct_info = self.find_direct_beam(xs_list[i_main])
            if direct_info is None:
                direct_info = data_info

        # Set output directory
        if self.output_dir is None:
            self.output_dir = AR_OUT_DIR_TEMPLATE % dict(ipts=self.ipts)

        # Important note: data_info is created from the cross-section with the most
        # data, so data_info.cross_section indicates which one that was.
        return data_info, direct_info, apply_norm, norm_run

    def slow_filter_cross_sections(self, ws):
        """
            Filter events according to an aggregated state log.
            :param str file_path: file to read

            BL4A:SF:ICP:getDI

            015 (0000 1111): SF1=OFF, SF2=OFF, SF1Veto=OFF, SF2Veto=OFF
            047 (0010 1111): SF1=ON, SF2=OFF, SF1Veto=OFF, SF2Veto=OFF
            031 (0001 1111): SF1=OFF, SF2=ON, SF1Veto=OFF, SF2Veto=OFF
            063 (0011 1111): SF1=ON, SF2=ON, SF1Veto=OFF, SF2Veto=OFF
        """
        state_log = "BL4A:SF:ICP:getDI"
        states = {'Off_Off': 15,
                  'On_Off': 47,
                  'Off_On': 31,
                  'On_On': 63}
        cross_sections = []

        for pol_state in states:
            try:
                _ws = FilterByLogValue(InputWorkspace=ws, LogName=state_log, TimeTolerance=0.1,
                                       MinimumValue=states[pol_state],
                                       MaximumValue=states[pol_state], LogBoundary='Left',
                                       OutputWorkspace='%s_%s' % (ws.getRunNumber(), pol_state))
                _ws.getRun()['cross_section_id'] = pol_state
                if _ws.getNumberEvents() > 0:
                    cross_sections.append(_ws)
            except:
                mantid.logger.error("Could not filter %s: %s" % (pol_state, sys.exc_info()[1]))

        return cross_sections

    def reduce(self):
        """
            Perform the reduction
        """
        self.log("\n\n---------- %s" % time.ctime())

        # Load cross-sections
        _filename = None if self.data_ws is not None else self.file_path
        #if self.data_ws is not None and self.use_slow_flipper_log:
        if self.data_ws is None:
            self.data_ws = LoadEventNexus(Filename=self.file_path, OutputWorkspace='raw_events')
        self.run_number = self.data_ws.getRunNumber()

        if self.use_slow_flipper_log:
            _xs_list = self.slow_filter_cross_sections(self.data_ws)
        else:
            _xs_list = MRFilterCrossSections(Filename=_filename, InputWorkspace=self.data_ws,
                                             PolState=self.pol_state,
                                             AnaState=self.ana_state,
                                             PolVeto=self.pol_veto,
                                             AnaVeto=self.ana_veto,
                                             CrossSectionWorkspaces="%s" % self.data_ws.getRunNumber())
            # If we have no cross section info, treat the data as unpolarized and use Off_Off as the label.
            for ws in _xs_list:
                if 'cross_section_id' not in ws.getRun():
                    ws.getRun()['cross_section_id'] = 'Off_Off'
        xs_list = [ws for ws in _xs_list if not ws.getRun()['cross_section_id'].value == 'unfiltered' and ws.getNumberEvents() > 0]

        # Reduce each cross-section
        report_list = self.reduce_workspace_group(xs_list)

        # Generate stitched plot
        ref_plot = None
        try:
            from .reflectivity_merge import combined_curves, plot_combined, combined_catalog_info

            #ipts_number = self.ipts.split('-')[1]
            matched_runs, scaling_factors, outputs = combined_curves(run=int(self.run_number), ipts=self.ipts)
            if not self.live:
                self.json_info = combined_catalog_info(matched_runs, self.ipts, outputs, run_number=self.run_number)
            self.log("Matched runs: %s" % str(matched_runs))
            ref_plot = plot_combined(matched_runs, scaling_factors, self.ipts, publish=False)
            self.log("Generated reflectivity: %s" % len(str(ref_plot)))
        except:
            self.log("Could not generate combined curve")
            self.log(str(sys.exc_info()[1]))
            logger.error(str(sys.exc_info()[1]))

        # Generate report and script
        logger.notice("Processing collection of %s reports" % len(report_list))
        try:
            html_report, _ = process_collection(summary_content=ref_plot, report_list=report_list,
                                                publish=self.publish, run_number=self.run_number)
        except:
            html_report = ''
            self.log("Could not process reports %s" % sys.exc_info()[1])

        if self.logfile:
            self.logfile.close()
        return html_report

    def reduce_workspace_group(self, xs_list):
        """
        """
        # Extract data info (find peaks, etc...)
        # This can be moved within the for-loop below re-extraction with each cross-section.
        # Generally, the peak ranges should be consistent between cross-section.
        data_info, direct_info, apply_norm, norm_run = self._extract_data_info(xs_list)
        self.log("Norm run: %g" % norm_run)

        # Determine the name of the direct beam workspace as needed
        ws_norm = direct_info.workspace_name if apply_norm and norm_run is not None else ''

        # Find reflectivity peak of scattering run
        ws = xs_list[0]
        run_number = ws.getRunNumber()
        entry = ws.getRun().getProperty("cross_section_id").value
        self.ipts = ws.getRun().getProperty("experiment_identifier").value
        logger.notice("R%s [%s] DATA TYPE: %s [ref=%s] [%s events]" % (run_number, entry, data_info.data_type, data_info.cross_section, ws.getNumberEvents()))
        self.log("R%s [%s] DATA TYPE: %s [ref=%s] [%s events]" % (run_number,
                                                                  entry,
                                                                  data_info.data_type,
                                                                  data_info.cross_section,
                                                                  ws.getNumberEvents()))

        if data_info.data_type < 1 or ws.getNumberEvents() < self.min_number_events:
            self.log("  - skipping: data type=%s; events: %s [cutoff: %s]" % (data_info.data_type, ws.getNumberEvents(), self.min_number_events))
            return [Report(ws, data_info, data_info, None, logfile=self.logfile, plot_2d=self.plot_2d)]

        wsg = GroupWorkspaces(InputWorkspaces=xs_list)
        MagnetismReflectometryReduction(InputWorkspace=wsg,
                                        NormalizationWorkspace=ws_norm,
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
                                        QStep=self.q_step,
                                        UseWLTimeAxis=False,
                                        TimeAxisStep=40,
                                        UseSANGLE=self.use_sangle,
                                        TimeAxisRange=data_info.tof_range,
                                        SpecularPixel=data_info.peak_position,
                                        ConstantQBinning=self.const_q_binning,
                                        ConstQTrim=0.1,
                                        OutputWorkspace="r_%s" % run_number)

        # Generate partial python script
        self.log("Workspace r_%s: %s" % (run_number, type(mtd["r_%s" % run_number])))
        write_partial_script(mtd["r_%s" % run_number])

        report_list = []
        for ws in xs_list:
            try:
                if str(ws).endswith('unfiltered'):
                    continue
                self.log("\n--- Run %s %s ---\n" % (self.run_number, str(ws)))
                entry = ws.getRun().getProperty("cross_section_id").value
                reflectivity = mtd["%s__reflectivity" % str(ws)]
                report = Report(ws, data_info, direct_info, reflectivity,
                                logfile=self.logfile, plot_2d=self.plot_2d)
                report_list.append(report)

                # Write output file
                self.log("  - ready to write: %s" % self.output_dir)
                write_reflectivity([reflectivity],
                                   os.path.join(self.output_dir, 'REF_M_%s_%s_autoreduce.dat' % (run_number, entry)), data_info.cross_section_label)
                SaveNexus(InputWorkspace=reflectivity,
                          Filename=os.path.join(self.output_dir, 'REF_M_%s_%s_autoreduce.nxs.h5' % (run_number, entry)))
                self.log("  - done writing")
                # Write partial output script
            except:
                self.log("  - reduction failed")
                # No data for this cross-section, skip to the next
                logger.error("Cross section: %s" % str(sys.exc_info()[1]))
                report = Report(ws, data_info, direct_info, None, plot_2d=self.plot_2d)
                report_list.append(report)

        return report_list

    def find_direct_beam(self, scatt_ws):
        """
            Find the appropriate direct beam run
            :param workspace scatt_ws: scattering workspace we are trying to match
        """
        run_number = scatt_ws.getRunNumber()
        entry = scatt_ws.getRun().getProperty("cross_section_id").value
        db_finder = DirectBeamFinder(scatt_ws, skip_slits=False,
                                     tolerance=self.tolerance,
                                     experiment=self.ipts)
        norm_run = db_finder.search()
        if norm_run is None:
            logger.warning("Run %s [%s]: Could not find direct beam with matching slit, trying with wl only" % (run_number, entry))
            norm_run = db_finder.search(skip_slits=True)

        apply_norm = False
        direct_info = None
        if norm_run is None:
            logger.warning("Run %s [%s]: Could not find direct beam run: skipping" % (run_number, entry))
        else:
            logger.notice("Run %s [%s]: Direct beam run: %s" % (run_number, entry, norm_run))

            # Find peak in direct beam run
            for norm_entry in ['entry', 'entry-Off_Off', 'entry-On_Off', 'entry-Off_On', 'entry-On_On']:
                try:
                    ws_direct = LoadEventNexus(Filename="REF_M_%s" % norm_run,
                                               NXentryName=norm_entry,
                                               OutputWorkspace="MR_%s" % norm_run)
                    if ws_direct.getNumberEvents() > DIRECT_BEAM_EVTS_MIN:
                        direct_info = DataInfo(ws_direct, norm_entry,
                                               use_roi=self.use_roi,
                                               update_peak_range=True, #self.update_peak_range,
                                               use_roi_bck=self.use_roi_bck,
                                               use_tight_bck=self.use_tight_bck,
                                               bck_offset=self.bck_offset)
                        apply_norm = True
                        break
                except:
                    # No data in this cross-section
                    logger.error("Direct beam %s: %s" % (norm_entry, sys.exc_info()[1]))

        return apply_norm, norm_run, direct_info
