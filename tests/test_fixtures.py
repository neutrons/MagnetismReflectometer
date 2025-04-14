# standard imports
import os

# third party packages
import pytest


@pytest.mark.datarepo()
def test_data_server(data_server):
    filepath = data_server.path_to("data_server_test.txt")
    assert "tests/mr_reduction-data/data_server_test.txt" in filepath
    assert "Templated autoreduction script for REF_M" in open(data_server.path_to_template, "r").read()
    events = data_server.load_events("REF_M_42535.nxs.h5")
    assert events.getNumberEvents() == 593081


def test_autoreduction_script(autoreduction_script):
    script = autoreduction_script()
    assert os.path.isfile(script)


if __name__ == "__main__":
    pytest.main([__file__])
