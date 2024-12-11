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
from mantid.simpleapi import AddSampleLog, CreateWorkspace, DeleteWorkspace, LoadNexus, mtd

# mr_reduction imports
from mr_reduction.reflectivity_output import DirectBeamOptions, ReflectedBeamOptions, write_reflectivity


@pytest.fixture(scope="module")
def mock_normalization_workspace():
    workspace = mtd.unique_hidden_name()
    CreateWorkspace(DataX=[0, 1], DataY=[0, 10], OutputWorkspace=workspace)
    for name, value, logType in [
        ("run_number", 12345, "Number"),
        ("normalization_run", 12345, "Number"),
        ("norm_peak_min", 10, "Number"),
        ("norm_peak_max", 20, "Number"),
        ("norm_bg_min", 5, "Number"),
        ("norm_bg_max", 15, "Number"),
        ("norm_low_res_min", 1, "Number"),
        ("norm_low_res_max", 2, "Number"),
        ("normalization_dirpix", 0.5, "Number"),
        ("normalization_file_path", "path/to/nexus_file.nxs.h5", "String"),
    ]:
        AddSampleLog(workspace, LogName=name, LogText=str(value), LogType=logType)
    yield workspace
    DeleteWorkspace(workspace)  # teardown steps after all tests in this module have run


@pytest.fixture(scope="module")
def mock_reflected_workspace():
    workspace = mtd.unique_hidden_name()
    CreateWorkspace(DataX=[0, 1], DataY=[0, 10], OutputWorkspace=workspace)
    for name, value, logType in [
        ("Filename", "path/to/nexus_file.nxs.h5", "String"),
    ]:
        AddSampleLog(workspace, LogName=name, LogText=str(value), LogType=logType)
    yield workspace
    DeleteWorkspace(workspace)  # teardown steps after all tests in this module have run


class TestDirectBeamOptions:
    def test_dat_header(self):
        header = DirectBeamOptions.dat_header()
        assert header.startswith("# [Direct Beam Runs]")

    def test_from_workspace(self, mock_normalization_workspace):
        options = DirectBeamOptions.from_workspace(mock_normalization_workspace)
        assert options is not None
        assert options.DB_ID == 1
        assert options.number == 12345
        assert options.File == "path/to/data_file_histo.nxs"

    def test_as_dat(self, mock_normalization_workspace):
        options = DirectBeamOptions.from_workspace(mock_normalization_workspace)
        assert (
            options.as_dat == "#        1         0         0        15        11       1.5         2        10"
            "        11       0.5         0     12345  path/to/data_file_histo.nxs\n"
        )


class TestReflectedBeamOptions:
    def test_dat_header(self):
        header = ReflectedBeamOptions.dat_header()
        assert header.startswith("# [Data Runs]\n")

    def test_filename(self, mock_reflected_workspace):
        assert ReflectedBeamOptions.filename(mock_reflected_workspace) == "path/to/data_file_histo.nxs"
        ws = CreateWorkspace(DataX=[0, 1], DataY=[0, 10], OutputWorkspace=mtd.unique_hidden_name())
        assert ReflectedBeamOptions.filename(ws) == "live data"
        DeleteWorkspace(ws)

    def test_two_theta_offset(self, mock_reflected_workspace):
        pass

    def test_from_workspace(self):
        pass

    def test_options(self):
        pass

    def test_as_dat(self):
        pass


@pytest.mark.datarepo()
def test_write_reflectivity(mock_filesystem, data_server):
    reflectivity_workspace = LoadNexus(data_server.path_to("REF_M_29160_2_Off_Off_autoreduce.nxs.h5"))
    output_file = os.path.join(mock_filesystem.tempdir, "REF_M_29160_2_Off_Off_autoreduce.dat")
    write_reflectivity([reflectivity_workspace], output_file, cross_section="Off-Off")
    # compare output_file to expected. Avoid the first 4 lines that deal with library versions and creation date
    obtained = open(output_file).readlines()[4:]
    expected = open(data_server.path_to("REF_M_29160_2_Off_Off_autoreduce.dat")).readlines()[4:]
    for obtained_line, expected_line in zip(obtained, expected):
        assert obtained_line == expected_line


if __name__ == "__main__":
    pytest.main([__file__])
