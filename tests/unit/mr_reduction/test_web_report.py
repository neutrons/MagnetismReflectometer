from unittest.mock import patch

import pytest

from mr_reduction.web_report import html_wrapper


class TestHtmlWrapper:
    """Test cases for the html_wrapper function"""

    def test_html_wrapper(self):
        """Test html_wrapper with multiple div elements"""
        report = "<table><tr><td>Table data</td></tr></table><div>First div</div><div>Second div</div>"
        with patch("mr_reduction.web_report.pyo.get_plotlyjs_version", return_value="3.0.0"):
            result = html_wrapper(report)
        assert report in result
        assert '<script src="https://cdn.plot.ly/plotly-3.0.0.js"></script>' in result

    def test_default_url(self):
        """There's no Plotly version 1.2.3, so default to 3.0.0"""
        report = "<table><tr><td>Table data</td></tr></table><div>First div</div><div>Second div</div>"
        with patch("mr_reduction.web_report.pyo.get_plotlyjs_version", return_value="1.2.3"):
            result = html_wrapper(report)
            assert '<script src="https://cdn.plot.ly/plotly-3.0.0.js"></script>' in result

    def test_special_characters(self):
        """Test html_wrapper with special characters in report"""
        report = "<div>Content with &amp; special chars &lt; &gt;</div>"
        result = html_wrapper(report)
        assert report in result  # Original content should be preserved


if __name__ == "__main__":
    pytest.main([__file__])
