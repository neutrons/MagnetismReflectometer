# standard library imports
import os
from operator import itemgetter
from typing import List

# third-party imports
from mantid.api import (
    AnalysisDataService,
    FileAction,
    FileProperty,
    PropertyMode,
    PythonAlgorithm,
    WorkspaceGroupProperty,
    WorkspaceProperty,
)
from mantid.kernel import Direction
from mantid.simpleapi import (
    AddSampleLog,
    CreateEmptyTableWorkspace,
    FilterEvents,
    GenerateEventsFilter,
    GroupWorkspaces,
    LoadEventNexus,
    logger,
    mtd,
)

# mr_reduction imports
from mr_reduction.settings import ANA_STATE, ANA_VETO, POL_STATE, POL_VETO
from mr_reduction.simple_utils import SampleLogs, workspace_handle
from mr_reduction.types import EventWorkspace, MantidWorkspace, WorkspaceGroup


def extract_times(times, is_start, is_sf1=False, is_sf2=False, is_veto1=False, is_veto2=False):
    """
    Extract a list of times
    """
    return [(times[i], is_start, [is_sf1, is_sf2, is_veto1, is_veto2]) for i in range(len(times))]


def load_legacy_cross_Sections(file_path: str, output_workspace: str) -> WorkspaceGroup:
    """
    For legacy MR data, load each cross-section independently.

    Parameters
    ----------
    file_path : str
        Path to the legacy Nexus file.
    output_workspace : str
        Name of the output GroupWorkspace to group the cross-sections.

    Returns
    -------
    mantid.api.WorkspaceGroup
        A workspace group containing the loaded cross-sections.
    """
    ws_base_name = os.path.basename(file_path)
    cross_sections: List[EventWorkspace] = list()

    for entry in ["Off_Off", "On_Off", "Off_On", "On_On"]:
        try:
            ws_name = "%s_%s" % (ws_base_name, entry)
            ws = LoadEventNexus(Filename=file_path, NXentryName="entry-%s" % entry, OutputWorkspace=ws_name)
            AddSampleLog(Workspace=ws, LogName="cross_section_id", LogText=entry)
            cross_sections.append(ws_name)
        except:  # noqa E722
            logger.information("Could not load %s from legacy data file" % entry)

    return GroupWorkspaces(InputWorkspaces=cross_sections, OutputWorkspace=output_workspace)


def create_table(change_list, start_time, has_polarizer=True, has_analyzer=True) -> MantidWorkspace:
    split_table_ws = CreateEmptyTableWorkspace()
    split_table_ws.addColumn("float", "start")
    split_table_ws.addColumn("float", "stop")
    split_table_ws.addColumn("str", "target")

    current_state = [False, False, False, False]
    current_state_t0 = 0

    # Keep track of when we have a fully specified state
    specified = [not has_polarizer, not has_analyzer]

    for item in change_list:
        # We have a change of state, add an entry for the state that just ended
        if specified[0] and specified[1] and not current_state[2] and not current_state[3]:
            xs = "%s_%s" % ("On" if current_state[0] else "Off", "On" if current_state[1] else "Off")
            start = int(current_state_t0 - start_time)
            stop = item[0] - start_time
            if start < 0 and stop <= 0:
                continue  # don't consider time-windows before the start time
            if start < 0 < stop:
                start = 0.0  # keep only the fragment of the time-window after the start time
            split_table_ws.addRow([start * 1e-9, stop * 1e-9, xs])

        # Now update the current state
        for i in range(len(current_state)):
            if item[2][i]:
                if i < 2:
                    specified[i] = True
                current_state[i] = item[1]
        current_state_t0 = item[0]
    return split_table_ws


