#pylint: disable=bare-except
"""
    Filter MR data and separate cross-section for compatibility with legacy software.
"""
from __future__ import (absolute_import, division, print_function)
import sys
from .settings import POL_STATE, ANA_STATE, POL_VETO, ANA_VETO
from .settings import TOF_MIN, TOF_MAX, TOF_BIN
from .settings import MANTID_PATH
sys.path.append(MANTID_PATH)

import logging
from mantid.simpleapi import *


def _filter_cross_sections(file_path, events=True, histo=False):
    """
        Filter events according to polarization state.
        :param str file_path: file to read
        :param bool events: if True, an event nexus file will be written
        :param bool histo: if True, a histo nexus file will be written
    """
    cross_sections = {}
    cross_sections_histo = {}

    xs_list = MRFilterCrossSections(file_path, PolState=POL_STATE, AnaState=ANA_STATE, PolVeto='', AnaVeto='')
    for ws in xs_list:
        entry = ws.getRun().getProperty("cross_section_id").value

        if events:
            events_file = "/tmp/filtered_%s_%s.nxs" % (entry, "events")
            SaveNexus(InputWorkspace=ws, Filename=events_file, Title='entry_%s' % entry)
            cross_sections['entry-%s' % entry] = events_file
        if histo:
            ws_binned = Rebin(InputWorkspace=ws, Params="%s, %s, %s" % (TOF_MIN, TOF_BIN, TOF_MAX), PreserveEvents=False)
            histo_file = "/tmp/filtered_%s_%s.nxs" % (entry, "histo")
            SaveNexus(InputWorkspace=ws_binned, Filename=histo_file, Title='entry_%s' % entry)
            cross_sections_histo['entry-%s' % entry] = histo_file

    return cross_sections, cross_sections_histo

def save_nxs(ws, pol_state, ana_state, events=True, histo=False):
    """
        Save a polarization state in a nexus file.
        :param Workspace ws: Mantid workspace
        :param str pol_state: polarization state On/Off
        :param str ana_state: analyzer state On/Off
        :param bool events: if True, an event nexus file will be written
        :param bool histo: if True, a histo nexus file will be written
    """
    output_events_name = None
    output_histo_name = None
    if events:
        output_events_name = "/tmp/filtered_%s_%s_%s.nxs" % (pol_state, ana_state, "events")
        SaveNexus(InputWorkspace=ws, Filename=output_events_name, Title='entry_%s_%s' % (pol_state, ana_state))
    if histo:
        ws_binned = Rebin(InputWorkspace=ws, Params="%s, %s, %s" % (TOF_MIN, TOF_BIN, TOF_MAX), PreserveEvents=False)
        output_histo_name = "/tmp/filtered_%s_%s_%s.nxs" % (pol_state, ana_state, "histo")
        SaveNexus(InputWorkspace=ws_binned, Filename=output_histo_name, Title='entry_%s_%s' % (pol_state, ana_state))
    return output_events_name, output_histo_name

##########################################################################
# The following is currently used while FilterEvents is being fixed,     #
# after which we will use MRFilterCrossSections with the function above. #
##########################################################################

def filter_analyzer(ws, pol_state='Off', events=True, histo=False):
    """
        Filter events according to the analyzer.
        :param Workspace ws: Mantid workspace
        :param str pol_state: polarization state On/Off
        :param bool events: if True, an event nexus file will be written
        :param bool histo: if True, a histo nexus file will be written
    """
    cross_sections = {}
    cross_sections_histo = {}
    analyzer = ws.getRun().getProperty("Analyzer").value[0]
    if analyzer > 0:
        try:
            ws_ana_off = FilterByLogValue(InputWorkspace=ws, LogName=ANA_STATE,
                                          MinimumValue=-0.01, MaximumValue=0.01, LogBoundary='Left')
            ws_ana_off = FilterByLogValue(InputWorkspace=ws_ana_off, LogName=ANA_VETO, TimeTolerance=0.1,
                                         MinimumValue=-.01, MaximumValue=0.01, LogBoundary='Left')
            events_file, histo_file = save_nxs(str(ws_ana_off), pol_state, 'Off', events, histo)
            cross_sections['entry-%s_Off' % pol_state] = events_file
            cross_sections_histo['entry-%s_Off' % pol_state] = histo_file
        except:
            logging.error("Could not filter %s-Off", pol_state)

        try:
            ws_ana_on = FilterByLogValue(InputWorkspace=ws, LogName=ANA_STATE,
                                         MinimumValue=1, MaximumValue=1, LogBoundary='Left')
            ws_ana_on = FilterByLogValue(InputWorkspace=ws_ana_on, LogName=ANA_VETO, TimeTolerance=0.1,
                                         MinimumValue=-.01, MaximumValue=0.01, LogBoundary='Left')

            events_file, histo_file = save_nxs(str(ws_ana_on), pol_state, 'On', events, histo)
            cross_sections['entry-%s_On' % pol_state] = events_file
            cross_sections_histo['entry-%s_On' % pol_state] = histo_file
        except:
            logging.error("Could not filter %s-On", pol_state)
    else:
        events_file, histo_file = save_nxs(str(ws), pol_state, 'Off', events, histo)
        cross_sections['entry-%s_Off' % pol_state] = events_file
        cross_sections_histo['entry-%s_Off' % pol_state] = histo_file
    return cross_sections, cross_sections_histo

def filter_cross_sections(file_path, events=True, histo=False):
    """
        Filter events according to polarization state.
        :param str file_path: file to read
        :param bool events: if True, an event nexus file will be written
        :param bool histo: if True, a histo nexus file will be written
    """
    ws = LoadEventNexus(Filename=file_path, OutputWorkspace="raw_events")

    # Check whether we have a polarizer
    polarizer = ws.getRun().getProperty("Polarizer").value[0]

    # Determine cross-sections
    cross_sections = {}
    cross_sections_histo = {}
    if polarizer > 0:
        ws_off = FilterByLogValue(InputWorkspace=ws, LogName=POL_STATE, TimeTolerance=0.1,
                                  MinimumValue=-.01, MaximumValue=0.01, LogBoundary='Left')
        ws_off = FilterByLogValue(InputWorkspace=ws_off, LogName=POL_VETO, TimeTolerance=0.1,
                                  MinimumValue=-.01, MaximumValue=0.01, LogBoundary='Left')

        xs_events, xs_histo = filter_analyzer(ws_off, 'Off', events, histo)
        cross_sections.update(xs_events)
        cross_sections_histo.update(xs_histo)

        ws_on = FilterByLogValue(InputWorkspace=ws, LogName=POL_STATE, TimeTolerance=0.1,
                                 MinimumValue=0.99, MaximumValue=1.01, LogBoundary='Left')
        ws_on = FilterByLogValue(InputWorkspace=ws_on, LogName=POL_VETO, TimeTolerance=0.1,
                                 MinimumValue=-.01, MaximumValue=0.01, LogBoundary='Left')

        xs_events, xs_histo = filter_analyzer(ws_on, 'On', events, histo)
        cross_sections.update(xs_events)
        cross_sections_histo.update(xs_histo)
    else:
        xs_events, xs_histo = filter_analyzer(ws, 'Off', events, histo)
        cross_sections.update(xs_events)
        cross_sections_histo.update(xs_histo)

    return cross_sections, cross_sections_histo
