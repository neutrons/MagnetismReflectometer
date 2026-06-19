import pytest

from mr_reduction.beam_options import DirectBeamOptions, ReflectedBeamOptions
from mr_reduction.io_dat import (
    ReducedFileData,
    determine_which_files_to_sum,
    read_reduced_data,
    read_reduced_file,
)


@pytest.mark.datarepo
def test_read_reduced_file_from_autoreduce_fixture(data_server):
    file_path = data_server.path_to("REF_M_29160_2_Off_Off_autoreduce.dat")
    direct_beam_runs, data_runs, additional_peaks, has_scaling_error, global_options = read_reduced_file(file_path)

    assert len(direct_beam_runs) == 1
    assert len(data_runs) == 1
    assert len(additional_peaks) == 0
    assert has_scaling_error is False
    assert data_runs[0][0] == 29160
    assert isinstance(data_runs[0][2], dict)
    assert data_runs[0][2]["DB_ID"] == 1


@pytest.mark.datarepo
def test_read_reduced_data_from_fixture(data_server):
    file_path = data_server.path_to("REF_M_29160_2_Off_Off_autoreduce.dat")
    reduced = read_reduced_data(file_path)

    assert isinstance(reduced, ReducedFileData)
    assert isinstance(reduced.reflected_beam_options[0], ReflectedBeamOptions)
    assert reduced.reflected_beam_options[0].scale == 1.0


def test_peak_1_runs_override_data_runs(tmp_path):
    test_file = tmp_path / "peak_override.dat"
    test_file.write_text(
        """# Datafile created by QuickNXS 4.16.0
# Datafile created using Mantid 6.14.0
# Date: 2025-01-20 10:30:00
# Type: Specular
# Input file indices: 50001,50002
# Extracted states: +
#
# [Direct Beam Runs]
# DB_ID P0 PN x_pos x_width y_pos y_width bg_pos bg_width dpix tth number File
# 0 0 0 179.5 19 144 46 39 56 180 0 50000 /tmp/50000.nxs.h5
#
# [Data Runs]
# scale P0 PN x_pos x_width y_pos y_width bg_pos bg_width fan dpix tth number DB_ID File
# 1 5 10 212.6 19 117.3 65.3 39 56 False 180 2.2255 50001 0 /tmp/50001.nxs.h5
#
# [Peak 1 Runs]
# scale P0 PN x_pos x_width y_pos y_width bg_pos bg_width fan dpix tth number DB_ID File
# 3.7201 5 10 214.9 22 121.8 56.3 39 56 False 180 4.1776 50002 0 /tmp/50002.nxs.h5
#
# [Global Options]
# name           value
# sample_length  10
#
# [Data]
#     Qz [1/A]      R [a.u.]     dR [a.u.]     dQz [1/A]   theta [rad]
2.263373e-02       1.986968e-02       1.427452e-04       1.252235e-03       1.445378e-02
"""
    )

    _, data_runs, additional_peaks, _, global_options = read_reduced_file(str(test_file))

    assert len(data_runs) == 1
    assert data_runs[0][0] == 50002
    assert len(additional_peaks) == 0
    assert global_options == {"sample_length": 10}


def test_determine_which_files_to_sum_with_summed_run_number():
    run_file = "/SNS/REF_M/IPTS-12345/nexus/REF_M_42112.nxs.h5"
    output = determine_which_files_to_sum(run_file, "42112", run_number_str="42112+42113")

    assert output == ("/SNS/REF_M/IPTS-12345/nexus/REF_M_42112.nxs.h5+/SNS/REF_M/IPTS-12345/nexus/REF_M_42113.nxs.h5")


@pytest.mark.datarepo
def test_read_reduced_data_metadata_from_fixture(data_server):
    file_path = data_server.path_to("REF_M_29160_2_Off_Off_autoreduce.dat")
    metadata = read_reduced_data(file_path).metadata

    assert metadata["input_file_indices"] == "29160_2"
    assert metadata["extracted_states"] == "Off-Off"
    assert metadata["sequence_id"] is None
    assert isinstance(metadata["lowest_q"], float)


@pytest.mark.datarepo
def test_read_reduced_data_options_from_fixture(data_server):
    file_path = data_server.path_to("REF_M_29160_2_Off_Off_autoreduce.dat")
    reduced = read_reduced_data(file_path)

    assert len(reduced.direct_beam_options) == 1
    assert len(reduced.reflected_beam_options) == 1
    assert len(reduced.additional_peak_options) == 0
    assert reduced.has_scaling_error is False
    assert isinstance(reduced.direct_beam_options[0], DirectBeamOptions)
    assert isinstance(reduced.reflected_beam_options[0], ReflectedBeamOptions)
