#pylint: disable=bare-except
"""
    Dummy replacement for MRFilterCrossSections while FilterEvents is being fixed.

    The problem: filtered out logs are currently saved in the filtered
    workspace as a zero-length log instead of having the last value in place.
"""
import sys
import logging
import mantid
from mantid.simpleapi import *
from .settings import POL_STATE, ANA_STATE, POL_VETO, ANA_VETO

def _dummy_filter_analyzer(ws, pol_state='Off'):
    """
        Filter events according to the analyzer.
        :param Workspace ws: Mantid workspace
        :param str pol_state: polarization state On/Off
    """
    cross_sections = []
    analyzer = ws.getRun().getProperty("Analyzer").value[0]
    if analyzer > 0:
        try:
            ws_ana_off = FilterByLogValue(InputWorkspace=ws, LogName=ANA_STATE,
                                          MinimumValue=-0.01, MaximumValue=0.01, LogBoundary='Left')
            ws_ana_off = FilterByLogValue(InputWorkspace=ws_ana_off, LogName=ANA_VETO, TimeTolerance=0.1,
                                         MinimumValue=-.01, MaximumValue=0.01, LogBoundary='Left',
                                         OutputWorkspace='entry-%s_Off' % pol_state)
            ws_ana_off.getRun()['cross_section_id'] = '%s_Off' % pol_state
            cross_sections.append(ws_ana_off)
        except:
            logging.error("Could not filter %s-Off", pol_state)

        try:
            ws_ana_on = FilterByLogValue(InputWorkspace=ws, LogName=ANA_STATE,
                                         MinimumValue=1, MaximumValue=1, LogBoundary='Left')
            ws_ana_on = FilterByLogValue(InputWorkspace=ws_ana_on, LogName=ANA_VETO, TimeTolerance=0.1,
                                         MinimumValue=-.01, MaximumValue=0.01, LogBoundary='Left',
                                         OutputWorkspace='entry-%s_On' % pol_state)
            ws_ana_on.getRun()['cross_section_id'] = '%s_On' % pol_state
            cross_sections.append(ws_ana_on)
        except:
            logging.error("Could not filter %s-On", pol_state)
    else:
        ws_off = CloneWorkspace(InputWorkspace=ws, OutputWorkspace='entry-%s_Off' % pol_state)
        ws_off.getRun()['cross_section_id'] = '%s_Off' % pol_state
        cross_sections.append(ws_off)
    return cross_sections

def _dummy_filter_cross_sections(ws):
    """
        Filter events according to polarization state.
        :param Workspace ws: Mantid workspace
    """
    # Check whether we have a polarizer
    polarizer = ws.getRun().getProperty("Polarizer").value[0]

    # Determine cross-sections
    cross_sections = []
    if polarizer > 0:
        ws_off = FilterByLogValue(InputWorkspace=ws, LogName=POL_STATE, TimeTolerance=0.1,
                                  MinimumValue=-.01, MaximumValue=0.01, LogBoundary='Left')
        ws_off = FilterByLogValue(InputWorkspace=ws_off, LogName=POL_VETO, TimeTolerance=0.1,
                                  MinimumValue=-.01, MaximumValue=0.01, LogBoundary='Left')

        xs_events = _dummy_filter_analyzer(ws_off, 'Off')
        cross_sections.extend(xs_events)

        ws_on = FilterByLogValue(InputWorkspace=ws, LogName=POL_STATE, TimeTolerance=0.1,
                                 MinimumValue=0.99, MaximumValue=1.01, LogBoundary='Left')
        ws_on = FilterByLogValue(InputWorkspace=ws_on, LogName=POL_VETO, TimeTolerance=0.1,
                                 MinimumValue=-.01, MaximumValue=0.01, LogBoundary='Left')

        xs_events = _dummy_filter_analyzer(ws_on, 'On')
        cross_sections.extend(xs_events)
    else:
        xs_events = _dummy_filter_analyzer(ws, 'Off')
        cross_sections.extend(xs_events)

    return cross_sections

def dummy_filter_cross_sections(ws):
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
                                  OutputWorkspace='entry-%s' % pol_state)
            _ws.getRun()['cross_section_id'] = pol_state
            cross_sections.append(_ws)
        except:
            logging.error("Could not filter %s: %s", pol_state, sys.exc_info()[1])

    return cross_sections
