"""
    Polarization testing code, originally from Tim C.
"""
import sys
import mantid
import mantid.simpleapi as api


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
    states = {'-Off_Off': 15,
              '-On_Off': 47,
              '-Off_On': 31,
              '-On_On': 63}
    ordered_states = ['-Off_Off', '-On_Off', '-Off_On', '-On_On']
    ws_list = []
    for s in ordered_states:
        try:
            api.FilterByLogValue(InputWorkspace=ws, LogName=state_log, TimeTolerance=0.1, OutputWorkspace='%s%s' % (str(ws), s),
                                 MinimumValue=states[s], MaximumValue=states[s], LogBoundary='Left')
            ws_list.append('%s%s' % (str(ws), s))
        except:
            mantid.logger.error("Failed for %s %s" % (s, states[s]))
            mantid.logger.error(str(sys.exc_value))

    return ws_list

def calculate_ratios(workspace, delta_wl=0.01, roi=[1,256,1,256], slow_filter=False, normalize=True):
    """
        CalcRatioSa calculates the flipping ratios and the SA (normalized difference) for a given file,
        run number, or workspace.
    """
    if slow_filter:
        wsg = filter_GetDI(workspace)
    else:
        from mr_reduction import settings
        wsg = api.MRFilterCrossSections(InputWorkspace=workspace,
                                        PolState=settings.POL_STATE,
                                        AnaState=settings.ANA_STATE,
                                        PolVeto=settings.POL_VETO,
                                        AnaVeto=settings.ANA_VETO)

    ws_list = []
    ws_non_zero = []
    labels = []
    for item in wsg:
        if mantid.mtd[item].getNumberEvents() > 0:
            mantid.logger.notice("Cross-section %s: %s events" % (item, mantid.mtd[item].getNumberEvents()))
            ws_non_zero.append(item) 
        s = extract_roi(workspace=item, step=delta_wl , roi=roi, normalize=normalize)
        ws_list.append(s)
    try:
        if len(ws_non_zero) == 4:
            ratio1 = api.Divide(LHSWorkspace=ws_list[1], RHSWorkspace=ws_list[3], OutputWorkspace='r1_'+str(workspace))
            ratio2 = api.Divide(LHSWorkspace=ws_list[2], RHSWorkspace=ws_list[0], OutputWorkspace='r2_'+str(workspace))
            sum1 = mantid.mtd[ws_list[2]] - mantid.mtd[ws_list[0]]
            sum2 = mantid.mtd[ws_list[2]] + mantid.mtd[ws_list[0]]
            asym1 = api.Divide(LHSWorkspace=sum1, RHSWorkspace=sum2, OutputWorkspace='a2_'+str(workspace))
            labels = ["On_Off / On_On", "Off_On / Off_Off", "(Off_On - Off_Off) / (Off_On + Off_Off)"]
        elif len(ws_non_zero) == 2:
            ratio1 = api.Divide(LHSWorkspace=ws_non_zero[0], RHSWorkspace=ws_non_zero[1], OutputWorkspace='r1_'+str(workspace))
            ratio2 = None
            asym1 = None
            labels = ["Off_Off / On_Off", None, None]
        else:
            asym1 = None
            ratio1 = None
            ratio2 = None
            labels = None
    except:
        mantid.logger.notice(str(sys.exc_value))

    return ws_non_zero, ratio1, ratio2, asym1, labels

def extract_roi(workspace, step='0.01', roi=[162,175,112,145], normalize=True):
    """
        Returns a spectrum (Counts/proton charge vs lambda) given a filename
        or run number and the lambda step size and the corner of the ROI.

        :param str workspace: Mantid workspace name
        :param float step: wavelength bin width for rebinning
        :param list roi: [x_min, x_max, y_min, y_max] pixels
    """
    _workspace = str(workspace)
    if normalize and mantid.mtd[_workspace].getRun()['gd_prtn_chrg'].value > 0:
        api.NormaliseByCurrent(InputWorkspace=_workspace, OutputWorkspace=_workspace)
    api.ConvertUnits(InputWorkspace=_workspace, Target='Wavelength', OutputWorkspace=_workspace)
    api.Rebin(InputWorkspace=_workspace, Params=step, OutputWorkspace=_workspace)
    api.RefRoi(InputWorkspace=_workspace, NXPixel=304, NYPixel=256, SumPixels=True,
               XPixelMin=roi[0], XPIxelMax=roi[1], YPixelMin=roi[2], YPixelMax=roi[3],
               IntegrateY=True, ConvertToQ=False, OutputWorkspace=_workspace)
    api.SumSpectra(InputWorkspace=_workspace, OutputWorkspace=_workspace)
    return _workspace
