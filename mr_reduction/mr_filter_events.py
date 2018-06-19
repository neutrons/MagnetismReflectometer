#pylint: disable=bare-except, wrong-import-order, unused-argument
"""
    Filter MR data and separate cross-section for compatibility with legacy software.
"""
from __future__ import (absolute_import, division, print_function)
import sys
import logging

import mantid.simpleapi as api

from .settings import POL_STATE, ANA_STATE, POL_VETO, ANA_VETO
from .settings import TOF_MIN, TOF_MAX, TOF_BIN

def filter_cross_sections(file_path, events=True, histo=False):
    """
        Filter events according to polarization state.
        :param str file_path: file to read
        :param bool events: if True, an event nexus file will be written
        :param bool histo: if True, a histo nexus file will be written
    """
    cross_sections = {}
    cross_sections_histo = {}

    xs_list = api.MRFilterCrossSections(file_path, PolState=POL_STATE, AnaState=ANA_STATE, PolVeto=POL_VETO, AnaVeto=ANA_VETO)
    for workspace in xs_list:
        entry = workspace.getRun().getProperty("cross_section_id").value

        if events:
            events_file = "/tmp/filtered_%s_%s.nxs" % (entry, "events")
            api.SaveNexus(InputWorkspace=workspace, Filename=events_file, Title='entry_%s' % entry)
            cross_sections['entry-%s' % entry] = events_file
        if histo:
            ws_binned = api.Rebin(InputWorkspace=workspace, Params="%s, %s, %s" % (TOF_MIN, TOF_BIN, TOF_MAX), PreserveEvents=False)
            histo_file = "/tmp/filtered_%s_%s.nxs" % (entry, "histo")
            api.SaveNexus(InputWorkspace=ws_binned, Filename=histo_file, Title='entry_%s' % entry)
            cross_sections_histo['entry-%s' % entry] = histo_file

    return cross_sections, cross_sections_histo

def _filter_cross_sections(file_path, events=True, histo=False):
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
    cross_sections = {}
    workspace = api.LoadEventNexus(Filename=file_path, OutputWorkspace="raw_events")

    for pol_state in states:
        try:
            _ws = api.FilterByLogValue(InputWorkspace=workspace, LogName=state_log, TimeTolerance=0.1,
                                       MinimumValue=states[pol_state],
                                       MaximumValue=states[pol_state], LogBoundary='Left')

            events_file = "/tmp/filtered_%s_%s.nxs" % (pol_state, "events")
            api.SaveNexus(InputWorkspace=_ws, Filename=events_file, Title='entry_%s' % pol_state)
            cross_sections['entry-%s' % pol_state] = events_file
        except:
            logging.error("Could not filter %s: %s", pol_state, sys.exc_info()[1])

    return cross_sections, None
