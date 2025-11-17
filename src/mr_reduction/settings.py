import os
from typing import List, Union

"""
Reduction settings for MR
"""
# MANTID_PATH = ["/opt/mantid50/lib", "/opt/mantid50/bin"]
# MANTID_PATH = '/SNS/users/m2d/mantid_build_area/master_release/bin'


# Polarization Processing Variables
# live data lacks PV's "PolarizerState", "PolarizerVeto", "AnalyzerState", and "AnalyzerVeto"
# so we need to use the short names
class PolarizationLogs:
    POL_STATE: str = "SF1"  # a.k.a "PolarizerState"
    POL_VETO: str = "SF1_Veto"  # a.k.a "PolarizerVeto"
    ANA_STATE: str = "SF2"  # a.k.a "AnalyzerState"
    ANA_VETO: str = "SF2_Veto"  # a.k.a "AnalyzerVeto"


# Default TOF binning for histograms
TOF_MIN = 10000
TOF_MAX = 100000
TOF_BIN = 400.0


DIRECT_BEAM_DIR = "/SNS/REF_M/shared/autoreduce/direct_beams/"
GLOBAL_AR_DIR = "/SNS/REF_M/shared/autoreduce"


def nexus_data_dir(ipts: str) -> str:
    return "/SNS/REF_M/%(ipts)s/nexus" % {"ipts": ipts}
