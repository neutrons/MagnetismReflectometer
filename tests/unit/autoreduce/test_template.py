# standard imports
import os
import string

# third party imports
import pytest

# mr_reduction imports
from mr_reduction.simple_utils import add_to_sys_path


def test_template(data_server, tempdir):
    r"""Substitute values in the templates as in done in the post-processing agent"""
    # Options for all samples in the run
    common = {
        "plot_in_2D": True,
        "use_const_q": True,
        "q_step": -0.02,
        "use_sangle": True,
        "fit_peak_in_roi": False,
        "sample_count": 1,
    }
    # Options for first sample
    sample1 = {
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
    # Options for second sample
    sample2 = {
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
    # Options for third sample
    sample3 = {
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
    values = {**common, **sample1, **sample2, **sample3}
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
        assert opts.sample_count == common["sample_count"]
        for a, b in [  # template and reduction keys don't have the same name
            ("plot_2d", "plot_in_2D"),
            ("const_q_binning", "use_const_q"),
            ("q_step", "q_step"),
            ("use_sangle", "use_sangle"),
            ("update_peak_range", "fit_peak_in_roi"),
        ]:
            assert opts.common[a] == common[b]
        # assert sample1 options
        for a, b in [
            ("force_peak_roi", "force_peak"),
            ("force_bck_roi", "force_background"),
            ("use_tight_bck", "use_side_bck"),
            ("bck_offset", "bck_width"),
        ]:
            assert opts.sample1[a] == sample1[b]
        assert opts.sample1["peak_roi"] == [sample1["peak_min"], sample1["peak_max"]]
        assert opts.sample1["bck_roi"] == [sample1["bck_min"], sample1["bck_max"]]
        # assert sample2 options
        for a, b in [
            ("force_peak_roi", "force_peak_s2"),
            ("force_bck_roi", "force_background_s2"),
            ("use_tight_bck", "use_side_bck_s2"),
            ("bck_offset", "bck_width_s2"),
        ]:
            assert opts.sample2[a] == sample2[b]
        assert opts.sample2["peak_roi"] == [sample2["peak_min_s2"], sample2["peak_max_s2"]]
        assert opts.sample2["bck_roi"] == [sample2["bck_min_s2"], sample2["bck_max_s2"]]
        # assert sample3 options
        for a, b in [
            ("force_peak_roi", "force_peak_s3"),
            ("force_bck_roi", "force_background_s3"),
            ("use_tight_bck", "use_side_bck_s3"),
            ("bck_offset", "bck_width_s3"),
        ]:
            assert opts.sample3[a] == sample3[b]
        assert opts.sample3["peak_roi"] == [sample3["peak_min_s3"], sample3["peak_max_s3"]]
        assert opts.sample3["bck_roi"] == [sample3["bck_min_s3"], sample3["bck_max_s3"]]


if __name__ == "__main__":
    pytest.main([__file__])
