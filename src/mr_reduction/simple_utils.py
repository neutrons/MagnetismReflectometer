# standard imports
import functools
import sys
from collections import namedtuple
from collections.abc import Mapping
from contextlib import contextmanager


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
