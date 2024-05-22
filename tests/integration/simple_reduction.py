# standard imports
import os

import pytest

# third party packages
from mantid.api import WorkspaceGroup
from mantid.simpleapi import MagnetismReflectometryReduction, MRFilterCrossSections

# mr_reduction imports
from mr_reduction.data_info import DataInfo


def extract_data_info(xs_list: WorkspaceGroup) -> DataInfo:
    r"""Extract data info for the cross-section with the most events"""
    n_max_events = 0
    i_main = 0
    for i in range(len(xs_list)):
        n_events = xs_list[i].getNumberEvents()
        if n_events > n_max_events:
            n_max_events = n_events
            i_main = i

    entry = xs_list[i_main].getRun().getProperty("cross_section_id").value
    return DataInfo(xs_list[i_main], entry)


@pytest.mark.datarepo()
def test_reduction_simple(data_server):
    # Directory containing test data for the MR upgrade
    # data_dir = "/SNS/REF_M/shared/ADARA.Test.Data.2018/"

    # file_path = data_dir + 'REF_M_25647.nxs.h5' # single xs
    # file_path =  data_dir + 'REF_M_25631.nxs.h5' # four xs
    # file_path = os.path.join(data_dir, "REF_M_28142.nxs.h5")  # 3 xs
    file_path = data_server.path_to("REF_M_28142.nxs.h5")
    # file_path = "/SNS/REF_M/IPTS-16469/0/25631/NeXus/REF_M_25631_event.nxs"

    # Extract a workspace for each cross-section
    wsg = MRFilterCrossSections(Filename=file_path)

    # Extract peaks and such from the cross-section with the highest counts
    data_info = extract_data_info(wsg)

    apply_norm = False
    direct_info = data_info
    MagnetismReflectometryReduction(
        InputWorkspace=wsg,
        NormalizationRunNumber=0,
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
        UseSANGLE=True,
        TimeAxisRange=data_info.tof_range,
        SpecularPixel=data_info.peak_position,
        ConstantQBinning=False,
        OutputWorkspace="r_%s" % data_info.run_number,
    )


if __name__ == "__main__":
    pytest.main([__file__])
