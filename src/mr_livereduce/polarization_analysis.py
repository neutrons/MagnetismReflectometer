"""
Polarization testing code, originally from Tim C.
"""

# standard imports
import sys
from typing import List, Union

# third party imports
import mantid
import mantid.simpleapi as api

# mr_reduction imports
from mr_reduction import settings as reduction_settings
from mr_reduction.filter_events import split_events
from mr_reduction.simple_utils import SampleLogs
from mr_reduction.types import MantidWorkspace


def filter_GetDI(ws):
    """
    Test filtering
    BL4A:SF:ICP:getDI

    015 (0000 1111): SF1=OFF, SF2=OFF, SF1Veto=OFF, SF2Veto=OFF
    047 (0010 1111): SF1=ON, SF2=OFF, SF1Veto=OFF, SF2Veto=OFF
    031 (0001 1111): SF1=OFF, SF2=ON, SF1Veto=OFF, SF2Veto=OFF
    063 (0011 1111): SF1=ON, SF2=ON, SF1Veto=OFF, SF2Veto=OFF
    """
    state_log = "BL4A:SF:ICP:getDI"
    states = {"Off_Off": 15, "On_Off": 47, "Off_On": 31, "On_On": 63}
    cross_sections = list(states.keys())
    ws_list = []
    for cross_section in cross_sections:
        try:
            output_workspace = f"{str(ws)}-{cross_section}"
            api.FilterByLogValue(
                InputWorkspace=ws,
                LogName=state_log,
                TimeTolerance=0.1,
                OutputWorkspace=output_workspace,
                MinimumValue=states[cross_section],
                MaximumValue=states[cross_section],
                LogBoundary="Left",
            )
            ws_list.append(output_workspace)
        except Exception as exception:  # noqa E722
            mantid.logger.error(f"Failed for {cross_section} {states[cross_section]}")
            mantid.logger.error(exception)

    return ws_list


