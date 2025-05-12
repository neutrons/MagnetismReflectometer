# standard library imports
import os
from copy import deepcopy
from typing import List
from unittest import mock

import numpy as np

# third-party imports
import pytest
from mantid.simpleapi import LoadNexusProcessed, mtd
from numpy.testing import assert_almost_equal
from orsopy.fileio.base import Column, ErrorColumn
from orsopy.fileio.orso import Orso, OrsoDataset, load_orso

# mr_reduction imports
from mr_reduction.io_orso import SequenceDataSet, concatenate_runs, save_cross_sections


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


@pytest.mark.datarepo
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


@pytest.mark.datarepo
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


@pytest.fixture
def mock_runpeak_datasets():
    dataset1, dataset2 = mock.Mock(), mock.Mock()
    dataset1.info.data_set, dataset2.info.data_set = "Off_Off", "On_Off"
    dataset1.info.columns = ["Qz", "R", "sR"]
    dataset1.data = np.array([[42, 1.0, 0.1]])  # only one row, containing Qz, R, sR
    dataset2.data = np.array([[43, 2.0, 0.2]])
    dataset2.info.columns = ["Qz", "R", "sR"]
    return [dataset1, dataset2]


class TestSequenceDataSet:
    def test_initialization_empty(self):
        sequence = SequenceDataSet()
        assert sequence.cross_sections is None
        assert sequence.runpeaks is None
        assert sequence.datasets == {}

    def test_load_runpeak(self, mock_runpeak_datasets):
        sequence = SequenceDataSet()
        with mock.patch("mr_reduction.io_orso.load_orso") as mock_load_orso:
            # Mock the return value of load_orso
            mock_load_orso.return_value = mock_runpeak_datasets
            sequence.load_runpeak("1234", "path/to/orso/file")
            assert sequence.runpeaks == ["1234"]
            assert sequence.cross_sections == ["Off_Off", "On_Off"]
            assert sequence.datasets["1234"] == mock_runpeak_datasets
        with pytest.raises(AssertionError, match="Runpeak 1234 already loaded"):
            sequence.load_runpeak("1234", "path/to/orso/file")

    def test_getitem(self):
        sequence = SequenceDataSet()
        sequence.datasets = {"1234": ["1234_Off_Off", "1234_On_Off"], "1235": ["1235_Off_Off", "1235_On_Off"]}
        sequence._cross_sections = ["Off_Off", "On_Off"]
        sequence.runpeaks = ["1234", "1235"]
        # fetch a runpeak
        assert sequence["1234"] == ["1234_Off_Off", "1234_On_Off"]
        assert sequence["1235"] == ["1235_Off_Off", "1235_On_Off"]
        # fetch a cross-section
        assert sequence["Off_Off"] == ["1234_Off_Off", "1235_Off_Off"]
        assert sequence["On_Off"] == ["1234_On_Off", "1235_On_Off"]

    def test_is_compatible(self, mock_runpeak_datasets):
        sequence = SequenceDataSet()
        assert sequence.is_compatible(mock_runpeak_datasets)
        sequence._cross_sections = ["Off_Off"]  # only one cross-section
        assert sequence.is_compatible(mock_runpeak_datasets) is False  # two datasets but only one cross-section
        sequence._cross_sections = ["Off_Off", "On_On"]
        assert sequence.is_compatible(mock_runpeak_datasets) is False  # datasets' cross-sections don't match
        sequence._cross_sections = ["Off_Off", "On_Off"]
        assert sequence.is_compatible(mock_runpeak_datasets)  # datasets' cross-sections match
        sequence._cross_sections = ["On_Off", "Off_Off"]
        assert sequence.is_compatible(mock_runpeak_datasets) is True  # different order of cross-sections

    def test_sort(self, mock_runpeak_datasets):
        dataset1, dataset2 = mock_runpeak_datasets
        sequence = SequenceDataSet()
        sequence.runpeaks = ["1234", "1235"]  # initial order
        sequence.datasets = {"1234": [dataset2], "1235": [dataset1]}  # dataset2 has bigger Qz-min than dataset1
        sequence.sort()  # sort runpeaks by Qz-min
        assert sequence.runpeaks == ["1235", "1234"]  # sorted order

    def test_scale_intensities(self, mock_runpeak_datasets):
        dataset1, dataset2 = mock_runpeak_datasets
        sequence = SequenceDataSet()
        sequence.runpeaks = ["1235", "1234"]
        sequence.datasets = {"1234": [dataset1], "1235": [dataset2]}
        sequence.scale_intensities({"1234": 2.0, "1235": 4.0})
        assert_almost_equal(sequence["1234"][0].data, np.array([[42, 2.0, 0.2]]), decimal=3)
        assert_almost_equal(sequence["1235"][0].data, np.array([[43, 8.0, 0.8]]), decimal=3)

    def test_concatenate(self, mock_runpeak_datasets):
        dataset1, dataset2 = mock_runpeak_datasets
        sequence = SequenceDataSet()
        sequence.runpeaks = ["1234", "1235"]
        sequence._cross_sections = ["Off_Off", "On_Off"]
        sequence.datasets = {"1234": [dataset1, dataset2], "1235": [dataset1, dataset2]}
        datasets = sequence.concatenate()
        assert_almost_equal(datasets[0].data, np.array([[42, 1.0, 0.1], [42, 1.0, 0.1]]), decimal=3)
        assert datasets[0].info.data_set == "Off_Off"
        assert_almost_equal(datasets[1].data, np.array([[43, 2.0, 0.2], [43, 2.0, 0.2]]), decimal=3)
        assert datasets[1].info.data_set == "On_Off"


