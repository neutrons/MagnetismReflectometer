# standard imports
import itertools
import os
import shutil
import string
import sys
import tempfile
import unittest.mock as mock
from collections import namedtuple
from os.path import dirname
from typing import Any, Generator, List

import pytest

# third party imports
from mantid.simpleapi import LoadEventNexus, LoadNexusProcessed, config, mtd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType

# mr_reduction imports
from mr_reduction.types import MantidWorkspace

this_module_path = sys.modules[__name__].__file__


@pytest.fixture  # scope="function"
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

        def load_events(self, basename: str, output_workspace: str = None) -> MantidWorkspace:
            r"""
            Load a Nexus events file from the data directory

            Parameters
            ----------
            basename
                file name (with extension) to look for
            output_workspace
                name of the output workspace. If None, a unique hidden name is automatically provided
            """
            if output_workspace is None:
                output_workspace = mtd.unique_hidden_name()
            return LoadEventNexus(self.path_to(basename), OutputWorkspace=output_workspace)

        def load_nexus_processed(self, basename: str, output_workspace: str = None) -> MantidWorkspace:
            r"""
            Load a Nexus file created with SaveNexusProcessed

            Parameters
            ----------
            basename
                file name (with extension) to look for
            output_workspace
                name of the output workspace. If None, a unique hidden name is automatically provided
            """
            if output_workspace is None:
                output_workspace = mtd.unique_hidden_name()
            return LoadNexusProcessed(self.path_to(basename), OutputWorkspace=output_workspace)

    yield _DataServe()
    for key, val in _backup.items():
        config[key] = val


@pytest.fixture  # scope="function"
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


@pytest.fixture
def autoreduction_script(tempdir, data_server):
    """Create a temporary autoreduction script by substituting the passed `options`
    in the template autorereduction script.

    Parameters
    ----------
    options: dict
        Dictionary with the options to be substituted in the template script. If `None`, default options
        defined in the body of this fixture are substituted. These options are good for reducing the two peaks
        of run 42537.
    amend_options: dict
        Dictionary to update either the default dictionary in the body of this fixture or the passed `options`.
        It is useful when the intent is to amend some of the default options.
    outdir: str
        Directory where to save script reduce_REF_M.py. If `None`, the script is saved in the temporary directory
        given by the `tempdir` fixture
    Returns
    -------
        Absolute path to the autoreduction script
    """

    def _autoreduction_script(options: dict = None, amend_options: dict = None, outdir: str = None) -> str:
        #
        # Options to reduce the two peaks of run 41447
        #
        common = {  # options for all peaks
            "plot_in_2D": True,
            "use_const_q": False,
            "q_step": -0.022,
            "use_sangle": False,
            "fit_peak_in_roi": False,
            "peak_count": 2,  # run 41447 has two peaks
        }
        # Options for first peak
        peak1 = {
            "force_peak": True,
            "peak_min": 169,
            "peak_max": 192,
            "use_roi_bck": False,
            "force_background": True,
            "bck_min": 30,
            "bck_max": 70,
            "use_side_bck": False,
            "bck_width": 10,
            "force_low_res": False,
            "low_res_min": 50,
            "low_res_max": 175,
        }
        # Options for second peak
        peak2 = {
            "force_peak_s2": True,
            "peak_min_s2": 207,
            "peak_max_s2": 220,
            "use_roi_bck_s2": False,
            "force_background_s2": False,
            "bck_min_s2": 30,
            "bck_max_s2": 70,
            "use_side_bck_s2": False,
            "bck_width_s2": 11,
            "force_low_res_s2": False,
            "low_res_min_s2": 50,
            "low_res_max_s2": 175,
        }
        # Options for third peak (will be ignored because `peak_count` is 2)
        peak3 = {
            "force_peak_s3": True,
            "peak_min_s3": 180,
            "peak_max_s3": 190,
            "use_roi_bck_s3": False,
            "force_background_s3": True,
            "bck_min_s3": 7,
            "bck_max_s3": 102,
            "use_side_bck_s3": False,
            "bck_width_s3": 12,
            "force_low_res_s3": False,
            "low_res_min_s3": 50,
            "low_res_max_s3": 175,
        }
        values = {**common, **peak1, **peak2, **peak3}  # all options into one dictionary
        if options is None:
            options = values
        if amend_options is not None:
            options.update(amend_options)

        # inject options in the reduction template and save as new script reduce_REF_M.py
        with open(data_server.path_to_template, "r") as file_handle:
            template = string.Template(file_handle.read())
            script = template.substitute(**options)
        if outdir is None:
            outdir = tempdir
        reduce_REF_M = os.path.join(outdir, "reduce_REF_M.py")
        open(reduce_REF_M, "w").write(script)
        return reduce_REF_M

    return _autoreduction_script


@pytest.fixture
def browser(tmp_path) -> Generator[WebDriver, Any, None]:
    """A headless Chromium browser for testing HTML reports containing plotly graphs.

    The yielded object has method `render_report(report :str)` so that one can mimic rendering
    an HTML report containing plotly graphs.
    """
    chrome_service = Service(ChromeDriverManager(chrome_type=ChromeType.GOOGLE).install())
    chrome_options = Options()
    options = [
        "--headless",
        "--disable-gpu",
        "--window-size=1920,1200",
        "--ignore-certificate-errors",
        "--disable-extensions",
        "--no-sandbox",
        "--disable-dev-shm-usage",
    ]
    for option in options:
        chrome_options.add_argument(option)
    driver = WebDriver(service=chrome_service, options=chrome_options)

    def _render_report(self: WebDriver, report: str) -> bool:
        # include in the report the javascript script to handle Plotly <dvi> elements,
        # then save the HTML to a temporary file,
        # and finally render the temporary file in the headless browser
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Plotly Graphs</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
</head>
<body>
{report}
</body>
</html>
"""
        html_path = str(tmp_path / "report.html")
        open(html_path, "w").write(html_content)
        self.get(f"file://{html_path}")  # browser can't consume a python string, must be a valid URL
        return True  # if all goes well

    # Bind the custom _render_report() function as a method of the driver instance
    driver.render_report = _render_report.__get__(driver)
    yield driver
    # Teardown code
    driver.quit()  # Or driver.close(), but quit() is safer
