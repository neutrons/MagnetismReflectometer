# standard library imports
import os
from typing import List

# third-party imports
import pytest
from mantid.simpleapi import LoadNexusProcessed, mtd

# mr_reduction imports
from mr_reduction.io_orso import save_cross_sections
from numpy.testing import assert_almost_equal
from orsopy.fileio.base import Column, ErrorColumn
from orsopy.fileio.orso import Orso, OrsoDataset, load_orso


def assert_columns(datasets: List[OrsoDataset]):
    """Test-helper function, assert that each dataset in the list has the expected columns"""
    for dataset in datasets:
        info: Orso = dataset.info
        assert len(info.columns) == 6
        for i, (label, coltype) in enumerate(
            [
                ("Qz", Column),
                ("R", Column),
                ("sR", ErrorColumn),
                ("sQz", ErrorColumn),
                ("theta", Column),
                ("stheta", ErrorColumn),
            ]
        ):
            assert isinstance(info.columns[i], coltype)
            assert info.columns[i].name == label


def assert_instrument_settings(datasets: List[OrsoDataset], thetas, wavelengths, polarizations):
    """Test-helper function, assert that each dataset in the list has the expected instrument settings"""
    for i, dataset in enumerate(datasets):
        info: Orso = dataset.info
        instrument_settings = info.data_source.measurement.instrument_settings
        assert_almost_equal(instrument_settings.incident_angle.magnitude, thetas[i], decimal=3)
        assert_almost_equal(instrument_settings.wavelength.min, wavelengths[i], decimal=3)
        assert instrument_settings.polarization.value == polarizations[i]


def test_save_cross_sections_output_file_extension():
    with pytest.raises(ValueError, match="Output file must have .ort extension"):
        save_cross_sections([], "output_file")


@pytest.mark.datarepo()
def test_save_cross_sections_single_cross_section(mock_filesystem, data_server):
    """write a single cross-section workspace to an ORSO file and check its contents"""
    reflectivity_workspace = LoadNexusProcessed(data_server.path_to("REF_M_29160_2_Off_Off_autoreduce.nxs.h5"))
    output_file = os.path.join(mock_filesystem.tempdir, "REF_M_29160_2_Off_Off_autoreduce.ort")
    save_cross_sections([reflectivity_workspace], output_file)
    #
    # load the ORSO file and check its contents
    #
    datasets: List[OrsoDataset] = load_orso(output_file)
    assert len(datasets) == 1
    assert_columns(datasets)
    assert_instrument_settings(datasets, thetas=[0.015], wavelengths=[2.7], polarizations=["pp"])


@pytest.mark.datarepo()
def test_save_cross_sections_run_cross_sections(mock_filesystem, data_server):
    workspace_list = []
    for cross_section in ["Off_Off", "On_Off"]:
        workspace = mtd.unique_hidden_name()
        LoadNexusProcessed(
            Filename=data_server.path_to(f"REF_M_42535_1_{cross_section}_autoreduce.nxs.h5"), OutputWorkspace=workspace
        )
        workspace_list.append(workspace)
    output_file = os.path.join(mock_filesystem.tempdir, "REF_M_29160_2_Off_Off_autoreduce.ort")
    save_cross_sections(workspace_list, output_file)
    #
    # load the ORSO file and check its contents
    #
    datasets: List[OrsoDataset] = load_orso(output_file)
    assert len(datasets) == 2
    assert set([dataset.info.data_set for dataset in datasets]) == {"Off_Off", "On_Off"}
    assert [dataset.data.shape for dataset in datasets] == [(52, 6), (52, 6)]
    assert_columns(datasets)
    assert_instrument_settings(datasets, thetas=[0.007, 0.007], wavelengths=[2.55, 2.55], polarizations=["po", "mo"])


if __name__ == "__main__":
    pytest.main([__file__])
