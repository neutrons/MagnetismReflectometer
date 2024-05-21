# standard imports
import time

# third party packages
import pytest


def test_data_server(data_server):
    filepath = data_server.path_to("data_server_test.txt")
    assert "tests/mr_reduction-data/data_server_test.txt" in filepath


if __name__ == "__main__":
    pytest.main([__file__])
