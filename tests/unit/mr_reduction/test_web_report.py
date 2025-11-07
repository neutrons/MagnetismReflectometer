from unittest.mock import MagicMock, mock_open, patch

import pytest

from mr_reduction.web_report import html_wrapper, save_report, upload_report


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


class TestSaveReport:
    """Test cases for the save_report function"""

    def test_save_report_single_string(self):
        """Test save_report with a single string report"""
        report = "<div>Test report content</div>"
        file_path = "/tmp/test_report.html"

        with (
            patch("mr_reduction.web_report.open", mock_open()) as mock_file,
            patch("mr_reduction.web_report.pyo.get_plotlyjs_version", return_value="5.24.1"),
            patch("mr_reduction.web_report.requests.head") as mock_head,
        ):
            # Mock successful CDN check
            mock_head.return_value.status_code = 200

            save_report(report, file_path)

            # Check that the file was opened with correct path and mode
            mock_file.assert_called_once_with(file_path, "w", encoding="utf-8")

            # Get the written content
            handle = mock_file()
            written_content = "".join(call.args[0] for call in handle.write.call_args_list)

            # Verify the content includes the report wrapped in HTML
            assert report in written_content
            assert "<!DOCTYPE html>" in written_content
            assert '<script src="https://cdn.plot.ly/plotly-5.24.1.js"></script>' in written_content
            assert "</body>" in written_content
            assert "</html>" in written_content

    def test_save_report_list_of_strings(self):
        """Test save_report with a list of report strings"""
        reports = ["<div>Report 1</div>", "<div>Report 2</div>", "<table><tr><td>Data</td></tr></table>"]
        file_path = "/tmp/test_report_list.html"

        with (
            patch("mr_reduction.web_report.open", mock_open()) as mock_file,
            patch("mr_reduction.web_report.pyo.get_plotlyjs_version", return_value="5.24.1"),
            patch("mr_reduction.web_report.requests.head") as mock_head,
        ):
            # Mock successful CDN check
            mock_head.return_value.status_code = 200

            save_report(reports, file_path)

            # Get the written content
            handle = mock_file()
            written_content = "".join(call.args[0] for call in handle.write.call_args_list)

            # Verify all reports are included
            for report in reports:
                assert report in written_content

            # Verify HTML structure
            assert "<!DOCTYPE html>" in written_content
            assert '<script src="https://cdn.plot.ly/plotly-5.24.1.js"></script>' in written_content

    def test_save_report_with_plotly_version_fallback(self):
        """Test save_report falls back to default version when CDN check fails"""
        report = "<div>Test report</div>"
        file_path = "/tmp/test_report_fallback.html"

        with (
            patch("mr_reduction.web_report.open", mock_open()) as mock_file,
            patch("mr_reduction.web_report.pyo.get_plotlyjs_version", return_value="99.99.99"),
            patch("mr_reduction.web_report.requests.head") as mock_head,
        ):
            # Simulate CDN not having the version
            mock_head.return_value.status_code = 404

            save_report(report, file_path)

            # Get the written content
            handle = mock_file()
            written_content = "".join(call.args[0] for call in handle.write.call_args_list)

            # Should fall back to version 3.0.0
            assert '<script src="https://cdn.plot.ly/plotly-3.0.0.js"></script>' in written_content


class TestUploadReport:
    """Test cases for the upload_report function"""

    def test_upload_report_single_string(self):
        """Test upload_report with a single string report"""
        report = "<div>Test report for upload</div>"
        run_number = 12345

        with patch("mr_reduction.web_report.publish_plot") as mock_publish:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_publish.return_value = mock_response

            result = upload_report(report, run_number)

            # Verify publish_plot was called with correct parameters
            mock_publish.assert_called_once_with("REF_M", run_number, files={"file": report})

            # Verify the response is returned
            assert result == mock_response
            assert result.status_code == 200

    def test_upload_report_list_of_strings(self):
        """Test upload_report with a list of report strings"""
        reports = ["<div>Report 1</div>", "<div>Report 2</div>", "<table><tr><td>Data</td></tr></table>"]
        run_number = "67890"

        with patch("mr_reduction.web_report.publish_plot") as mock_publish:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_publish.return_value = mock_response

            result = upload_report(reports, run_number)

            # Verify all reports are concatenated
            expected_composite = "\n".join(reports)
            mock_publish.assert_called_once_with("REF_M", run_number, files={"file": expected_composite})

            assert result == mock_response

    def test_upload_report_no_html_wrapper(self):
        """Test that upload_report does NOT wrap the report in HTML"""
        report = "<div>Raw report content</div>"
        run_number = 11111

        with patch("mr_reduction.web_report.publish_plot") as mock_publish:
            mock_publish.return_value = MagicMock()

            upload_report(report, run_number)

            # Get the actual content sent to publish_plot
            call_args = mock_publish.call_args
            uploaded_content = call_args.kwargs["files"]["file"]

            # Verify the content does NOT include HTML wrapper elements
            assert "<!DOCTYPE html>" not in uploaded_content
            assert "<html" not in uploaded_content
            assert "<script src=" not in uploaded_content
            assert "</body>" not in uploaded_content
            assert "</html>" not in uploaded_content

            # But should contain the raw report
            assert report in uploaded_content

    def test_upload_report_with_integer_run_number(self):
        """Test upload_report with integer run number"""
        report = "<div>Test</div>"
        run_number = 98765

        with patch("mr_reduction.web_report.publish_plot") as mock_publish:
            mock_publish.return_value = MagicMock()

            upload_report(report, run_number)

            # Verify integer run number is accepted
            mock_publish.assert_called_once()
            assert mock_publish.call_args.args[1] == run_number

    def test_upload_report_with_string_run_number(self):
        """Test upload_report with string run number"""
        report = "<div>Test</div>"
        run_number = "98765"

        with patch("mr_reduction.web_report.publish_plot") as mock_publish:
            mock_publish.return_value = MagicMock()

            upload_report(report, run_number)

            # Verify string run number is accepted
            mock_publish.assert_called_once()
            assert mock_publish.call_args.args[1] == run_number


if __name__ == "__main__":
    pytest.main([__file__])
