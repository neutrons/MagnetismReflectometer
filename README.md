# MR automated reduction
Automated reduction code based on Mantid.

 - Code under `mr_reduction` is common reduction code.
 - Code under `autoreduce` is the top-level code used by the post-processing.
 - Code under `livereduce` is the top-level code for live reduction.

# Configuration
The configuration file under `livereduce/livereduce.conf` needs to be place under `/etc` on
the live reduction node.

# TODO:
- Use polarizer/analyzer labels to make sure Off is always +.

# TODO - Mantid:
- Automate the selection of const-Q binning.
- Write output algorithm that takes in a group workspace.
