import pytest
from mantid.simpleapi import LoadEventNexus, mtd
from numpy.testing import assert_allclose

from mr_reduction.mr_reduction import ReductionProcess
from mr_reduction.runpeak import RunPeakNumber
from mr_reduction.script_output import generate_script_from_ws


@pytest.mark.datarepo
def test_generate_script_from_ws(data_server, tmp_path, mock_filesystem):
    """Test generation of reduction script from reflectivity workspace.

    Steps taken in this test:
    1. Reduces a data run.
    2. Generates a script from the resulting reflectivity workspace.
    3. Executes the generated script.
    4. Verifies that the reflectivity data matches.

    Note that the reflectivity data does not match exactly. One source of
    discrepancy is that the reduction parameters are written with limited
    precision in the generated Python script.
    """
    # Load data run
    workspace = LoadEventNexus(Filename=data_server.path_to("REF_M_44382.nxs.h5"), OutputWorkspace="ws_44382")
    peak_number = 1

    # Reduce data run
    output_dir = tmp_path / "output"
    mock_filesystem.DirectBeamFinder.return_value.search.return_value = 44380
    ReductionProcess(data_run="44382", data_ws=workspace, output_dir=output_dir, peak_number=peak_number).reduce()

    # Generate Python script from reflectivity workspace
    runpeak = RunPeakNumber("44382", peak_number)
    ws_refl_xs = mtd[f"r_{runpeak}"][0]
    x_expected, y_expected, dy_expected, dx_expected = (
        ws_refl_xs.readX(0),
        ws_refl_xs.readY(0),
        ws_refl_xs.readE(0),
        ws_refl_xs.readDx(0),
    )

    script = generate_script_from_ws(
        [ws_refl_xs], group_name=str(ws_refl_xs), quicknxs_mode=False, include_workspace_string=False
    )

    # Execute the generated script to be able to compare results
    globals_ = {}
    exec(script, globals_)

    # The reflectivity workspace has been replaced in MDS
    ws_refl = mtd[f"r_{runpeak}"]
    ws_refl_xs = ws_refl[0]
    x_actual, y_actual, dy_actual, dx_actual = (
        ws_refl_xs.readX(0),
        ws_refl_xs.readY(0),
        ws_refl_xs.readE(0),
        ws_refl_xs.readDx(0),
    )

    # Verify that the reflectivity data matches
    assert_allclose(x_expected, x_actual, rtol=1e-5)
    assert_allclose(y_expected, y_actual, rtol=0.01)
    assert_allclose(dy_expected, dy_actual, rtol=0.01)
    assert_allclose(dx_expected, dx_actual, rtol=1e-5)
