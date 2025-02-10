"""
Polarization testing code, originally from Tim C.
"""

# standard imports
import sys
from typing import List

# third party imports
import mantid
import mantid.simpleapi as mantid_api

# mr_reduction imports
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
    states = {"-Off_Off": 15, "-On_Off": 47, "-Off_On": 31, "-On_On": 63}
    ordered_states = ["-Off_Off", "-On_Off", "-Off_On", "-On_On"]
    ws_list = []
    for s in ordered_states:
        try:
            mantid_api.FilterByLogValue(
                InputWorkspace=ws,
                LogName=state_log,
                TimeTolerance=0.1,
                OutputWorkspace="%s%s" % (str(ws), s),
                MinimumValue=states[s],
                MaximumValue=states[s],
                LogBoundary="Left",
            )
            ws_list.append("%s%s" % (str(ws), s))
        except:  # noqa E722
            print("Failed for %s %s" % (s, states[s]))
            print(sys.exc_value)

    return ws_list


def counts_in_roi(
    workspace: MantidWorkspace, wavelength_bin: float = 0.01, roi: List[int] = [162, 175, 112, 145]
) -> str:
    """
    Single spectrum of Counts vs wavelength for counts found in the ROI.

    Counts are normalized by proton charge, if sample-log gd_prtn_chrg exists.
    This function will overwrite the input workspace.

    Parameters
    ----------
    workspace
        Mantid workspace object or name
    wavelength_bin
        Wavelength bin width for rebinning the spectrum [default: 0.01]
    roi
        Rectangular Region Of Interest in the pixel detector bounded
        by pixel numbers [x_min, x_max, y_min, y_max]

    Returns
    -------
    The name of the input workspace, after being transformed into a single spectrum of counts vs wavelength.
    """
    workspace_name = str(workspace)
    if SampleLogs(workspace)["gd_prtn_chrg"] > 0:
        #  Divide intensities by the value stored in sample log "gd_prtn_chrg"
        mantid_api.NormaliseByCurrent(InputWorkspace=workspace_name, OutputWorkspace=workspace_name)
    mantid_api.ConvertUnits(InputWorkspace=workspace_name, Target="Wavelength", OutputWorkspace=workspace_name)
    mantid_api.Rebin(InputWorkspace=workspace_name, Params=wavelength_bin, OutputWorkspace=workspace_name)
    mantid_api.RefRoi(
        InputWorkspace=workspace_name,
        NXPixel=304,
        NYPixel=256,
        SumPixels=True,  # sum spectra over all pixels in the ROI
        NormalizeSum=False,  # do not divide by the number of pixels in the ROI
        XPixelMin=roi[0],
        XPIxelMax=roi[1],
        YPixelMin=roi[2],
        YPixelMax=roi[3],
        IntegrateY=True,
        ConvertToQ=False,
        OutputWorkspace=workspace_name,
    )
    mantid_api.SumSpectra(InputWorkspace=workspace_name, OutputWorkspace=workspace_name)
    return workspace_name


def calculate_ratios(workspace, delta_wl=0.01, roi=[1, 256, 1, 256], slow_filter=False):
    """
    CalcRatioSa calculates the flipping ratios and the SA (normalized difference) for a given file,
    run number, or workspace.
    """
    if slow_filter:
        wsg = filter_GetDI(workspace)
    else:
        from mr_reduction import settings

        wsg = mantid_api.MRFilterCrossSections(
            InputWorkspace=workspace,
            PolState=settings.POL_STATE,
            AnaState=settings.ANA_STATE,
            PolVeto=settings.POL_VETO,
            AnaVeto=settings.ANA_VETO,
        )

    ws_list = []
    ws_non_zero = []
    labels = []
    for item in wsg:
        if mantid.mtd[item].getNumberEvents() > 100:
            mantid.logger.notice("Cross-section %s: %s events" % (item, mantid.mtd[item].getNumberEvents()))
            ws_non_zero.append(item)
        s = counts_in_roi(workspace=item, wavelength_bin=delta_wl, roi=roi)
        ws_list.append(s)
    mantid.logger.notice("Cross-sections found: %s" % len(wsg))
    try:
        if len(ws_non_zero) >= 3:
            ratio1 = mantid_api.Divide(
                LHSWorkspace=ws_list[0], RHSWorkspace=ws_list[1], OutputWorkspace="r1_" + str(workspace)
            )
            ratio2 = mantid_api.Divide(
                LHSWorkspace=ws_list[0], RHSWorkspace=ws_list[2], OutputWorkspace="r2_" + str(workspace)
            )
            sum1 = mantid.mtd[ws_list[2]] - mantid.mtd[ws_list[0]]
            sum2 = mantid.mtd[ws_list[2]] + mantid.mtd[ws_list[0]]
            asym1 = mantid_api.Divide(LHSWorkspace=sum1, RHSWorkspace=sum2, OutputWorkspace="a2_" + str(workspace))
            labels = ["On_Off / On_On", "Off_On / Off_Off", "(Off_On - Off_Off) / (Off_On + Off_Off)"]
        elif len(ws_non_zero) == 2:
            ratio1 = mantid_api.Divide(
                LHSWorkspace=ws_non_zero[0], RHSWorkspace=ws_non_zero[1], OutputWorkspace="r1_" + str(workspace)
            )
            ratio2 = None
            sum1 = mantid.mtd[ws_list[1]] - mantid.mtd[ws_list[0]]
            sum2 = mantid.mtd[ws_list[1]] + mantid.mtd[ws_list[0]]
            asym1 = mantid_api.Divide(LHSWorkspace=sum1, RHSWorkspace=sum2, OutputWorkspace="a2_" + str(workspace))
            labels = ["Off_Off / On_Off", None, "(On_Off - Off_Off) / (On_Off + Off_Off)"]
        else:
            asym1 = None
            ratio1 = None
            ratio2 = None
            labels = None
    except:  # noqa E722
        mantid.logger.notice(str(sys.exc_info()[1]))

    if ratio1 is not None:
        mantid_api.CloneWorkspace(InputWorkspace=ratio1, OutputWorkspace="ratio1")
        ratio1 = mantid.mtd["ratio1"]
    if ratio2 is not None:
        mantid_api.CloneWorkspace(InputWorkspace=ratio2, OutputWorkspace="ratio2")
        ratio2 = mantid.mtd["ratio2"]
    if asym1 is not None:
        mantid_api.CloneWorkspace(InputWorkspace=asym1, OutputWorkspace="asym1")
        asym1 = mantid.mtd["asym1"]

    return ws_non_zero, ratio1, ratio2, asym1, labels
