# standard library imports
import math
from datetime import datetime
from typing import Dict, List, Optional, Union

# third-party imports
import numpy as np
from mantid.utils.reflectometry.orso_helper import MantidORSODataColumns, MantidORSODataset, MantidORSOSaver
from numpy.testing import assert_almost_equal, assert_equal
from orsopy.fileio.base import Value as ORSOValue
from orsopy.fileio.base import ValueRange as ORSOValueRange
from orsopy.fileio.data_source import InstrumentSettings as ORSOInstrumentSettings
from orsopy.fileio.data_source import Measurement as ORSOMeasurement
from orsopy.fileio.orso import Orso, OrsoDataset, load_orso, save_orso

# mr_reduction imports
import mr_reduction
from mr_reduction.beam_options import DirectBeamOptions, ReflectedBeamOptions
from mr_reduction.logging import logger
from mr_reduction.script_output import generate_script_from_ws
from mr_reduction.simple_utils import SampleLogs, workspace_handle
from mr_reduction.spin_setup import REFMSpinSetup
from mr_reduction.types import MantidAlgorithmHistory, MantidWorkspace


def dataset_assembler(workspace: MantidWorkspace) -> MantidORSODataset:
    """
    Assemble a MantidORSODataset given a workspace containing reflectivity for one cross-section.

    Parameters
    ----------
    workspace : MantidWorkspace
        The Mantid workspace containing the reflectivity data

    Returns
    -------
    MantidORSODataset
        The assembled MantidORSODataset containing the reflectivity data and selected metadata
        collected from the sample logs of the workspace.

    Notes
    -----
    This function collects numerical data (Q, intensity, theta) from the workspace,
    gathers reduction algorithm history, and creates a MantidORSODataset with the
    appr
    """
    # TODO: direct_options will be used in a future version if we bother to gather data from the normalizing run
    # direct_options = DirectBeamOptions.from_workspace(workspace)
    reflected_options = ReflectedBeamOptions.from_workspace(workspace)

    #
    # collect the numerical data (Q, intensity, theta)
    #
    ws = workspace_handle(workspace)

    q, q_error = ws.readX(0), ws.readDx(0)
    intensity, intensity_error = ws.readY(0), ws.readE(0)
    data_columns = MantidORSODataColumns(
        q_data=q,
        reflectivity_data=intensity,
        reflectivity_error=intensity_error,
        q_resolution=q_error,
        q_unit=MantidORSODataColumns.Unit.InverseAngstrom,
        r_error_value_is=MantidORSODataColumns.ErrorValue.Sigma,
        q_error_value_is=MantidORSODataColumns.ErrorValue.Sigma,
    )
    theta_in_degrees = reflected_options.tth * math.pi / 360.0
    theta = np.full(len(q), theta_in_degrees)
    data_columns.add_column(
        name="theta", unit=MantidORSODataColumns.Unit.Degrees, physical_quantity="theta", data=theta
    )

    theta_error = theta * (q_error / q)
    data_columns.add_error_column(
        error_of="theta",
        error_type=MantidORSODataColumns.ErrorType.Uncertainty,
        value_is=MantidORSODataColumns.ErrorValue.Sigma,
        data=theta_error,
    )

    #
    # reduction (or stitch) algorithm history
    #
    reduction_history = None
    for history in ws.getHistory().getAlgorithmHistories():
        if history.name() in ("MagnetismReflectometryReduction", "Stitch1D"):
            reduction_history = history
            break

    def _reduction_timestamp(history: Optional[MantidAlgorithmHistory]) -> Optional[datetime]:
        """Algorithm execution date (in UTC), and convert to a datetime object expressed in local time

        Parameters
        ----------
        history : AlgorithmHistory
            The reduction algorithm history

        Returns
        -------
        datetime
            The reduction timestamp in local time, or None if the timestamp could not be parsed or if hi
        """
        if not history:
            return None
        try:
            return MantidORSODataset.create_local_datetime_from_utc_string(history.executionDate().toISO8601String())
        except ValueError:
            logger.notice(
                "Could not parse the reduction timestamp into the required format "
                "- this information will be excluded from the file."
            )
            return None

    #
    # create the dataset
    #
    sample_logs = SampleLogs(workspace)
    cross_section_label = sample_logs["cross_section_id"]  # e.g. "Off_Off", "On_Off"

    dataset = MantidORSODataset(
        dataset_name=cross_section_label,
        data_columns=data_columns,
        ws=ws,
        reduction_timestamp=_reduction_timestamp(reduction_history),
        creator_name="ORNL/SNS/REF_M",
        creator_affiliation="Oak Ridge National Laboratory",
    )

    #
    # ORSO header
    dataset.set_facility("ORNL/SNS")
    dataset.set_proposal_id(sample_logs["experiment_identifier"])
    dataset.set_reduction_call(generate_script_from_ws([workspace], str(workspace), quicknxs_mode=False))

    info: Orso = dataset.dataset.info
    reduction_software = info.reduction.software
    reduction_software.name = "mr_reduction"
    reduction_software.version = mr_reduction.__version__

    measurement: ORSOMeasurement = info.data_source.measurement
    measurement.instrument_settings = ORSOInstrumentSettings(
        incident_angle=ORSOValue(theta_in_degrees, "deg"),
        wavelength=ORSOValueRange(sample_logs["lambda_min"], sample_logs["lambda_max"], "angstrom"),
        polarization=REFMSpinSetup.from_workspace(workspace).as_orso,
    )
    # building the InstrumentSetting object

    return dataset


