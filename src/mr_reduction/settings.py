"""
Reduction settings for MR
"""
# MANTID_PATH = ["/opt/mantid50/lib", "/opt/mantid50/bin"]
# MANTID_PATH = '/SNS/users/m2d/mantid_build_area/master_release/bin'

# Polarization states
POL_STATE = "PolarizerState"
POL_VETO = "PolarizerVeto"
ANA_STATE = "AnalyzerState"
ANA_VETO = "AnalyzerVeto"

# POL_STATE = "SF1"
# ANA_STATE = "SF2"
# POL_VETO = "SF1_Veto"
# ANA_VETO = "SF2_Veto"

# Default TOF binning for histograms
TOF_MIN = 10000
TOF_MAX = 100000
TOF_BIN = 400.0


def ar_out_dir(ipts: str) -> str:
    return "/SNS/REF_M/%(ipts)s/shared/autoreduce/" % {"ipts": ipts}


def nexus_data_dir(ipts: str) -> str:
    return "/SNS/REF_M/%(ipts)s/nexus" % {"ipts": ipts}


DIRECT_BEAM_DIR = "/SNS/REF_M/shared/autoreduce/direct_beams/"
GLOBAL_AR_DIR = "/SNS/REF_M/shared/autoreduce"
