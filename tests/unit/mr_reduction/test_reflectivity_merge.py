from mr_reduction.reflectivity_merge import write_reflectivity_cross_section
from tests.unit.mr_reduction.test_reflectivity_output import parse_quicknxs_reduced_file


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

    direct_rows, data_rows = parse_quicknxs_reduced_file(output_file)
    assert len(direct_rows) == 1
    assert len(data_rows) == 1
    assert data_rows[0]["DB_ID"] == "1"