def filter_cross_sections(
    events_workspace: EventWorkspace,
    output_workspace: str,
    pv_polarizer_state: str = POL_STATE,
    pv_analyzer_state: str = ANA_STATE,
    pv_polarizer_veto: str = POL_VETO,
    pv_analyzer_veto: str = ANA_VETO,
    check_devices: bool = True,
) -> WorkspaceGroup:
    """
    Filter events according to the polarization states
    :param str file_path: data file path
    """
    sample_logs = SampleLogs(events_workspace)
    if check_devices is True:
        polarizer = sample_logs["Polarizer"]
        analyzer = sample_logs["Analyzer"]
    else:
        polarizer = 1  # assume a polarizer of type "1" is enabled in the experiment
        analyzer = 1  # assume an analyzer of type "1" is enabled in the experiment

    change_list = []

    if polarizer > 0:
        # SF1 ON
        splitws, _ = GenerateEventsFilter(
            InputWorkspace=events_workspace,
            LogName=pv_polarizer_state,
            MinimumLogValue=0.99,
            MaximumLogValue=1.01,
            TimeTolerance=0,
            OutputWorkspace="filter",
            InformationWorkspace="filter_info",
            LogBoundary="Left",
            UnitOfTime="Seconds",
        )
        time_dict = splitws.toDict()
        change_list.extend(extract_times(time_dict["start"], is_start=True, is_sf1=True))
        change_list.extend(extract_times(time_dict["stop"], is_start=False, is_sf1=True))

        # SF1 OFF
        splitws, _ = GenerateEventsFilter(
            InputWorkspace=events_workspace,
            LogName=pv_polarizer_state,
            MinimumLogValue=-0.01,
            MaximumLogValue=0.01,
            TimeTolerance=0,
            OutputWorkspace="filter",
            InformationWorkspace="filter_info",
            LogBoundary="Left",
            UnitOfTime="Seconds",
        )
        time_dict = splitws.toDict()
        change_list.extend(extract_times(time_dict["start"], is_start=False, is_sf1=True))
        change_list.extend(extract_times(time_dict["stop"], is_start=True, is_sf1=True))

        # SF1 VETO
        if pv_polarizer_veto != "":
            splitws, _ = GenerateEventsFilter(
                InputWorkspace=events_workspace,
                LogName=pv_polarizer_veto,
                MinimumLogValue=0.99,
                MaximumLogValue=1.01,
                TimeTolerance=0,
                OutputWorkspace="filter",
                InformationWorkspace="filter_info",
                LogBoundary="Left",
                UnitOfTime="Seconds",
            )
            time_dict = splitws.toDict()
            change_list.extend(extract_times(time_dict["start"], is_start=True, is_veto1=True))
            change_list.extend(extract_times(time_dict["stop"], is_start=False, is_veto1=True))

    if analyzer > 0:
        # SF2 ON
        splitws, _ = GenerateEventsFilter(
            InputWorkspace=events_workspace,
            LogName=pv_analyzer_state,
            MinimumLogValue=0.99,
            MaximumLogValue=1.01,
            TimeTolerance=0,
            OutputWorkspace="filter",
            InformationWorkspace="filter_info",
            LogBoundary="Left",
            UnitOfTime="Seconds",
        )
        time_dict = splitws.toDict()
        change_list.extend(extract_times(time_dict["start"], is_start=True, is_sf2=True))
        change_list.extend(extract_times(time_dict["stop"], is_start=False, is_sf2=True))

        # SF2 OFF
        splitws, _ = GenerateEventsFilter(
            InputWorkspace=events_workspace,
            LogName=pv_analyzer_state,
            MinimumLogValue=-0.01,
            MaximumLogValue=0.01,
            TimeTolerance=0,
            OutputWorkspace="filter",
            InformationWorkspace="filter_info",
            LogBoundary="Left",
            UnitOfTime="Seconds",
        )
        time_dict = splitws.toDict()
        change_list.extend(extract_times(time_dict["start"], is_start=False, is_sf2=True))
        change_list.extend(extract_times(time_dict["stop"], is_start=True, is_sf2=True))

        # SF2 VETO
        if not pv_analyzer_veto == "":
            splitws, _ = GenerateEventsFilter(
                InputWorkspace=events_workspace,
                LogName=pv_analyzer_veto,
                MinimumLogValue=0.99,
                MaximumLogValue=1.01,
                TimeTolerance=0,
                OutputWorkspace="filter",
                InformationWorkspace="filter_info",
                LogBoundary="Left",
                UnitOfTime="Seconds",
            )
            time_dict = splitws.toDict()
            change_list.extend(extract_times(time_dict["start"], is_start=True, is_veto2=True))
            change_list.extend(extract_times(time_dict["stop"], is_start=False, is_veto2=True))

    start_time = events_workspace.run().startTime().totalNanoseconds()

    change_list = sorted(change_list, key=itemgetter(0))
    split_table_ws = create_table(change_list, start_time, has_polarizer=(polarizer > 0), has_analyzer=(analyzer > 0))

    if split_table_ws.rowCount() > 0:
        # Filter events with the split table
        correction_workspace = mtd.unique_hidden_name()  # temporary workspace for the TOF correction
        outputs = FilterEvents(
            InputWorkspace=events_workspace,
            SplitterWorkspace=split_table_ws,
            GroupWorkspaces=True,
            FilterByPulseTime=False,
            OutputWorkspaceIndexedFrom1=False,
            CorrectionToSample="None",
            SpectrumWithoutDetector="Skip",
            SplitSampleLogs=True,
            RelativeTime=True,
            ExcludeSpecifiedLogs=True,
            OutputTOFCorrectionWorkspace=correction_workspace,
            OutputWorkspaceBaseName=output_workspace,
        )
        AnalysisDataService.remove(correction_workspace)
        for ws in outputs[-1]:
            cross_section_id = str(ws).replace(output_workspace + "_", "")  # e.g. "12345_On_On" becomes "On_On"
            AddSampleLog(Workspace=ws, LogName="cross_section_id", LogText=cross_section_id)
    elif polarizer <= 0 and analyzer <= 0:
        # If we don't have a splitter table, it might be because we don't have analyzer/polarizer
        # information. In this case don't filter and return the raw workspace.
        logger.warning("No polarizer/analyzer information available")
        GroupWorkspaces([events_workspace], OutputWorkspace=output_workspace)
    else:
        raise RuntimeError("No events remained after filtering!")
    return workspace_handle(output_workspace)


