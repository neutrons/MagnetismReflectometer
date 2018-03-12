#pylint: disable=bare-except
"""
    Find a suitable direct beam file for a data set.
"""
from __future__ import (absolute_import, division, print_function)
import sys
import os
import json
import math
import logging

sys.path.insert(0,'/opt/mantidnightly/bin')
import mantid
from mantid.simpleapi import *

from .data_info import DataInfo


class DirectBeamFinder(object):
    """
    """
    def __init__(self, scatt_ws, skip_slits=False, allow_later_runs=False,
                 tolerance=0.2, huber_x_cut=0, experiment=''):
        """
            Extract information from the given workspace
            :param workspace scatt_ws: workspace to find a direct beam for
        """
        self.data_dir = "/SNS/REF_M/%s/data" % experiment
        self.ar_dir = "/SNS/REF_M/%s/shared/autoreduce" % experiment
        self.db_dir = "/SNS/REF_M/shared/autoreduce/direct_beams/"

        self.tolerance = tolerance
        self.huber_x_cut = huber_x_cut
        self.skip_slits = skip_slits
        self.allow_later_runs = allow_later_runs

        self.wl = scatt_ws.getRun().getProperty("LambdaRequest").getStatistics().mean
        self.s1 = scatt_ws.getRun().getProperty("S1HWidth").getStatistics().mean
        self.s2 = scatt_ws.getRun().getProperty("S2HWidth").getStatistics().mean
        self.s3 = scatt_ws.getRun().getProperty("S3HWidth").getStatistics().mean
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
                summary_path = os.path.join(self.ar_dir, item+'.json')
                if not os.path.isfile(summary_path):
                    entry='entry'
                    is_valid = False
                    for entry in ['entry', 'entry-Off_Off', 'entry-On_Off', 'entry-Off_On', 'entry-On_On']:
                        try:
                            ws = LoadEventNexus(Filename=os.path.join(self.data_dir, item),
                                                NXentryName=entry,
                                                MetaDataOnly=False,
                                                OutputWorkspace="meta_data")
                            if ws.getNumberEvents() > 1000:
                                is_valid = True
                                break
                        except:
                            # If there's no data in the entry, LoadEventNexus will fail.
                            # This is expected so we just need to proceed with the next entry.
                            logging.debug("Finding direct beam: %s [%s]: %s", item, entry, sys.exc_value)

                    if not is_valid:
                        meta_data = dict(run=0, invalid=True)
                        fd = open(summary_path, 'w')
                        fd.write(json.dumps(meta_data))
                        fd.close()
                        continue

                    run_number = int(ws.getRunNumber())
                    sangle = ws.getRun().getProperty("SANGLE").getStatistics().mean
                    dangle = ws.getRun().getProperty("DANGLE").getStatistics().mean
                    dangle0 = ws.getRun().getProperty("DANGLE0").getStatistics().mean
                    direct_beam_pix = ws.getRun().getProperty("DIRPIX").getStatistics().mean
                    det_distance = ws.getRun().getProperty("SampleDetDis").getStatistics().mean / 1000.0
                    pixel_width = 0.0007

                    huber_x = ws.getRun().getProperty("HuberX").getStatistics().mean
                    wl = ws.getRun().getProperty("LambdaRequest").getStatistics().mean
                    s1 = ws.getRun().getProperty("S1HWidth").getStatistics().mean
                    s2 = ws.getRun().getProperty("S2HWidth").getStatistics().mean
                    s3 = ws.getRun().getProperty("S3HWidth").getStatistics().mean
                    try:
                        data_info = DataInfo(ws, entry, huber_x_cut=self.huber_x_cut)
                        peak_pos = data_info.peak_position if data_info.peak_position is not None else direct_beam_pix
                    except:
                        data_info = None
                        peak_pos = direct_beam_pix
                    theta_d = (dangle - dangle0) / 2.0
                    theta_d += ((direct_beam_pix - peak_pos) * pixel_width) * 180.0 / math.pi / (2.0 * det_distance)

                    meta_data = dict(theta_d=theta_d, run=run_number, wl=wl, s1=s1, s2=s2, s3=s3, dangle=dangle, sangle=sangle, huber_x=huber_x)
                    fd = open(summary_path, 'w')
                    fd.write(json.dumps(meta_data))
                    fd.close()
                    if data_info is not None and data_info.data_type == 0:
                        standard_path = os.path.join(self.db_dir, item+'.json')
                        fd = open(standard_path, 'w')
                        fd.write(json.dumps(meta_data))
                        fd.close()

    def search_dir(self, db_dir):
        """
            Look for json files in the given directory and try to find
            a suitable direct beam.
            :param str db_dir: directory path
        """
        closest = None
        for item in os.listdir(db_dir):
            if item.endswith(".json"):
                summary_path = os.path.join(db_dir, item)
                fd = open(summary_path, 'r')
                meta_data = json.loads(fd.read())
                fd.close()
                if 'invalid' in meta_data.keys():
                    continue
                run_number = meta_data['run']
                dangle = meta_data['dangle']
                theta_d = meta_data['theta_d'] if 'theta_d' in meta_data else 0
                sangle = meta_data['sangle'] if 'sangle' in meta_data else 0

                wl = meta_data['wl']
                s1 = meta_data['s1']
                s2 = meta_data['s2']
                s3 = meta_data['s3']
                if 'huber_x' in meta_data:
                    huber_x = meta_data['huber_x']
                else:
                    huber_x = 0
                #if run_number == run_ or (dangle > self.tolerance and huber_x < 9) :
                if run_number == self.run or ((theta_d > self.tolerance or sangle > self.tolerance) and huber_x < self.huber_x_cut):
                    continue
                # If we don't allow runs taken later than the run we are processing...
                if not self.allow_later_runs and run_number > self.run:
                    continue

                if math.fabs(wl-self.wl) < self.tolerance \
                    and (self.skip_slits is True or \
                    (math.fabs(s1-self.s1) < self.tolerance \
                    and math.fabs(s2-self.s2) < self.tolerance \
                    and math.fabs(s3-self.s3) < self.tolerance)):
                    if closest is None:
                        closest = run_number
                    elif abs(run_number-self.run) < abs(closest-self.run):
                        closest = run_number

        return closest