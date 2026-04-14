import pytest

from cwmscli.commands.blob import _default_download_dest as blob_default_download_dest
from cwmscli.commands.clob import _default_download_dest as clob_default_download_dest

SAFE_CASES = [
    ("REPORTS/REL-BLB", "REPORTS/REL-BLB"),
    ("REPORTS\\REL-BLB", "REPORTS\\REL-BLB"),
    ("/REPORTS/REL-BLB", "REPORTS/REL-BLB"),
    ("\\REPORTS\\REL-BLB", "REPORTS\\REL-BLB"),
]


UNSAFE_CASES = [
    "",
    "/",
    "\\",
    "../REPORTS/REL-BLB",
    "..\\REPORTS\\REL-BLB",
    "./REPORTS/REL-BLB",
    ".\\REPORTS\\REL-BLB",
    "REPORTS/../REL-BLB",
    "REPORTS\\..\\REL-BLB",
    "REPORTS/./REL-BLB",
    "REPORTS\\.\\REL-BLB",
    "C:/REPORTS/REL-BLB",
    "C:\\REPORTS\\REL-BLB",
    "//server/share/file",
    "\\\\server\\share\\file",
]


@pytest.mark.parametrize("blob_id,expected", SAFE_CASES)
def test_blob_default_download_dest_allows_safe_relative_paths(blob_id, expected):
    assert blob_default_download_dest(blob_id) == expected


@pytest.mark.parametrize("clob_id,expected", SAFE_CASES)
def test_clob_default_download_dest_allows_safe_relative_paths(clob_id, expected):
    assert clob_default_download_dest(clob_id) == expected


@pytest.mark.parametrize("blob_id", UNSAFE_CASES)
def test_blob_default_download_dest_rejects_unsafe_paths(blob_id):
    with pytest.raises(ValueError):
        blob_default_download_dest(blob_id)


@pytest.mark.parametrize("clob_id", UNSAFE_CASES)
def test_clob_default_download_dest_rejects_unsafe_paths(clob_id):
    with pytest.raises(ValueError):
        clob_default_download_dest(clob_id)
