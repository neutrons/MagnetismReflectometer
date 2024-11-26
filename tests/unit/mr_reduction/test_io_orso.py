# standard imports

# third party imports
# from mantid.utils.reflectometry.orso_helper import MantidORSODataColumns, MantidORSODataset, MantidORSOSaver
import pytest
from mantid.simpleapi import LoadNexus


def test_io_orso(data_server):
    reflectivity_workspace = LoadNexus(data_server.path_to("REF_M_29160_2_Off_Off_autoreduce.nxs.h5"))
    assert reflectivity_workspace


if __name__ == "__main__":
    pytest.main([__file__])
