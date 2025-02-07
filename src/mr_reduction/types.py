"""
Compendium of custom type hints.

"""

# standard library imports
from typing import List, TypeAlias, Union

# third party imports
import mantid

"""
List of EvenWorkspace objects representing different cross-sections (Off_Off, Off_on, ...),
usually the result of running mantid algorithm MRFilterCrossSections on an input Nexus events file.
"""
CrossSectionEventWorkspaces: TypeAlias = List[mantid.dataobjects.EventWorkspace]

"""Any type of Mantid workspace"""
MantidWorkspace: TypeAlias = Union[str, mantid.api.Workspace]
MantidAlgorithmHistory: TypeAlias = mantid.api.AlgorithmHistory
