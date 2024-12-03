# standard imports
import os

# from mantid.utils.reflectometry.orso_helper import MantidORSODataColumns, MantidORSODataset, MantidORSOSaver
import pytest

# third party imports
from mantid.simpleapi import LoadNexus

# mr_reduction imports
from mr_reduction.io_orso import write_orso


def test_write_orso_output_file_extension():
    with pytest.raises(ValueError, match="Output file must have .ort extension"):
        write_orso([], "output_file", "cross_section")


def test_write_orso(mock_filesystem, data_server):
    reflectivity_workspace = LoadNexus(data_server.path_to("REF_M_29160_2_Off_Off_autoreduce.nxs.h5"))
    output_file = os.path.join(mock_filesystem.tempdir, "REF_M_29160_2_Off_Off_autoreduce.ort")
    write_orso([reflectivity_workspace], output_file, cross_section="Off-Off")
    assert os.path.exists(output_file)


if __name__ == "__main__":
    pytest.main([__file__])
