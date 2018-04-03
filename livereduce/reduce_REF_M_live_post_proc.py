#pylint: disable=bare-except
import sys
from mantid import simpleapi
sys.path.append("/SNS/REF_M/shared/autoreduce")
from mr_reduction import mr_reduction as refm

# Clean up zero-length logs, which should not exist in the real live data
run_obj = input.run()
keys_live = run_obj.keys()
for k in keys_live:
    if hasattr(run_obj[k], 'size') and run_obj[k].size() == 0:
        print k
        run_obj[k] = 0.0

try:
    red = refm.ReductionProcess(data_run=input.getRunNumber(), data_ws = input)
    red.reduce()
except:
    print("Problem processing live workspace")
    simpleapi.CloneWorkspace(InputWorkspace=input, OutputWorkspace=output)
