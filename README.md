# MR automated reduction
Automated reduction code based on Mantid.

 - Code under `mr_reduction` is common reduction code.
 - Code under `autoreduce` is the top-level code used by the post-processing.
 - Code under `livereduce` is the top-level code for live reduction.

# Configuration
The configuration file under `autoreduce/livereduce.conf` needs to be place under `/etc` on
the live reduction node.

# TODO:
- Update polarizer/analyzer PV names.
- Use polarizer/analyzer labels to make sure Off is always +.

# TODO - Live Reduction
- Allow a workspace as the input to mr_reduction rather than a file.

# TODO - Mantid:
- Automate the selection of const-Q binning.
- Write output algorithm that takes in a group workspace.

# Done:
- Common peak ranges: pick the cross-section with the highest count and use its peak definition for the other ones.
- Q resolution (currently done in reflectivity_output.py).
- Refactor MRInspectData, add a property for the event number cut-off.