def save_cross_sections(ws_list: List[MantidWorkspace], output_path: str) -> None:
    r"""
    Save the reflectivities for different cross-sections for a particular peak

    This function generates and writes reflectivity data (typically as a result of an autoreduction process)
    to an output file in ORSO ASCII format, which can be loaded by SasView.

    Parameters
    ----------
    ws_list : list
        A list of workspace objects containing reflectivity data for the different cross-sections.
    output_path : str
        The path where the output file will be written. Must end with extension ".ort".

    Raises
    -------
    ValueError
        If the output file path does not end with ".ort".
    """
    if not output_path.endswith(".ort"):
        raise ValueError("Output file must have .ort extension")

    orso_saver = MantidORSOSaver(output_path, comment="May not be fully ORSO compliant")
    for ws in ws_list:
        orso_saver.add_dataset(dataset_assembler(ws))
    orso_saver.save_orso_ascii()


class SequenceDataSet:
    """
    Class to handle a sequence of ORSO files, each containing the reflectivities for the different cross-sections
    (e.g. "Off_Off", "On_Off", etc.) of a particular run (e.g. run "29160", runpeak "29160_2").

    The sequence is typically composed of a series of consecutive runs (e.g. "29160", "29161", "29162")
    representing a sequence of reflectometry experiments conducted on the same sample
    but at different incident angles or wavelengths ranges.
    """

    def __init__(self, filepath_sequence: Dict[str, str] = None):
        """
        Initialize the SequenceDataSet with a list of ORSO files, each containing the reflectivities
        for the different cross-sections (e.g. "Off_Off", "On_Off", etc.)
        of a particular runpeak (e.g. run "29160", runpeak "29160_2").

        Parameters
        ----------
        filepath_sequence
            a dictionary `filepath_sequence[runpeak] = filepath` where `runpeak` is the runpeak identifier
        """
        self._cross_sections: Optional[List[str]] = None  # e.g. ["Off_Off", "On_Off"]
        self.runpeaks: Optional[List[str]] = None  # e.g. ["29160", "29161", "29162"]
        self.datasets: Dict[str, List[OrsoDataset]] = {}  # e.g. {"2916": [On_Off, On_On], "2917": [On_Off, On_On]}
        if filepath_sequence is None:
            return
        for runpeak, filepath in filepath_sequence.items():
            self.load_runpeak(runpeak, filepath)

    def __getitem__(self, item):
        """
        Get the datasets for a given runpeak or a cross-section.

        When `item` is a cross-section label (e.g. "Off_Off", "On_Off"), it returns the datasets for that cross-section
        by iterating over the runpeaks in the order of list `self.runpeaks`.

        Examples
        --------
        >>> datasets = sequence["29160"]  # get all cross-section datasets for runpeak "29160"
        >>> datasets = sequence["Off_Off"]  # get the runpeak datasets for cross-section "Off_Off"

        Parameters
        ----------
        item : str
            The runpeak (e.g. "29160", "29160_2") or cross-section label (e.g. "Off_Off", "On_Off").

        Returns
        -------
        List[OrsoDataset]
            The list of datasets for the given runpeak or cross-section.
        """
        if item in self.runpeaks:  # item is a runpeak
            return self.datasets[item]
        elif item in self.cross_sections:  # item is a cross-section
            index = self.cross_sections.index(item)  # find the index of the cross-section label `item`
            return [self.datasets[runpeak][index] for runpeak in self.runpeaks]
        else:
            raise KeyError(f"{item} not found in the datasets")

    @property
    def cross_sections(self) -> Optional[List[str]]:
        """Get the list of cross-section labels e.g. ["Off_Off", "On_Off"]"""
        return self._cross_sections

    def is_compatible(self, datasets: List[OrsoDataset]) -> bool:
        """
        Check if the cross-section labels in the input datasets are the same as those in this SequenceDataSet, and
        whether they are in the same order.

        The name of each dataset (dataset.info.data_set) in input `datasets` should be a valid cross-section label,
        such as "Off_On", "On_Off", etc.

        Parameters
        ----------
        datasets : List[OrsoDataset]
            List of input datasets to check.

        Returns
        -------
        bool
            True if the datasets are compatible, False otherwise.
        """
        if self.cross_sections is None or len(self.cross_sections) == 0:
            return True  # the SequenceDataSet is empty, so it is compatible with any input datasets
        if len(datasets) != len(self.cross_sections):
            return False  # quick check on the number of cross-sections
        cross_sections = [dataset.info.data_set for dataset in datasets]  # collect the input cross-section labels
        return self.cross_sections == cross_sections  # the order matters

    def load_runpeak(self, runpeak: str, filepath: str):
        """
        Load an ORSO file containing the datasets for the different cross-sections of a given runpeak.

        Parameters
        ----------
        runpeak : str
            The runpeak identifier (e.g. "29160", "29160_2").
        filepath : str
            Path to the ORSO file.
        """
        assert runpeak not in self.datasets, f"Runpeak {runpeak} already loaded"
        datasets: List[OrsoDataset] = load_orso(filepath)
        assert self.is_compatible(datasets), "Cross-section labels do not match the existing datasets"
        if self.cross_sections is None:  # this is the very first dataset to be loaded
            self._cross_sections = [dataset.info.data_set for dataset in datasets]
            self.runpeaks = []
        self.datasets[runpeak] = datasets
        self.runpeaks.append(runpeak)

    def sort(self):
        """
        Sort the runpeak sequence by increasing Qz values

        Assumptions:
           all the cross-sections datasets of a runpeak have the same Qz values
           in any given OrsoDataset, the Qz values are in the first column
        """

        def qz_min(runpeak: str) -> float:
            """find smallest Qz for the datasets of a given runpeak"""
            datasets = self.datasets[runpeak]  # cross-section datasets for this runpeak
            # look at the first value of the first column of the first dataset. That's Qz min
            return datasets[0].data[0][0]

        self.runpeaks.sort(key=qz_min)  # sort the list of runpeaks by increasing Qz values

    def scale_intensities(self, scaling_factors: Dict[str, float]):
        """
        Scale the datasets by the given scaling factors.

        This will rescale Column "R" and ErrorColumn "R" in each dataset by the corresponding scaling factor.
        It's assumed they are columns 1 and 2 in the datasets of any cross-section of any runpeak.

        Parameters
        ----------
        scaling_factors
            A dictionary `scaling_factors[runpeak] = scaling`
        """
        assert set(scaling_factors) == set(self.runpeaks), "Scaling factors must be provided for all runpeaks"
        for runpeak, scaling_factor in scaling_factors.items():
            for dataset in self.datasets[runpeak]:  # iterate over the cross-sections
                data: np.array = dataset.data
                data[:, 1] *= scaling_factor  # scale the R column in-place
                data[:, 2] *= scaling_factor  # scale the sR column in-place

    def concatenate(self) -> List[OrsoDataset]:
        """
        Concatenate the datasets of all the runpeaks, for each cross-section.

        For instance, starting with datasets {"2916": [On_Off, On_On], "2917": [On_Off, On_On]},
        we end up with datasets ["On_Off", "On_On"] where dataset "On_Off" results from
        concatenating datasets ["2916"][0] and ["2917"][0].
        Notice that the last Qz values of ["2916"][0] can be higher than the first Qz values of ["2917"][0]
        because we're not stitching, just concatenating.

        Returns
        -------
        A list of datasets, one for each cross-section.
        """
        datasets: List[OrsoDataset] = []
        for cross_section in self.cross_sections:  # iterate over the cross-sections labels
            # concatenate the numpy arrays containing the data for this cross-section for all runpeaks
            data = np.concatenate([dataset.data for dataset in self[cross_section]])
            # use the `info` attribute of the dataset of the first runpeak
            dataset: OrsoDataset = self[cross_section][0]
            datasets.append(OrsoDataset(info=dataset.info, data=data))
        return datasets


