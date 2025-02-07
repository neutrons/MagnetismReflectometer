# standard imports
import math
from datetime import datetime
from typing import Optional

import numpy as np
from mantid.simpleapi import mtd

# third party imports
from mantid.utils.reflectometry.orso_helper import MantidORSODataColumns, MantidORSODataset, MantidORSOSaver

# mr_reduction imports
import mr_reduction
from mr_reduction.beam_options import DirectBeamOptions, ReflectedBeamOptions
from mr_reduction.logging import logger
from mr_reduction.script_output import generate_script_from_ws
from mr_reduction.simple_utils import SampleLogs
from mr_reduction.types import MantidAlgorithmHistory, MantidWorkspace


def dataset_assembler(workspace: MantidWorkspace) -> MantidORSODataset:
    # TODO: direct_options will be used in a future version
    # direct_options = DirectBeamOptions.from_workspace(workspace)
    reflected_options = ReflectedBeamOptions.from_workspace(workspace)

    #
    # collect the numerical data (Q, intensity, theta)
    #
    ws = mtd[str(workspace)]

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

    theta = np.full(len(q), reflected_options.tth * math.pi / 360.0)
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
    for history in workspace.getHistory().getAlgorithmHistories():
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
    dataset = MantidORSODataset(
        dataset_name="dataset_name",
        data_columns=data_columns,
        ws=workspace,
        reduction_timestamp=_reduction_timestamp(reduction_history),
        creator_name="ORNL/SNS/REF_M",
        creator_affiliation="Oak Ridge National Laboratory",
    )

    #
    # additional info for the ORSO header
    dataset.set_facility("ORNL/SNS")
    sample_logs = SampleLogs(workspace)
    dataset.set_proposal_id(sample_logs["experiment_identifier"])
    dataset.set_reduction_call(generate_script_from_ws([workspace], str(workspace), quicknxs_mode=False))
    reduction_software = dataset._header.reduction.software
    reduction_software.name = "mr_reduction"
    reduction_software.version = mr_reduction.__version__

    return dataset


def write_orso(ws_list, output_path):
    r"""
    Write out reflectivity output (usually from autoreduction, as file REF_M_*_autoreduce.dat).

    This function generates and writes reflectivity data (typically as a result of an autoreduction process)
    to an output file in ORSO ASCII format, which can be loaded by SasView.

    Parameters
    ----------
    ws_list : list
        A list of workspace objects containing reflectivity data.
    output_path : str
        The path where the output file will be written. Must end with extension ".ort".
    """
    if not output_path.endswith(".ort"):
        raise ValueError("Output file must have .ort extension")

    orso_saver = MantidORSOSaver(output_path, comment="May not be fully ORSO compliant")
    for ws in ws_list:
        orso_saver.add_dataset(dataset_assembler(ws))
    orso_saver.save_orso_ascii()
