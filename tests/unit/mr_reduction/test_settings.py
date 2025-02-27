# standard library imports
from unittest.mock import patch

# third party imports
import pytest

# mr_reduction imports
from mr_reduction.settings import collect_search_directories


def test_collect_search_directories():
    with patch("os.path.isdir", return_value=True):
        # Test with no extra paths
        assert collect_search_directories("IPTS-12345") == ["/SNS/REF_M/IPTS-12345/shared/autoreduce/"]

        # Test with a single extra path
        result = collect_search_directories("IPTS-12345", "/extra/path")
        assert result == ["/extra/path", "/SNS/REF_M/IPTS-12345/shared/autoreduce/"]

        # Test with multiple extra paths
        result = collect_search_directories("IPTS-12345", ["/extra/path1", "/extra/path2"])
        assert result == ["/extra/path1", "/extra/path2", "/SNS/REF_M/IPTS-12345/shared/autoreduce/"]

        # Test with duplicate paths
        result = collect_search_directories("IPTS-12345", ["/extra/path", "/extra/path"])
        assert result == ["/extra/path", "/SNS/REF_M/IPTS-12345/shared/autoreduce/"]

    with patch("os.path.isdir", side_effect=lambda x: x != "/non/existing/path"):
        # Test with non-existing path
        result = collect_search_directories("IPTS-12345", ["/extra/path", "/non/existing/path"])
        assert result == ["/extra/path", "/SNS/REF_M/IPTS-12345/shared/autoreduce/"]


if __name__ == "__main__":
    pytest.main([__file__])
