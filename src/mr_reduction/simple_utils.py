# standard imports
import functools
import sys
from collections import namedtuple
from collections.abc import Mapping
from contextlib import contextmanager


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
