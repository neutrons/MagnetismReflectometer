"""
Unit tests for the `reflectivity_output` module in the `mr_reduction` package.

This module contains tests for the `write_reflectivity` function, which writes
reflectivity data to a specified output file. The tests use the `pytest` framework
and mock the filesystem and data server to verify the correctness of the output.

Tested function:
- `write_reflectivity`: Writes reflectivity data to a file.

Test cases:
- `test_write_reflectivity`: Verifies that the `write_reflectivity` function correctly
  writes the reflectivity data to the output file, comparing the result with an expected
  output file.

Dependencies:
- `pytest`: For running the tests and marking test cases.
- `mantid.simpleapi`: For loading Nexus files.
- `mr_reduction.reflectivity_output`: The module under test.
"""

# standard imports
import os

import pytest

# third party imports
from mantid.simpleapi import LoadNexus

# mr_reduction imports
from mr_reduction.reflectivity_output import write_reflectivity

# Test helpers for QuickNXS reduced-file compatibility checks.


def _row_to_dict(columns: list[str], tokens: list[str]) -> dict[str, str]:
    """Map tokenized row values by column name, ignoring the leading '#' token."""
    return {name: tokens[i] for i, name in enumerate(columns) if name != "#" and i < len(tokens)}


def parse_quicknxs_reduced_file(file_path: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Parse reduced file sections using the same tokenization contract as QuickNXS.

    This intentionally checks only format-level compatibility and does not import/call QuickNXS.
    """
    with open(file_path, "r") as file_handle:
        lines = file_handle.readlines()

    if not lines or not lines[0].startswith("# Datafile created by QuickNXS"):
        raise AssertionError("Reduced file is missing the QuickNXS signature line")

    direct_rows: list[dict[str, str]] = []
    data_rows: list[dict[str, str]] = []
    section = None
    direct_columns = None
    data_columns = None

    for line in lines:
        if "[Direct Beam Runs]" in line:
            section = "direct"
            continue
        if "[Data Runs]" in line:
            section = "data"
            continue
        if line.startswith("# [") and ("[Direct Beam Runs]" not in line) and ("[Data Runs]" not in line):
            section = None
            continue

        tokens = line.replace(", ", ",").split()
        if section == "direct":
            if "DB_ID" in tokens:
                direct_columns = tokens
                continue
            # QuickNXS parser requires at least this token count for direct rows.
            if len(tokens) < 14:
                continue
            if direct_columns is None:
                raise AssertionError("Direct beam rows found before a Direct Beam Runs header")
            direct_rows.append(_row_to_dict(direct_columns, tokens))
            continue

        if section == "data":
            if "DB_ID" in tokens:
                data_columns = tokens
                continue
            # QuickNXS parser requires at least this token count for data rows.
            if len(tokens) < 16:
                continue
            if data_columns is None:
                raise AssertionError("Data rows found before a Data Runs header")
            data_rows.append(_row_to_dict(data_columns, tokens))

    if len(data_rows) == 0:
        raise AssertionError("No parseable Data Runs rows were found")

    return direct_rows, data_rows


@pytest.mark.datarepo
def test_write_reflectivity(mock_filesystem, data_server):
    reflectivity_workspace = LoadNexus(data_server.path_to("REF_M_29160_2_Off_Off_autoreduce.nxs.h5"))
    output_file = os.path.join(mock_filesystem.tempdir, "REF_M_29160_2_Off_Off_autoreduce.dat")
    write_reflectivity([reflectivity_workspace], output_file, cross_section="Off-Off")

    # verify output satisfies the QuickNXS parsing contract without importing quicknxs
    direct_rows, data_rows = parse_quicknxs_reduced_file(output_file)
    assert len(direct_rows) >= 1
    assert len(data_rows) >= 1

    # compare output_file to expected. Skip first 4 header lines (signature/version/date), which can vary.
    with open(output_file) as output_handle:
        obtained = output_handle.readlines()[4:]
    with open(data_server.path_to("REF_M_29160_2_Off_Off_autoreduce.dat")) as expected_handle:
        expected = expected_handle.readlines()[4:]

    assert len(obtained) == len(expected)
    for obtained_line, expected_line in zip(obtained, expected):
        if ("REF_M_29137_histo.nxs" in obtained_line) or ("REF_M_29160_histo.nxs" in obtained_line):
            obtained_items = obtained_line.split()[:-1]  # remove the last item which is the absolute file path
            expected_items = expected_line.split()[:-1]
            assert obtained_items == expected_items
        else:
            assert obtained_line == expected_line


if __name__ == "__main__":
    pytest.main([__file__])
