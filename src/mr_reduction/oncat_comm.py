"""
    ONCat reduced file ingestion.
"""
import pyoncat

def ingest(file_path):
    # Use PyONCat v1.3.1 or above.
    assert tuple(map(int, pyoncat.__version__.split("."))) >= (1, 3, 1)

    # Use the testing instance of ONCat.
    ONCAT_URL = "https://oncat-testing.ornl.gov"

    # These credentials can be used for manual testing.  The autoreducer VM's have
    # their own client credentials which should be used.
    CLIENT_ID = "b883cec7-d977-4015-8ecd-e6c3d9a33582"
    CLIENT_SECRET = "2977f72c-2b92-4540-a482-126b72eabb62"
    SCOPES = ["api:read", "api:write:location"]

    oncat = pyoncat.ONCat(
        ONCAT_URL,
        client_id = CLIENT_ID,
        client_secret = CLIENT_SECRET,
        flow = pyoncat.CLIENT_CREDENTIALS_FLOW,
        scopes = SCOPES,
    )
    oncat.Reduction.create({"location": file_path})
