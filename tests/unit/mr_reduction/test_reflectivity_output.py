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


@pytest.mark.datarepo
def test_write_reflectivity(mock_filesystem, data_server):
    reflectivity_workspace = LoadNexus(data_server.path_to("REF_M_29160_2_Off_Off_autoreduce.nxs.h5"))
    output_file = os.path.join(mock_filesystem.tempdir, "REF_M_29160_2_Off_Off_autoreduce.dat")
    write_reflectivity([reflectivity_workspace], output_file, cross_section="Off-Off")
    # compare output_file to expected. Avoid the first 4 lines that deal with library versions and creation date
    obtained = open(output_file).readlines()[4:]
    expected = open(data_server.path_to("REF_M_29160_2_Off_Off_autoreduce.dat")).readlines()[4:]
    for obtained_line, expected_line in zip(obtained, expected):
        if ("REF_M_29137_histo.nxs" in obtained_line) or ("REF_M_29160_histo.nxs" in obtained_line):
            obtained_items = obtained_line.split()[:-1]  # remove the last item which is the absolute file path
            expected_items = expected_line.split()[:-1]
            assert obtained_items == expected_items
        else:
            assert obtained_line == expected_line


if __name__ == "__main__":
    pytest.main([__file__])