def concatenate_runs(
    filepath_sequence: Dict[str, str], concatenated_filepath: str, scaling_factors: Dict[str, float] = None
) -> List[OrsoDataset]:
    """
    Concatenate the reflectivity curves for a sequence of runs or runpeaks (e.g. "29160_1", "29161_1", "29162_1"),
    and save to an ORSO file in ASCII format.

    Each runpeak is represented by an ORSO file containing the reflectivities for the different cross-sections
    (e.g. "Off_Off", "On_Off", etc.). All the ORSO files must contain reflectivity data for the same cross-sections
    and in the same order.

    Other assumptions:
    - The Qz values are in the first column of each dataset.
    - The reflectivity values are in the second column of each dataset.
    - The error values are in the third column of each dataset.

    Parameters
    ----------
    filepath_sequence
        a dictionary `filepath_sequence[runpeak] = filepath` where `runpeak` is the runpeak identifier
    concatenated_filepath
        The path where the stitched ORSO file will be saved. Should end with ".ort" extension.
    scaling_factors
        A dictionary `scaling_factors[runpeak] = scaling`

    Returns
    -------
    A list of datasets, one for each cross-section, containing the concatenated reflectivity data.
    """
    assert concatenated_filepath.endswith(".ort"), "Output file must have .ort extension"
    if scaling_factors is not None:
        assert set(filepath_sequence) == set(scaling_factors), "Scaling factors must be provided for all runpeaks"

    sequence = SequenceDataSet(filepath_sequence)
    sequence.sort()  # sort runpeaks by increasing Qz values
    if scaling_factors is not None:
        sequence.scale_intensities(scaling_factors)
    datasets = sequence.concatenate()  # concatenate the runpeaks for each cross-section
    save_orso(datasets, concatenated_filepath)
    return datasets