def calculate_ratios(
    workspace: MantidWorkspace,
    delta_wl: Union[float, str] = 0.01,
    roi: List[float] = [1, 256, 1, 256],
    slow_filter: bool = False,
):
    """
    CalcRatioSa calculates the flipping ratios and the SA (normalized difference) for a given file,
    run number, or workspace.

    Parameters
    ----------
    workspace : MantidWorkspace
        The input workspace to calculate the ratios and SA.
    delta_wl : float, optional
        The wavelength bin width for rebinning, in Angstroms. Default is 0.01.
    roi : list, optional
        The region of interest (ROI) in the detector as [x_min, x_max, y_min, y_max],
        defining the pixel coordinates (x_min, y_min) and (x_max, y_max) of two opposite corners
        of the rectangular ROI. Default is [1, 256, 1, 256], which encompasses the entire detector.
    slow_filter : bool, optional
        If True, use the polarization/analyzer filtering method appropriate for pre-EPICS upgrade. Default is False.
    """
    if slow_filter:
        workspace_group = filter_GetDI(workspace)
    else:
        workspace_group = split_events(input_workspace=workspace)

    ws_list = []
    ws_non_zero = []
    labels = []
    for workspace in workspace_group:
        event_count = mantid.mtd[workspace].getNumberEvents()
        if event_count > 100:
            mantid.logger.notice(f"Cross-section {workspace}: {event_count} events")
            ws_non_zero.append(workspace)
        intensities: MantidWorkspace = intensities_in_roi_pixels(workspace=workspace, step=delta_wl, roi=roi)
        ws_list.append(intensities)

    try:
        if len(ws_non_zero) >= 3:  # the experiment used both polarizer and anaylizer
            ratio1 = api.Divide(
                LHSWorkspace=ws_list[0], RHSWorkspace=ws_list[1], OutputWorkspace="r1_" + str(workspace)
            )
            ratio2 = api.Divide(
                LHSWorkspace=ws_list[0], RHSWorkspace=ws_list[2], OutputWorkspace="r2_" + str(workspace)
            )
            sum1 = mantid.mtd[ws_list[2]] - mantid.mtd[ws_list[0]]
            sum2 = mantid.mtd[ws_list[2]] + mantid.mtd[ws_list[0]]
            asym1 = api.Divide(LHSWorkspace=sum1, RHSWorkspace=sum2, OutputWorkspace="a2_" + str(workspace))
            labels = ["On_Off / On_On", "Off_On / Off_Off", "(Off_On - Off_Off) / (Off_On + Off_Off)"]
        elif len(ws_non_zero) == 2:
            ratio1 = api.Divide(
                LHSWorkspace=ws_non_zero[0], RHSWorkspace=ws_non_zero[1], OutputWorkspace="r1_" + str(workspace)
            )
            ratio2 = None
            sum1 = mantid.mtd[ws_list[1]] - mantid.mtd[ws_list[0]]
            sum2 = mantid.mtd[ws_list[1]] + mantid.mtd[ws_list[0]]
            asym1 = api.Divide(LHSWorkspace=sum1, RHSWorkspace=sum2, OutputWorkspace="a2_" + str(workspace))
            labels = ["Off_Off / On_Off", None, "(On_Off - Off_Off) / (On_Off + Off_Off)"]
        else:
            asym1 = None
            ratio1 = None
            ratio2 = None
            labels = None
    except:  # noqa E722
        mantid.logger.notice(str(sys.exc_info()[1]))

    if ratio1 is not None:
        api.CloneWorkspace(InputWorkspace=ratio1, OutputWorkspace="ratio1")
        ratio1 = mantid.mtd["ratio1"]
    if ratio2 is not None:
        api.CloneWorkspace(InputWorkspace=ratio2, OutputWorkspace="ratio2")
        ratio2 = mantid.mtd["ratio2"]
    if asym1 is not None:
        api.CloneWorkspace(InputWorkspace=asym1, OutputWorkspace="asym1")
        asym1 = mantid.mtd["asym1"]

    return ws_non_zero, ratio1, ratio2, asym1, labels


def intensities_in_roi_pixels(
    workspace: MantidWorkspace, step: Union[float, str] = "0.01", roi: list[float] = [162, 175, 112, 145]
) -> MantidWorkspace:
    """
    Returns a spectrum of normalized intensities (Counts/proton_charge) vs wavelength for
    each pixel in the specified region of interest (ROI) in the detector.

    Parameters
    ----------
    workspace : str
        Mantid workspace name.
    step : float
        Wavelength bin width for rebinning, in Angstroms.
    roi : list
        [x_min, x_max, y_min, y_max] defines the pixel coordinates (x_min, y_min) and (x_max, y_max)
        of two opposite corners of the rectangular ROI.

    Returns
    -------
    Name of the processed Mantid workspace, one spectrum per pixel in the ROI.
    """
    workspace_name = str(workspace)
    if SampleLogs(workspace)["gd_prtn_chrg"] > 0:
        api.NormaliseByCurrent(InputWorkspace=workspace_name, OutputWorkspace=workspace_name)
    api.ConvertUnits(InputWorkspace=workspace_name, Target="Wavelength", OutputWorkspace=workspace_name)
    api.Rebin(InputWorkspace=workspace_name, Params=str(step), OutputWorkspace=workspace_name)
    api.RefRoi(
        InputWorkspace=workspace_name,
        NXPixel=304,
        NYPixel=256,
        SumPixels=True,
        XPixelMin=roi[0],
        XPIxelMax=roi[1],
        YPixelMin=roi[2],
        YPixelMax=roi[3],
        IntegrateY=True,
        ConvertToQ=False,
        OutputWorkspace=workspace_name,
    )
    api.SumSpectra(InputWorkspace=workspace_name, OutputWorkspace=workspace_name)
    return workspace_name
