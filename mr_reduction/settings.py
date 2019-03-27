"""
    Reduction settings for MR
"""
MANTID_PATH = "/opt/mantidnightly/bin"
#MANTID_PATH = '/SNS/users/m2d/mantid_build_area/master_release/bin'

# Polarization states
POL_STATE = "PolarizerState"
POL_VETO = "PolarizerVeto"
ANA_STATE = "AnalyzerState"
ANA_VETO = "AnalyzerVeto"

#POL_STATE = "SF1"
#ANA_STATE = "SF2"
#POL_VETO = "SF1_Veto"
#ANA_VETO = "SF2_Veto"

# Default TOF binning for histograms
TOF_MIN = 10000
TOF_MAX = 100000
TOF_BIN = 400.0

#AR_OUT_DIR_TEMPLATE = "/tmp"
AR_OUT_DIR_TEMPLATE = "/SNS/REF_M/%(ipts)s/shared/autoreduce/"
DATA_DIR_TEMPLATE = "/SNS/REF_M/%(ipts)s/nexus"
DIRECT_BEAM_DIR = "/SNS/REF_M/shared/autoreduce/direct_beams/"
GLOBAL_AR_DIR = "/SNS/REF_M/shared/autoreduce"
