# pylint: disable=bare-except, invalid-name, too-many-nested-blocks, too-many-arguments, too-many-instance-attributes, too-many-locals, too-few-public-methods
"""
Find a suitable direct beam file for a data set.
"""

# standard library imports
import json
import logging
import math
import os
import sys
from json.decoder import JSONDecodeError

# third party imports
from mantid.simpleapi import LoadEventNexus, MRGetTheta

# mr_reduction imports
from mr_reduction.data_info import DataInfo, DataType
from mr_reduction.settings import DIRECT_BEAM_DIR, nexus_data_dir
from mr_reduction.simple_utils import SampleLogs, workspace_handle
from mr_reduction.types import MantidWorkspace


class DirectBeamFinder:
    """
    Class to find a suitable direct beam file for a given scattering workspace.

    This class extracts information from the given workspace and searches for a matching direct beam run
    based on various criteria such as wavelength, slit gaps, and experiment identifier.
    """

    def __init__(
        self,
        scatt_ws: MantidWorkspace,
        experiment: str,
        ar_dir: str,
        skip_slits=False,
        allow_later_runs=False,
        tolerance=0.2,
    ):
        """
        Initialize the DirectBeamFinder with the given scattering workspace and parameters.

        This method extracts necessary information from the given workspace and sets up the
        directories and parameters for searching a suitable direct beam run.

        Parameters
        ----------
        scatt_ws : MantidWorkspace
            The scattering workspace to match with a direct beam run.
        experiment : str
            The experiment identifier (e.g., "IPTS-12345"). Default is an empty string.
        ar_dir : str
            Directory to search for autoreduced data.
            In autoreduce mode, it will be /SN/REF_M/IPTS-XXXX/shared/autoreduce/
        skip_slits : bool, optional
            Whether to skip the slit gap matching. Default is False.
        allow_later_runs : bool, optional
            Whether to allow later runs in the search for a direct beam. Default is False.
        tolerance : float, optional
            Tolerance for matching the direct beam run based on wavelength and slit gaps. Default is 0.2.
        """
        assert "IPTS-" in experiment, f"Experiment identifier must contain 'IPTS-': {experiment}"
        # Directory where the Nexus data files are stored.
        self.data_dir = nexus_data_dir(experiment)
        # Directory where the autoreduced data files are stored.
        self.ar_dir = ar_dir
        # Directory where the direct beam files are stored.
        self.db_dir = DIRECT_BEAM_DIR
        # Tolerance for matching the direct beam run based on wavelength and slit gaps.
        self.tolerance = tolerance
        # Whether to skip the slit gap matching.
        self.skip_slits = skip_slits
        # Whether to allow later runs in the search for a direct beam.
        self.allow_later_runs = allow_later_runs
        sample_logs = SampleLogs(scatt_ws)
        self.wl = sample_logs.mean("LambdaRequest")
        if "BL4A:Mot:S1:X:Gap" in sample_logs:
            self.s1 = sample_logs.mean("BL4A:Mot:S1:X:Gap")  # Slit 1 gap of the scattering workspace.
            self.s2 = sample_logs.mean("BL4A:Mot:S2:X:Gap")
            self.s3 = sample_logs.mean("BL4A:Mot:S3:X:Gap")
        else:
            self.s1 = sample_logs.mean("S1HWidth")
            self.s2 = sample_logs.mean("S2HWidth")
            self.s3 = sample_logs.mean("S3HWidth")
        self.run = int(workspace_handle(scatt_ws).getRunNumber())

    def search(self, skip_slits=False, allow_later_runs=False):
        """
        Search for a suitable direct beam file.

        This method first updates the meta-data about the experiment data,
        then searches for a matching direct beam run based on various criteria such as wavelength,
        slit gaps, and experiment identifier.
        It first looks in the autoreduction directory and then in the top-level storage directory
        containing metadata for all direct-beam runs.
        The search will stop as soon as a suitable direct beam run is found.

        Parameters
        ----------
        skip_slits : bool, optional
            Whether to skip the slit gap matching. Default is False.
        allow_later_runs : bool, optional
            Whether to allow later runs in the search for a direct beam. Default is False.

        Returns
        -------
        closest : str or None
            The path to the closest matching direct beam file, or None if no suitable file is found.
        """
        self.skip_slits = skip_slits
        self.allow_later_runs = allow_later_runs

        # Update the meta-data about the experiment data
        if os.path.isdir(self.data_dir):
            self.update_database()

        closest = None

        # Look in the autoreduction directory first
        if closest is None and os.path.isdir(self.ar_dir):
            closest = self.search_dir(self.ar_dir)

        # Look in the top level storage place, the directory containing metadata for all direct-beam runs
        if closest is None and os.path.isdir(self.db_dir):
            closest = self.search_dir(self.db_dir)

        return closest

    def update_database(self):
        """
        Create a metadata JSON file from each event Nexus file in the data directory.

        This method iterates over the event Nexus files in the data directory `data_dir`
        and queries the autoreduction directory (`ar_dir`) for the corresponding metadata file.
        If no metadata file is found, the method extracts the necessary information from the event Nexus file
        and writes it to a new metadata JSON file in the autoreduction directory.
        if the event Nexus file corresponds to a direct-beam run,
        then the method also writes the metadata to the directory of direct-beam metadata (`db_dir`).
        """
        for item in os.listdir(self.data_dir):
            # example of valid filenames: "REF_M_30900_event.nxs", "REF_M_30900.nxs.h5"
            if item.endswith("_event.nxs") or item.endswith("h5"):
                # Check if the summary file already exists in the autoreduction directory, otherwise create it
                metadata_path = os.path.join(self.ar_dir, item + ".json")
                if os.path.isfile(metadata_path) is False:
                    # Check if the file is valid by trying to load any of its cross-sections with LoadEventNexus
                    is_valid = False
                    for entry in ["entry", "entry-Off_Off", "entry-On_Off", "entry-Off_On", "entry-On_On"]:
                        try:
                            ws = LoadEventNexus(
                                Filename=os.path.join(self.data_dir, item),
                                NXentryName=entry,
                                MetaDataOnly=False,
                                OutputWorkspace="meta_data",
                            )
                            if ws.getNumberEvents() > 1000:
                                is_valid = True
                                break
                        except:  # noqa E722
                            # If there's no data in the entry, LoadEventNexus will fail.
                            # This is expected so we just need to proceed with the next entry.
                            logging.debug("Finding direct beam: %s [%s]: %s", item, entry, sys.exc_info()[1])

                    # If the file is not valid, flag it as such and continue to the next events file
                    if is_valid is False:
                        meta_data = dict(run=0, invalid=True)
                        fd = open(metadata_path, "w")
                        fd.write(json.dumps(meta_data))
                        fd.close()
                        continue

                    # If the file is valid, proceed to extract the meta-data
                    try:
                        run_number = int(ws.getRunNumber())
                        sample_logs = SampleLogs(ws)
                        sangle = sample_logs.mean("SANGLE")
                        dangle = sample_logs.mean("DANGLE")
                        direct_beam_pix = sample_logs.mean("DIRPIX")

                        wl = sample_logs.mean("LambdaRequest")
                        if "BL4A:Mot:S1:X:Gap" in sample_logs:
                            s1 = sample_logs.mean("BL4A:Mot:S1:X:Gap")
                            s2 = sample_logs.mean("BL4A:Mot:S2:X:Gap")
                            s3 = sample_logs.mean("BL4A:Mot:S3:X:Gap")
                        else:
                            s1 = sample_logs.mean("S1HWidth")
                            s2 = sample_logs.mean("S2HWidth")
                            s3 = sample_logs.mean("S3HWidth")
                        try:
                            # assume only one peak, so that peak_number = 1. This is true for direct-beam runs.
                            data_info = DataInfo(ws, entry, peak_number=1)
                            peak_pos = (
                                data_info.peak_position if data_info.peak_position is not None else direct_beam_pix
                            )
                        except:  # noqa E722
                            data_info = None
                            peak_pos = direct_beam_pix

                        theta_d = MRGetTheta(ws, SpecularPixel=peak_pos, UseSANGLE=False) * 180.0 / math.pi
                        data_type = DataType.UNKNOWN
                        try:
                            data_type = DataType.from_workspace(ws)
                            if data_type == DataType.DIRECT_BEAM:
                                theta_d = 0  # scattering angle two-theta is zero for direct beam
                        except:  # noqa E722
                            logging.info("No data type information in the Sample logs")

                        meta_data = dict(
                            data_type=data_type.value,
                            theta_d=theta_d,
                            run=run_number,
                            wl=wl,
                            s1=s1,
                            s2=s2,
                            s3=s3,
                            dangle=dangle,
                            sangle=sangle,
                        )

                        # Write the meta-data to the summary file in the first autoreduction directory
                        with open(metadata_path, "w") as fd:
                            fd.write(json.dumps(meta_data))

                        # If a direct-beam run, also write it to the directory of direct-beam metadata
                        if (data_info is not None) and (data_info.data_type == DataType.DIRECT_BEAM):
                            standard_path = os.path.join(self.db_dir, item + ".json")
                            with open(standard_path, "w") as fd:
                                fd.write(json.dumps(meta_data))
                    except:  # noqa E722
                        logging.info("Could not process run %s\n %s", run_number, sys.exc_info()[1])

    def search_dir(self, db_dir):
        """
        Look for json files in the given directory and try to find
        a suitable direct beam.
        :param str db_dir: directory path
        """
        closest = None
        for item in os.listdir(db_dir):
            if not item.endswith("nxs.h5.json"):
                continue
            summary_path = os.path.join(db_dir, item)
            with open(summary_path, "r") as fd:
                try:
                    meta_data = json.load(fd)
                except JSONDecodeError as e:
                    raise ValueError(f"Could not read {summary_path}: {e}")
            if "invalid" in meta_data.keys():
                continue
            run_number = meta_data["run"]
            # If we don't allow runs taken later than the run we are processing...
            if not self.allow_later_runs and run_number > self.run:
                continue

            data_type = DataType.from_value(meta_data["data_type"]) if "data_type" in meta_data else DataType.UNKNOWN
            # Data type = 1 is for direct beams
            if (run_number == self.run) or (data_type != DataType.DIRECT_BEAM):
                continue

            wl = meta_data["wl"]
            s1 = meta_data["s1"]
            s2 = meta_data["s2"]
            s3 = meta_data["s3"]

            if math.fabs(wl - self.wl) < self.tolerance and (
                self.skip_slits is True
                or (
                    math.fabs(s1 - self.s1) < self.tolerance
                    and math.fabs(s2 - self.s2) < self.tolerance
                    and math.fabs(s3 - self.s3) < self.tolerance
                )
            ):
                if closest is None:
                    closest = run_number
                elif abs(run_number - self.run) < abs(closest - self.run):
                    closest = run_number

        return closest