def test_concatenate_runs(mock_runpeak_datasets):
    def _load_orso_mock(filepath: str):
        match filepath:
            case "path/to/1234.ort":  # has Qz_min == 43
                dataset1, dataset2 = mock_runpeak_datasets
                dataset1.data = np.array([[43, 1.0, 0.1]])  # dataset for "Off_Off"
                dataset2.data = np.array([[43, 2.0, 0.2]])  # dataset for "On_Off"
                return [dataset1, dataset2]
            case "path/to/1235.ort":  # has Qz_min == 42, should go first when concatenating
                dataset1, dataset2 = [deepcopy(dataset) for dataset in mock_runpeak_datasets]
                dataset1.data = np.array([[42, 3.0, 0.3]])  # dataset for "Off_Off"
                dataset2.data = np.array([[42, 4.0, 0.4]])  # dataset for "On_Off"
                return [dataset1, dataset2]

    def _OrsoDataSet_mock(info, data):
        dataset = mock.Mock()
        dataset.info = info
        dataset.data = data
        return dataset

    with mock.patch("mr_reduction.io_orso.load_orso", new=_load_orso_mock):
        with mock.patch("mr_reduction.io_orso.OrsoDataset", new=_OrsoDataSet_mock):
            with mock.patch("mr_reduction.io_orso.save_orso") as save_orso_mock:
                save_orso_mock.return_value = None
                datasets = concatenate_runs(
                    filepath_sequence={"1234": "path/to/1234.ort", "1235": "path/to/1235.ort"},
                    concatenated_filepath="concatenated.ort",
                    scaling_factors={"1234": 2.0, "1235": 1.0},
                )
                assert [datasets[0].info.data_set, datasets[1].info.data_set] == ["Off_Off", "On_Off"]
                assert_almost_equal(datasets[0].data, np.array([[42, 3, 0.3], [43, 2, 0.2]]), decimal=3)
                assert_almost_equal(datasets[1].data, np.array([[42, 4, 0.4], [43, 4, 0.4]]), decimal=3)


if __name__ == "__main__":
    pytest.main([__file__])
