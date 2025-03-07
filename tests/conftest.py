# standard imports
import os
import sys
import unittest.mock as mock
from collections import namedtuple
from os.path import dirname
from typing import List

import pytest

# third party imports
from mantid.simpleapi import config

this_module_path = sys.modules[__name__].__file__


@pytest.fixture()  # scope="function"
def tempdir(tmpdir):
    r"""Get the path of pytest fixture tmpdir as a string"""
    return str(tmpdir)


@pytest.fixture(scope="session")
def data_server():
    r"""Object containing info and functionality for data files
    Also, it adds the path of the data-repo to the list of Mantid data directories
    """

    _options = ["datasearch.directories", "default.facility", "default.instrument"]
    _backup = {key: config[key] for key in _options}

    class _DataServe:
        datarepo = os.path.join(os.path.dirname(this_module_path), "mr_reduction-data")

        def __init__(self):
            self._directories = [self.datarepo]
            for directory in self._directories:
                config.appendDataSearchDir(directory)
            config["default.facility"] = "SNS"
            config["default.instrument"] = "REF_M"

        @property
        def directories(self) -> List[str]:
            r"""Absolute path to the data-repo directory"""
            return self._directories

        @property
        def path_to_template(self) -> str:
            r"""Absolute path to reduce_REF_M.py.template"""
            return os.path.join(dirname(dirname(self.datarepo)), "src", "mr_autoreduce", "reduce_REF_M.py.template")

        def path_to(self, basename: str) -> str:
            r"""
            Absolute path to a file in the data directories or any of its subdirectories.

            Parameters
            ----------
            basename
                file name (with extension) to look for

            Returns
            -------
                First match of the file in the data directory or its subdirectories
            """
            for directory in self._directories:
                for dirpath, dirnames, filenames in os.walk(directory):
                    if basename in filenames:
                        return os.path.join(dirpath, basename)
            raise IOError(f"File {basename} not found in data directory {self._directories}")

    yield _DataServe()
    for key, val in _backup.items():
        config[key] = val


@pytest.fixture()  # scope="function"
def mock_filesystem(tempdir, data_server):
    r"""
    A set of mocks to redirect paths such as /SNS/REF_M/%(ipts)s/shared/autoreduce/
    and /SNS/REF_M/%(ipts)s/nexus to a temporary directory.
    """
    MockSetup = namedtuple("MockSetup", ["tempdir", "DirectBeamFinder"])

    with (
        mock.patch("mr_reduction.mr_reduction.DirectBeamFinder") as mock_DirectBeamFinder,
        mock.patch("mr_reduction.reflectivity_merge.nexus_data_dir") as mock_data_dir,
    ):
        mock_data_dir.return_value = data_server.datarepo

        yield MockSetup(tempdir, mock_DirectBeamFinder)
