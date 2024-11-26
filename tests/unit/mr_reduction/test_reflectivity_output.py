# standard imports
import os

import pytest

# third party imports
from mantid.simpleapi import LoadNexus

# mr_reduction imports
from mr_reduction.reflectivity_output import write_reflectivity


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
