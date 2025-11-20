"""
This module contains integration tests for the simple reduction of a REF_M run.

The main test, `test_reduction_simple`, verifies the reduction process for 28142 by:
1. Setting up the data server to provide the necessary data file.
2. Extracting workspaces for each cross-section using `filter_events.get_xs_list`.
3. Extracting data information for the cross-section with the highest counts.
4. Reduce using `mantid.simpleapi.MagnetismReflectometryReduction` with the extracted data information.
5. Asserting the successful completion of the reduction process.

The test relies on the `data_server` fixture.
"""

import pytest
from mantid.api import WorkspaceGroup
from mantid.simpleapi import MagnetismReflectometryReduction, mtd

from mr_reduction.data_info import DataInfo
from mr_reduction.filter_events import get_xs_list


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


@pytest.mark.datarepo
def test_reduction_simple(data_server):
    wsg = get_xs_list(
        file_path=data_server.path_to("REF_M_28142.nxs.h5"),  # three cross-sections
        output_workspace=mtd.unique_hidden_name(),
    )

    data_info = extract_data_info(wsg)  # Extract peaks and such from the cross-section with the highest counts
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
