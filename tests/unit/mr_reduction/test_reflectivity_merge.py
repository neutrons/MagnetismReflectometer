import pytest

from mr_reduction.io_dat import read_reduced_file
from mr_reduction.reflectivity_merge import (
    _extract_sequence_id,
    compute_scaling_factors,
    write_reflectivity_cross_section,
)


def test_write_reflectivity_cross_section(tmp_path):
    output_file = write_reflectivity_cross_section(
        runpeak="42535_1",
        cross_section="Off_Off",
        matched_runs=["42535_1"],
        direct_beam_info=(
            "#        1         0         0       180        13       133        75       161        11"
            "       180         0     42534  /tmp/REF_M_42534_histo.nxs\n"
        ),
        data_info=(
            "#        1         0         0     180.5        24       144        47        50        41"
            "     False       180  0.765104     42535         1  /tmp/REF_M_42535_histo.nxs\n"
        ),
        data_buffer="   0.0103752    0.00349571   6.63863e-05   0.000562007    0.00660061\n",
        xs_label="+",
        output_dir=str(tmp_path),
    )

    with open(output_file, "r") as file_handle:
        assert file_handle.readline().startswith("# Datafile created by QuickNXS")

    direct_beam_runs, data_runs, *_ = read_reduced_file(output_file)
    assert len(direct_beam_runs) == 1
    assert len(data_runs) == 1
    assert data_runs[0][2]["DB_ID"] == 1


@pytest.mark.datarepo
def test_extract_sequence_id(data_server):
    file_path = data_server.path_to("REF_M_29160_2_Off_Off_autoreduce.dat")
    run_peak_number, group_id, lowest_q = _extract_sequence_id(file_path)

    assert run_peak_number == "29160_2"
    assert group_id is None
    assert isinstance(lowest_q, float)


@pytest.mark.datarepo
def test_compute_scaling_factors_reads_option_objects(data_server):
    scaling_factors, direct_beam_info, data_info, data_buffer, cross_section_label = compute_scaling_factors(
        matched_runs=["42535_1", "42536_1"],
        cross_section="Off_Off",
        ar_dir=data_server.datarepo,
    )

    assert len(scaling_factors) == 2
    assert len(direct_beam_info.splitlines()) >= 2
    assert len(data_info.splitlines()) >= 2
    assert len(data_buffer.splitlines()) > 0
    assert cross_section_label == "+"