class Questor:
    """Helper class to check a few things of an ORSO file, used in test functions"""

    def __init__(self, filepath: str = None, datasets: List[OrsoDataset] = None):
        self.datasets: datasets
        if filepath is not None:
            self.datasets = load_orso(filepath)

    @property
    def incident_angle(self):
        """Fetch the theta angle for each dataset"""
        return [
            dataset.info.data_source.measurement.instrument_settings.incident_angle.magnitude
            for dataset in self.datasets
        ]

    @property
    def polarizations(self) -> List[str]:
        """Fetch the polarization states for each dataset, e.g. 'unpolarized', 'op', 'mm'"""
        return [
            dataset.info.data_source.measurement.instrument_settings.polarization.value for dataset in self.datasets
        ]

    @property
    def cross_sections(self) -> List[str]:
        """Fetch the cross section label for each dataset, e.g. 'Off_Off', 'Off_On'"""
        return [dataset.info.data_set for dataset in self.datasets]

    def assert_equal(self, **kwargs):
        """
        Assert that the specified attributes of the Questor instance match the given values.

        Parameters
        ----------
        **kwargs : dict
            Keyword arguments where the key is the name of the attribute to check,
            and the value is the expected value.

        Raises
        ------
        AssertionError
            If any of the specified attributes do not match the expected values.

        Examples
        --------
        >>> questor = Questor(filepath="path/to/file.ort")
        >>> questor.assert_equal(cross_sections=["Off_Off"], polarizations=["unpolarized"])
        """
        for query, test_value in kwargs.items():
            stored_value = getattr(self, query)
            assert_equal(stored_value, test_value)

    def assert_almost_equal(self, decimal: Union[int, List[int]], **kwargs):
        """
        Assert that the specified attributes of the Questor instance match the given values to a certain decimal place.

        Parameters
        ----------
        decimal : int or list of int
            The number of decimal places to which to compare the values. If a single integer is provided,
            it is used for all comparisons. If a list of integers is provided,
            each integer corresponds to the number of decimal places for each comparison.

        **kwargs : dict
            Keyword arguments where the key is the name of the attribute to check,
            and the value is the expected value.

        Raises
        ------
        AssertionError
            If any of the specified attributes do not match the expected values.

        Examples
        --------
        >>> questor = Questor(filepath="path/to/file.ort")
        >>> questor.assert_almost_equal(decimal=3, incident_angle=[0.0273, 0.0114])
        """
        if isinstance(decimal, int):
            decimal = [decimal] * len(kwargs)  # same decimal for all values to test
        for i, (query, test_value) in enumerate(kwargs.items()):
            stored_value = getattr(self, query)
            assert_almost_equal(stored_value, test_value, decimal=decimal[i])
