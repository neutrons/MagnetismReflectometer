import os
import re
from pathlib import Path

import pytest
from mantid.simpleapi import LoadEventNexus, mtd

from mr_reduction.mr_reduction import ReductionProcess
from mr_reduction.runpeak import RunPeakNumber
from mr_reduction.script_output import generate_script_from_ws


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


@pytest.mark.datarepo
def test_generate_script_from_ws(data_server, tmp_path, mock_filesystem):
    """Test generation of reduction script from workspace group."""
    # Load data run
    workspace = LoadEventNexus(Filename=data_server.path_to("REF_M_44382.nxs.h5"), OutputWorkspace="ws_44382")

    # Reduce data run
    output_dir = tmp_path / "output"
    mock_filesystem.DirectBeamFinder.return_value.search.return_value = 44380
    ReductionProcess(data_run="44382", data_ws=workspace, output_dir=output_dir).reduce()

    # Generate script from reflectivity workspace
    runpeak = RunPeakNumber("44382", None)
    ws_refl = mtd["r_%s" % runpeak]
    script = generate_script_from_ws(ws_refl, group_name=str(ws_refl))

    generated = _normalize_paths(script)

    with open(data_server.path_to(f"REF_M_{runpeak}_partial.py")) as fd:
        expected_text = fd.read()
        expected = _normalize_paths(expected_text)

    # Verify script content
    assert generated == expected
