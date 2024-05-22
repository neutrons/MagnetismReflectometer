# pylint: disable=bare-except, invalid-name, too-many-nested-blocks, too-many-arguments, too-many-instance-attributes, too-many-locals, too-few-public-methods
"""
Find a suitable direct beam file for a data set.
"""

from __future__ import absolute_import, division, print_function

import json
import logging
import math
import sys

from mantid.simpleapi import *

from .data_info import DataInfo
from .settings import DIRECT_BEAM_DIR, ar_out_dir, nexus_data_dir


class DirectBeamFinder(object):
    """ """

    def __init__(self, scatt_ws, skip_slits=False, allow_later_runs=False, tolerance=0.2, experiment=""):
        """
        Extract information from the given workspace
        :param workspace scatt_ws: workspace to find a direct beam for
        """
        self.data_dir = nexus_data_dir(experiment)
        self.ar_dir = ar_out_dir(experiment)
        self.db_dir = DIRECT_BEAM_DIR

        self.tolerance = tolerance
        self.skip_slits = skip_slits
        self.allow_later_runs = allow_later_runs

        self.wl = scatt_ws.getRun().getProperty("LambdaRequest").getStatistics().mean
        if "BL4A:Mot:S1:X:Gap" in scatt_ws.getRun():
            self.s1 = scatt_ws.getRun()["BL4A:Mot:S1:X:Gap"].getStatistics().mean
            self.s2 = scatt_ws.getRun()["BL4A:Mot:S2:X:Gap"].getStatistics().mean
            self.s3 = scatt_ws.getRun()["BL4A:Mot:S3:X:Gap"].getStatistics().mean
        else:
            self.s1 = scatt_ws.getRun()["S1HWidth"].getStatistics().mean
            self.s2 = scatt_ws.getRun()["S2HWidth"].getStatistics().mean
            self.s3 = scatt_ws.getRun()["S3HWidth"].getStatistics().mean
        self.run = int(scatt_ws.getRunNumber())

    def search(self, skip_slits=False, allow_later_runs=False):
        """
        Update our data information, and search for a suitable direct beam file.
        """
        self.skip_slits = skip_slits
        self.allow_later_runs = allow_later_runs

        # Update the meta-data about the experiment data
        if os.path.isdir(self.data_dir):
            self.update_database()

        closest = None
        # Look in the autoreduction directory
        if closest is None and os.path.isdir(self.ar_dir):
            closest = self.search_dir(self.ar_dir)

        # Look in the top level storage place
        if closest is None and os.path.isdir(self.db_dir):
            closest = self.search_dir(self.db_dir)

        return closest

    def update_database(self):
        """
        Create meta-data json files from data sets
        """
        for item in os.listdir(self.data_dir):
            if item.endswith("_event.nxs") or item.endswith("h5"):
                summary_path = os.path.join(self.ar_dir, item + ".json")
                if not os.path.isfile(summary_path):
                    entry = "entry"
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

                    if not is_valid:
                        meta_data = dict(run=0, invalid=True)
                        fd = open(summary_path, "w")
                        fd.write(json.dumps(meta_data))
                        fd.close()
                        continue

                    try:
                        run_number = int(ws.getRunNumber())
                        sangle = ws.getRun().getProperty("SANGLE").getStatistics().mean
                        dangle = ws.getRun().getProperty("DANGLE").getStatistics().mean
                        direct_beam_pix = ws.getRun().getProperty("DIRPIX").getStatistics().mean

                        wl = ws.getRun().getProperty("LambdaRequest").getStatistics().mean
                        if "BL4A:Mot:S1:X:Gap" in ws.getRun():
                            s1 = ws.getRun()["BL4A:Mot:S1:X:Gap"].getStatistics().mean
                            s2 = ws.getRun()["BL4A:Mot:S2:X:Gap"].getStatistics().mean
                            s3 = ws.getRun()["BL4A:Mot:S3:X:Gap"].getStatistics().mean
                        else:
                            s1 = ws.getRun()["S1HWidth"].getStatistics().mean
                            s2 = ws.getRun()["S2HWidth"].getStatistics().mean
                            s3 = ws.getRun()["S3HWidth"].getStatistics().mean
                        try:
                            data_info = DataInfo(ws, entry)
                            peak_pos = (
                                data_info.peak_position if data_info.peak_position is not None else direct_beam_pix
                            )
                        except:  # noqa E722
                            data_info = None
                            peak_pos = direct_beam_pix

                        theta_d = MRGetTheta(ws, SpecularPixel=peak_pos, UseSANGLE=False) * 180.0 / math.pi
                        data_type = -1
                        try:
                            data_type = int(ws.getRun().getProperty("data_type").value[0])
                            if data_type == 1:
                                theta_d = 0
                        except:  # noqa E722
                            logging.info("Not data type information")

                        meta_data = dict(
                            data_type=data_type,
                            theta_d=theta_d,
                            run=run_number,
                            wl=wl,
                            s1=s1,
                            s2=s2,
                            s3=s3,
                            dangle=dangle,
                            sangle=sangle,
                        )
                        fd = open(summary_path, "w")
                        fd.write(json.dumps(meta_data))
                        fd.close()
                        if data_info is not None and data_info.data_type == 0:
                            standard_path = os.path.join(self.db_dir, item + ".json")
                            fd = open(standard_path, "w")
                            fd.write(json.dumps(meta_data))
                            fd.close()
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
                meta_data = json.load(fd)
            if "invalid" in meta_data.keys():
                continue
            run_number = meta_data["run"]
            # If we don't allow runs taken later than the run we are processing...
            if not self.allow_later_runs and run_number > self.run:
                continue

            data_type = meta_data["data_type"] if "data_type" in meta_data else -1
            # Data type = 1 is for direct beams
            if run_number == self.run or not data_type == 1:
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
