# standard imports
import os
import string

# third party imports
import pytest

# mr_reduction imports
from mr_reduction.simple_utils import add_to_sys_path


def test_template(data_server, tempdir):
    r"""Substitute values in the templates as in done in the post-processing agent"""
    # Options for all peaks in the run
    common = {
        "plot_in_2D": True,
        "use_const_q": True,
        "q_step": -0.02,
        "use_sangle": True,
        "fit_peak_in_roi": False,
        "peak_count": 1,
    }
    # Options for first peak
    peak1 = {
        "force_peak": True,
        "peak_min": 160,
        "peak_max": 170,
        "use_roi_bck": True,
        "force_background": True,
        "bck_min": 5,
        "bck_max": 100,
        "use_side_bck": True,
        "bck_width": 10,
    }
    # Options for second peak
    peak2 = {
        "force_peak_s2": False,
        "peak_min_s2": 170,
        "peak_max_s2": 180,
        "use_roi_bck_s2": False,
        "force_background_s2": False,
        "bck_min_s2": 6,
        "bck_max_s2": 101,
        "use_side_bck_s2": False,
        "bck_width_s2": 11,
    }
    # Options for third peak
    peak3 = {
        "force_peak_s3": True,
        "peak_min_s3": 180,
        "peak_max_s3": 190,
        "use_roi_bck_s3": False,
        "force_background_s3": True,
        "bck_min_s3": 7,
        "bck_max_s3": 102,
        "use_side_bck_s3": False,
        "bck_width_s3": 12,
    }
    values = {**common, **peak1, **peak2, **peak3}
    # inject values in the reduction template
    with open(data_server.path_to_template, "r") as file_handle:
        template = string.Template(file_handle.read())
        script = template.substitute(**values)
    open(os.path.join(tempdir, "reduce_REF_M.py"), "w").write(script)
    # verify the values have been injected into the autoreduction script
    with add_to_sys_path(tempdir):
        from reduce_REF_M import reduction_user_options

        opts = reduction_user_options()
        # assert common options
        assert opts.peak_count == common["peak_count"]
        for a, b in [  # template and reduction keys don't have the same name
            ("plot_2d", "plot_in_2D"),
            ("const_q_binning", "use_const_q"),
            ("q_step", "q_step"),
            ("use_sangle", "use_sangle"),
            ("update_peak_range", "fit_peak_in_roi"),
        ]:
            assert opts.common[a] == common[b]
        # assert peak1 options
        for a, b in [
            ("force_peak_roi", "force_peak"),
            ("force_bck_roi", "force_background"),
            ("use_tight_bck", "use_side_bck"),
            ("bck_offset", "bck_width"),
        ]:
            assert opts.peak1[a] == peak1[b]
        assert opts.peak1["peak_roi"] == [peak1["peak_min"], peak1["peak_max"]]
        assert opts.peak1["bck_roi"] == [peak1["bck_min"], peak1["bck_max"]]
        # assert peak2 options
        for a, b in [
            ("force_peak_roi", "force_peak_s2"),
            ("force_bck_roi", "force_background_s2"),
            ("use_tight_bck", "use_side_bck_s2"),
            ("bck_offset", "bck_width_s2"),
        ]:
            assert opts.peak2[a] == peak2[b]
        assert opts.peak2["peak_roi"] == [peak2["peak_min_s2"], peak2["peak_max_s2"]]
        assert opts.peak2["bck_roi"] == [peak2["bck_min_s2"], peak2["bck_max_s2"]]
        # assert peak3 options
        for a, b in [
            ("force_peak_roi", "force_peak_s3"),
            ("force_bck_roi", "force_background_s3"),
            ("use_tight_bck", "use_side_bck_s3"),
            ("bck_offset", "bck_width_s3"),
        ]:
            assert opts.peak3[a] == peak3[b]
        assert opts.peak3["peak_roi"] == [peak3["peak_min_s3"], peak3["peak_max_s3"]]
        assert opts.peak3["bck_roi"] == [peak3["bck_min_s3"], peak3["bck_max_s3"]]


if __name__ == "__main__":
    pytest.main([__file__])
