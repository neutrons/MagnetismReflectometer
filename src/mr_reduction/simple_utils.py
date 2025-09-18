import functools
import sys
from collections import namedtuple
from collections.abc import Mapping
from contextlib import contextmanager

from mantid.simpleapi import mtd

from mr_reduction.types import MantidWorkspace


@contextmanager
def add_to_sys_path(path, clean_module_reduce_REF_M=True):
    r"""Temporarily add `path` to the PYTHONPATH.

    Parameters
    ----------
    path : str
        The path to be added to the PYTHONPATH.
    clean_module_reduce_REF_M : bool, optional
        If True, remove the "reduce_REF_M" module from sys.modules if it exists,
        so it can be re-imported. Default is True.

    Examples
    --------
    with add_to_sys_path(tempdir):
        from reduce_REF_M import reduction_user_options
    """
    sys.path.insert(0, path)
    if clean_module_reduce_REF_M and ("reduce_REF_M" in sys.modules):
        del sys.modules["reduce_REF_M"]  # need to re-import
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
    """Syntactic sugar for a more descriptive operation"""
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

    def __contains__(self, property_name):
        return self._run.hasProperty(property_name)

    def __getitem__(self, property_name):
        value = self._run.getProperty(property_name).value
        if isinstance(value, (int, float, str)):  # scalar sample logs can only be one of these three types
            return value
        else:
            return value[0]  # return the first value

    def property(self, property_name: str):
        """property object for the given property name"""
        return self._run.getProperty(property_name)

    def mean(self, property_name) -> float:
        """mean value of the property"""
        return self._run.getStatistics(property_name).mean
