# standard imports
import os
from typing import List

# mr_reduction imports
import mr_reduction

# from mantid.utils.reflectometry.orso_helper import MantidORSODataColumns, MantidORSODataset, MantidORSOSaver
import pytest

# third party imports
from mantid.simpleapi import LoadNexusProcessed
from mr_reduction.io_orso import write_orso
from orsopy.fileio.base import Column, ErrorColumn
from orsopy.fileio.orso import Orso, OrsoDataset, load_orso


def test_write_orso_output_file_extension():
    with pytest.raises(ValueError, match="Output file must have .ort extension"):
        write_orso([], "output_file")


@pytest.mark.datarepo()
def test_write_orso(mock_filesystem, data_server):
    reflectivity_workspace = LoadNexusProcessed(data_server.path_to("REF_M_29160_2_Off_Off_autoreduce.nxs.h5"))
    output_file = os.path.join(mock_filesystem.tempdir, "REF_M_29160_2_Off_Off_autoreduce.ort")
    write_orso([reflectivity_workspace], output_file)
    #
    # load the ORSO file and check its contents
    #
    datasets: List[OrsoDataset] = load_orso(output_file)
    assert len(datasets) == 1
    dataset = datasets[0]
    assert dataset.data.shape == (35, 6)
    info: Orso = dataset.info
    assert len(info.columns) == 6
    for i, (label, coltype) in enumerate(
        [
            ("Qz", Column),
            ("R", Column),
            ("sR", ErrorColumn),
            ("sQz", ErrorColumn),
            ("theta", Column),
            ("stheta", ErrorColumn),
        ]
    ):
        assert isinstance(info.columns[i], coltype)
        assert info.columns[i].name == label
    assert info.reduction.software.version == mr_reduction.__version__
    assert "MagnetismReflectometryReduction" in info.reduction.call


if __name__ == "__main__":
    pytest.main([__file__])
