"""Compendium of custom type hints."""

import mantid

"""
List of EvenWorkspace objects representing different cross-sections (Off_Off, Off_on, ...),
usually the result of running filter_events.split_events on an input Nexus events file.
"""
type CrossSectionEventWorkspaces = list[mantid.dataobjects.EventWorkspace]


"""Any type of Mantid workspace, including its name"""
type MantidWorkspace = str | mantid.api.Workspace


type MantidAlgorithmHistory = mantid.api.AlgorithmHistory
