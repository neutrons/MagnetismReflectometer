# standard imports
import sys
from contextlib import contextmanager


@contextmanager
def add_to_sys_path(path):
    r""" "Temporarily dd `path` to the PYTHONPATH"""
    sys.path.insert(0, path)
    try:
        yield
    finally:
        sys.path.remove(path)
