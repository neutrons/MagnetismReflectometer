"""
Accumulation workspace

To test: nc -l  31466 < REF_M_25640.adara
"""

from mantid import simpleapi

DEBUG = True
if DEBUG:
    logfile = open("/SNS/REF_M/shared/autoreduce/MR_live_outer.log", "a")
    logfile.write("Starting proc\n")

simpleapi.logger.notice("Starting proc")
try:
    simpleapi.CloneWorkspace(InputWorkspace=input, OutputWorkspace=output)  # noqa F821
except RuntimeError:
    return input  # noqa F706