def split_events(
    file_path: str = None,
    input_workspace: MantidWorkspace = None,
    pv_polarizer_state: str = POL_STATE,
    pv_analyzer_state: str = ANA_STATE,
    pv_polarizer_veto: str = POL_VETO,
    pv_analyzer_veto: str = ANA_VETO,
    check_devices: bool = True,
    output_workspace: str = None,
) -> WorkspaceGroup:
    if (file_path is None) and (input_workspace is None):
        raise ValueError("Either file_path or input_workspace must be provided")

    if (file_path is not None) and file_path.endswith(".nxs"):
        return load_legacy_cross_Sections(file_path, output_workspace)
    else:
        # if user provides both file_path and input_workspace, use the input_workspace
        if input_workspace is None:
            # load data file into a temporary workspace
            events_workspace = LoadEventNexus(Filename=file_path, OutputWorkspace=mtd.unique_hidden_name())
        else:
            events_workspace = workspace_handle(input_workspace)
        filter_cross_sections(
            events_workspace,
            output_workspace,
            pv_polarizer_state=pv_polarizer_state,
            pv_analyzer_state=pv_analyzer_state,
            pv_polarizer_veto=pv_polarizer_veto,
            pv_analyzer_veto=pv_analyzer_veto,
            check_devices=check_devices,
        )
        if input_workspace is None:
            AnalysisDataService.remove(str(events_workspace))
        return workspace_handle(output_workspace)
