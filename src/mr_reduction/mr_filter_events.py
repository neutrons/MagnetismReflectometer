# pylint: disable=bare-except, wrong-import-order, unused-argument
"""
Filter MR data and separate cross-section for compatibility with legacy software.
"""

# standard imports
import logging
import sys

# third party imports
import mantid.simpleapi as api

# mr_reduction imports
from mr_reduction.settings import ANA_STATE, ANA_VETO, POL_STATE, POL_VETO, TOF_BIN
from mr_reduction.simple_utils import SampleLogs


def get_tof_range(ws):
    """
    Determine TOF range from the data
    :param workspace ws: workspace to work with
    """
    sample_logs = SampleLogs(ws)
    sample_detector_distance = sample_logs.mean("SampleDetDis")
    source_sample_distance = sample_logs.mean("ModeratorSamDis")
    # Check units
    if sample_logs.property("SampleDetDis").units not in ["m", "meter"]:
        sample_detector_distance /= 1000.0
    if sample_logs.property("ModeratorSamDis").units not in ["m", "meter"]:
        source_sample_distance /= 1000.0

    source_detector_distance = source_sample_distance + sample_detector_distance

    h = 6.626e-34  # m^2 kg s^-1
    m = 1.675e-27  # kg
    wl = sample_logs["LambdaRequest"]
    chopper_speed = sample_logs["SpeedRequest1"]
    wl_offset = 0
    cst = source_detector_distance / h * m
    half_width = 3.2 / 2.0
    tof_min = cst * (wl + wl_offset * 60.0 / chopper_speed - half_width * 60.0 / chopper_speed) * 1e-4
    tof_max = cst * (wl + wl_offset * 60.0 / chopper_speed + half_width * 60.0 / chopper_speed) * 1e-4

    return [tof_min, tof_max]


def filter_cross_sections(file_path, events=True, histo=False):
    """
    Filter events according to polarization state.
    :param str file_path: file to read
    :param bool events: if True, an event nexus file will be written
    :param bool histo: if True, a histo nexus file will be written
    """
    cross_sections = {}
    cross_sections_histo = {}

    xs_list = api.MRFilterCrossSections(
        file_path, PolState=POL_STATE, AnaState=ANA_STATE, PolVeto=POL_VETO, AnaVeto=ANA_VETO
    )

    if len(xs_list) > 0:
        tof_min, tof_max = get_tof_range(xs_list[0])

    for workspace in xs_list:
        sample_logs = SampleLogs(workspace)
        if "cross_section_id" in sample_logs:
            entry = sample_logs["cross_section_id"]
        else:
            entry = "Off_Off"
            api.AddSampleLog(Workspace=workspace, LogName="cross_section_id", LogText=entry)
        if workspace.getNumberEvents() < 5:
            logging.warn("No events in %s", entry)
            continue

        run_number = workspace.getRunNumber()
        if events:
            events_file = "/tmp/filtered_%s_%s_%s.nxs" % (run_number, entry, "events")
            api.SaveNexus(InputWorkspace=workspace, Filename=events_file, Title="entry_%s" % entry)
            cross_sections["entry-%s" % entry] = events_file
        if histo:
            # tof_min = workspace.getTofMin()
            # tof_max = workspace.getTofMax()
            ws_binned = api.Rebin(
                InputWorkspace=workspace, Params="%s, %s, %s" % (tof_min, TOF_BIN, tof_max), PreserveEvents=False
            )
            histo_file = "/tmp/filtered_%s_%s_%s.nxs" % (run_number, entry, "histo")
            api.SaveNexus(InputWorkspace=ws_binned, Filename=histo_file, Title="entry_%s" % entry)
            cross_sections_histo["entry-%s" % entry] = histo_file

    return cross_sections, cross_sections_histo


def _filter_cross_sections(file_path):
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
    states = {"Off_Off": 15, "On_Off": 47, "Off_On": 31, "On_On": 63}
    cross_sections = {}
    workspace = api.LoadEventNexus(Filename=file_path, OutputWorkspace="raw_events")

    for pol_state in states:
        try:
            _ws = api.FilterByLogValue(
                InputWorkspace=workspace,
                LogName=state_log,
                TimeTolerance=0.1,
                MinimumValue=states[pol_state],
                MaximumValue=states[pol_state],
                LogBoundary="Left",
            )

            events_file = "/tmp/filtered_%s_%s.nxs" % (pol_state, "events")
            api.SaveNexus(InputWorkspace=_ws, Filename=events_file, Title="entry_%s" % pol_state)
            cross_sections["entry-%s" % pol_state] = events_file
        except:  # noqa E722
            logging.error("Could not filter %s: %s", pol_state, sys.exc_info()[1])

    return cross_sections, None
