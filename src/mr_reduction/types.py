"""
Compendium of custom type hints.

"""

# standard library imports
from typing import List, TypeAlias, Union

# third party imports
import mantid
from mantid.api import WorkspaceGroup
from mantid.dataobjects import EventWorkspace

"""
List of EvenWorkspace objects representing different cross-sections (Off_Off, Off_on, ...),
usually the result of running filter_events.split_events on an input Nexus events file.
"""
CrossSectionEventWorkspaces: TypeAlias = List[mantid.dataobjects.EventWorkspace]

"""Any type of Mantid workspace, including its name"""
MantidWorkspace: TypeAlias = Union[str, mantid.api.Workspace]

MantidAlgorithmHistory: TypeAlias = mantid.api.AlgorithmHistory
