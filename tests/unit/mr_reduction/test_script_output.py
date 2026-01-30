import re
import shutil
from pathlib import Path

import pytest
from mantid.simpleapi import LoadEventNexus, mtd

from mr_reduction.mr_reduction import ReductionProcess
from mr_reduction.runpeak import RunPeakNumber
from mr_reduction.script_output import generate_script_from_ws, write_reduction_script


def _normalize_paths(text: str, placeholder: str = "<FILE_PATH>") -> str:
    """Replace file paths with a placeholder for comparison purposes."""

    def repl(match: re.Match) -> str:
        path = match.group("path")
        filename = Path(path).name
        return f"Filename='{placeholder}/{filename}'"

    return re.sub(
        r"Filename\s*=\s*'(?P<path>[^']+)'",
        repl,
        text,
    )


def _remove_comments(text: str) -> str:
    """Remove comments from the script text for comparison purposes."""
    return re.sub(r"#.*", "", text)


@pytest.mark.datarepo
def test_generate_script_from_ws(data_server, tmp_path, mock_filesystem):
    """Test generation of reduction script from workspace group."""
    # Load data run
    workspace = LoadEventNexus(Filename=data_server.path_to("REF_M_44382.nxs.h5"), OutputWorkspace="ws_44382")
    peak_number = 1

    # Reduce data run
    output_dir = tmp_path / "output"
    mock_filesystem.DirectBeamFinder.return_value.search.return_value = 44380
    ReductionProcess(data_run="44382", data_ws=workspace, output_dir=output_dir, peak_number=peak_number).reduce()

    # Generate script from reflectivity workspace
    runpeak = RunPeakNumber("44382", peak_number)
    ws_refl = mtd[f"r_{runpeak}"]
    script = generate_script_from_ws(ws_refl, group_name=str(ws_refl))

    generated = _normalize_paths(script)

    with open(data_server.path_to(f"REF_M_{runpeak}_partial.py")) as fd:
        expected_text = fd.read()
        expected = _normalize_paths(expected_text)

    # Verify script content
    assert generated == expected


@pytest.mark.datarepo
def test_write_reduction_script(data_server, tmp_path):
    """Test writing of combined reduction script."""
    # Copy partial scripts to temporary autoreduce directory
    ar_dir = tmp_path / "autoreduce"
    ar_dir.mkdir(parents=True, exist_ok=True)
    runpeaks = [RunPeakNumber("42535", 1), RunPeakNumber("42536", 1), RunPeakNumber("42537", 1)]
    for runpeak in runpeaks:
        partial_file_path = data_server.path_to(f"REF_M_{runpeak}_partial.py")
        shutil.copy(partial_file_path, ar_dir)

    # Write combined script from partial scripts
    scaling_factors = [1.0, 0.95, 0.8]
    script_filepath = write_reduction_script(runpeaks, scaling_factors, str(ar_dir))

    with open(script_filepath) as fd:
        actual = _normalize_paths(fd.read())
        actual = _remove_comments(actual)

    with open(data_server.path_to("REF_M_42535_1_combined.py")) as fd:
        expected = _normalize_paths(fd.read())
        expected = _remove_comments(expected)

    # Verify script content
    assert actual == expected
