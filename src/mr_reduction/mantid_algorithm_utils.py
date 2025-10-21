from mantid.api import PythonAlgorithm
from mantid.dataobjects import EventWorkspace


def mantid_algorithm_exec(algorithm_class: type[PythonAlgorithm], **kwargs) -> EventWorkspace | None:
    """Helper function for executing a Mantid-style algorithm.

    Parameters
    ----------
    algorithm_class:
        The algorithm class to execute
    **kwargs:
        Keyword arguments to set the algorithm properties.

    Returns
    -------
    Workspace or None:
        If ``OutputWorkspace`` is passed as a keyword argument,
        the value of the algorithm property ``OutputWorkspace`` will be returned
    """
    algorithm_instance = algorithm_class()
    assert hasattr(algorithm_instance, "PyInit"), f"{algorithm_class} is not a Mantid Python algorithm"
    algorithm_instance.PyInit()
    for name, value in kwargs.items():
        algorithm_instance.setProperty(name, value)
    algorithm_instance.PyExec()
    if "OutputWorkspace" in kwargs:
        return algorithm_instance.getProperty("OutputWorkspace").value
