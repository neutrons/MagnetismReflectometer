# third party packages
import pytest
from mantid.simpleapi import LoadEventNexus, mtd

# mr_reduction imports
from mr_reduction.mr_direct_beam_finder import DirectBeamFinder


@pytest.fixture(scope="module")
def ws(data_server):
    workspace = mtd.unique_hidden_name()
    LoadEventNexus(Filename=data_server.path_to("REF_M_29160.nxs.h5"), OutputWorkspace=workspace)
    return workspace


class TestDirectBeamFinder:
    @pytest.mark.datarepo()
    def test_reduce_with_dirst(self, ws, tempdir: str):
        """
        This will excercise a different path in looking for direct beams.
        """
        finder = DirectBeamFinder(scatt_ws=ws)
        finder.data_dir = tempdir
        finder.ar_dir = tempdir
        finder.db_dir = tempdir
        finder.search()

    @pytest.mark.datarepo()
    def test_search_dir_json_decode_error(self, tmpdir, ws):
        # Create a temporary directory containing a malformed JSON file
        db_dir = tmpdir.mkdir("test_search_dir_json_decode_error")
        malformed_json_file = db_dir.join("REF_M_43827.nxs.h5.json")
        malformed_json_file.write('{"data_type": 0, "theta_d": 0.274}ngle": 4.917}')
        # Call the search_dir method and assert that it raises a ValueError
        finder = DirectBeamFinder(scatt_ws=ws)
        with pytest.raises(ValueError, match=f"Could not read {malformed_json_file}"):
            finder.search_dir(str(db_dir))


if __name__ == "__main__":
    pytest.main([__file__])
