"""
Accumulation workspace

To test: nc -l  31466 < REF_M_25640.adara
"""

from mantid import simpleapi

simpleapi.logger.notice("Starting proc")
input_workspace = None
output_workspace = None
try:
    simpleapi.CloneWorkspace(InputWorkspace=input_workspace, OutputWorkspace=output_workspace)
except:  # noqa E722
    output_workspace = input_workspace
