# standard imports
import os
import sys

# add the path to directory `src/` so we can do imports such as
# `from mr_livereduce.polarization_analysisimport calculate_ratios`
this_module_path = sys.modules[__name__].__file__
repo_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(this_module_path))))
src_path = os.path.join(repo_path, "src", "mr_livereduce")
sys.path.append(src_path)

del src_path
del repo_path
del this_module_path
