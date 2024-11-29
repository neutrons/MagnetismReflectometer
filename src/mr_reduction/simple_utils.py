# standard imports
import functools
import sys
from collections import namedtuple
from collections.abc import Mapping
from contextlib import contextmanager

# third party imports
from mantid.simpleapi import mtd

# mr_reduction imports
from mr_reduction.types import MantidWorkspace


@contextmanager
def add_to_sys_path(path):
    r""" "Temporarily dd `path` to the PYTHONPATH"""
    sys.path.insert(0, path)
    try:
        yield
    finally:
        sys.path.remove(path)


def namedtuplefy(func):
    r"""
    Decorator to transform the return dictionary of a function into
    a namedtuple

    Parameters
    ----------
    func: Function
        Function to be decorated
    name: str
        Class name for the namedtuple. If None, the name of the function
        will be used
    Returns
    -------
    Function
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        res = func(*args, **kwargs)
        if wrapper.nt is None:
            if isinstance(res, Mapping) is False:
                raise ValueError("Cannot namedtuplefy a non-dict")
            wrapper.nt = namedtuple(func.__name__ + "_nt", res.keys())
        return wrapper.nt(**res)

    wrapper.nt = None
    return wrapper


def workspace_handle(input_workspace: MantidWorkspace):
    return mtd[str(input_workspace)]


class SampleLogs:
    """
    Wrapper around Mantid's run object so that `SampleLogs(workspace)[property_name]`
    returns the first value of the property if it is a vector, or the value if it is a scalar.

    Mantid's default run object `workspace.getRun()[property_name]` returns the property object, not its value.
    Usually, we're interested in the property's value, not the object itself.

    With this wrapper, we would write:
        sample_logs = SampleLogs(workspace)
        value = sample_logs[property_name]  # value if scalar, first value if vector
    instead of:
        sample_logs = workspace.getRun()
        value = sample_logs.getProperty(property_name).value  # if scalar
        value = sample_logs.getProperty(property_name).firstValue()  # if vector
    """

    def __init__(self, input_workspace: MantidWorkspace):
        self._run = workspace_handle(input_workspace).getRun()

    def __getitem__(self, property_name):
        if self._run.hasProperty(property_name):
            p = self._run.getProperty(property_name)
            if hasattr(p, "firstValue"):
                return p.firstValue()
            return p.value

    def property(self, property_name):
        return self._run.getProperty(property_name)

    def mean(self, property_name) -> float:
        return self._run.getStatistics(property_name).mean
