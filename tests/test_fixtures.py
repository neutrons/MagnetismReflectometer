# standard imports
import os

# third party packages
import pytest


@pytest.mark.datarepo()
def test_data_server(data_server):
    filepath = data_server.path_to("data_server_test.txt")
    assert "tests/mr_reduction-data/data_server_test.txt" in filepath
    assert "Templated autoreduction script for REF_M" in open(data_server.path_to_template, "r").read()


if __name__ == "__main__":
    pytest.main([__file__])
