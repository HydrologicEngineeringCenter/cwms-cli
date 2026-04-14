import sys
import types

import pandas as pd
import pytest

from cwmscli.commands.blob import (
    _blob_id_for_path,
    _default_download_dest,
    _find_blob_id_collisions,
    _list_matching_files,
    _save_blob_content,
    download_cmd,
    list_cmd,
    upload_cmd,
)


def test_list_matching_files_filters_by_regex(tmp_path):
    (tmp_path / "one.txt").write_text("1")
    (tmp_path / "two.bin").write_text("2")
    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "three.txt").write_text("3")

    matches = _list_matching_files(str(tmp_path), r".*\.txt$", recursive=True)
    rel_paths = [rel for _, rel in matches]
    assert rel_paths == ["one.txt", "subdir/three.txt"]


def test_blob_id_for_path_uses_prefix_and_relative_path():
    blob_id = _blob_id_for_path(
        input_dir="/tmp/in",
        rel_path="reports/jan/final.pdf",
        blob_id_prefix="OPS_",
    )
    assert blob_id == "OPS_REPORTS_JAN_FINAL"


def test_upload_cmd_continues_on_error_for_directory(tmp_path, monkeypatch):
    file_a = tmp_path / "a.txt"
    file_b = tmp_path / "b.txt"
    file_a.write_text("a")
    file_b.write_text("b")

    calls = []

    class FakeCwms:
        @staticmethod
        def init_session(api_root, api_key):
            return None

        @staticmethod
        def store_blobs(blob, fail_if_exists):
            calls.append(blob["id"])
            if blob["id"] == "B":
                raise RuntimeError("simulated failure")

    monkeypatch.setitem(sys.modules, "cwms", FakeCwms)

    class FakeHTTPError(Exception):
        pass

    monkeypatch.setitem(
        sys.modules, "requests", types.SimpleNamespace(HTTPError=FakeHTTPError)
    )

    with pytest.raises(SystemExit) as exc:
        upload_cmd(
            input_file=None,
            input_dir=str(tmp_path),
            file_regex=r".*\.txt$",
            recursive=False,
            blob_id=None,
            blob_id_prefix="",
            description=None,
            media_type=None,
            overwrite=False,
            dry_run=False,
            office="SWT",
            api_root="https://example.test/",
            api_key="x",
        )

    assert exc.value.code == 1
    assert calls == ["A", "B"]


def test_find_blob_id_collisions_detects_same_stem_and_path_collisions():
    matches = [
        ("C:/tmp/a.txt", "a.txt"),
        ("C:/tmp/a.json", "a.json"),
        ("C:/tmp/dir/a.txt", "dir/a.txt"),
        ("C:/tmp/dir_a.txt", "dir_a.txt"),
    ]

    collisions = _find_blob_id_collisions(
        matches, input_dir="C:/tmp", blob_id_prefix=""
    )

    assert collisions == {
        "A": ["a.txt", "a.json"],
        "DIR_A": ["dir/a.txt", "dir_a.txt"],
    }


def test_upload_cmd_aborts_before_upload_when_generated_ids_collide(
    tmp_path, monkeypatch
):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "a.json").write_text("{}")

    calls = []

    class FakeCwms:
        @staticmethod
        def init_session(api_root, api_key):
            calls.append(("init_session", api_root, api_key))
            return None

        @staticmethod
        def store_blobs(blob, fail_if_exists):
            calls.append(("store_blobs", blob["id"]))

    monkeypatch.setitem(sys.modules, "cwms", FakeCwms)

    class FakeHTTPError(Exception):
        pass

    monkeypatch.setitem(
        sys.modules, "requests", types.SimpleNamespace(HTTPError=FakeHTTPError)
    )

    with pytest.raises(SystemExit) as exc:
        upload_cmd(
            input_file=None,
            input_dir=str(tmp_path),
            file_regex=r".*",
            recursive=False,
            blob_id=None,
            blob_id_prefix="",
            description=None,
            media_type=None,
            overwrite=False,
            dry_run=False,
            office="SWT",
            api_root="https://example.test/",
            api_key="x",
        )

    assert exc.value.code == 2
    assert calls == [("init_session", "https://example.test/", "x")]


def test_save_blob_content_writes_raw_text(tmp_path):
    dest = tmp_path / "blob.txt"

    written = _save_blob_content("plain text payload", str(dest), "text/plain")

    assert written == str(dest)
    assert dest.read_text(encoding="utf-8") == "plain text payload"


def test_default_download_dest_strips_leading_path_separators():
    assert _default_download_dest("/REPORTS/REL-BLB") == "REPORTS/REL-BLB"
    assert _default_download_dest("\\REPORTS\\REL-BLB") == "REPORTS\\REL-BLB"


def test_download_cmd_uses_media_type_to_write_text(tmp_path, monkeypatch):
    dest = tmp_path / "downloaded"

    class FakeBlobListing:
        df = pd.DataFrame(
            [{"id": "TEST_TXT", "media-type-id": "text/plain", "description": "x"}]
        )

    class FakeCwms:
        @staticmethod
        def init_session(api_root, api_key=None):
            return None

        @staticmethod
        def get_blob(office_id, blob_id):
            assert office_id == "SWT"
            assert blob_id == "TEST_TXT"
            return "retrieved text"

        @staticmethod
        def get_blobs(office_id, blob_id_like):
            assert office_id == "SWT"
            assert blob_id_like == "TEST_TXT"
            return FakeBlobListing()

    monkeypatch.setitem(sys.modules, "cwms", FakeCwms)

    class FakeHTTPError(Exception):
        pass

    monkeypatch.setitem(
        sys.modules, "requests", types.SimpleNamespace(HTTPError=FakeHTTPError)
    )

    download_cmd(
        blob_id="test_txt",
        dest=str(dest),
        office="SWT",
        api_root="https://example.test/",
        api_key="x",
        dry_run=False,
    )

    saved = tmp_path / "downloaded.txt"
    assert saved.exists()
    assert saved.read_text(encoding="utf-8") == "retrieved text"


def test_download_cmd_default_dest_stays_relative_for_leading_slash_id(
    tmp_path, monkeypatch
):
    class FakeBlobListing:
        df = pd.DataFrame(
            [
                {
                    "id": "/REPORTS/REL-BLB",
                    "media-type-id": "text/plain",
                    "description": "x",
                }
            ]
        )

    class FakeCwms:
        @staticmethod
        def init_session(api_root, api_key=None):
            return None

        @staticmethod
        def get_blob(office_id, blob_id):
            assert blob_id == "/REPORTS/REL-BLB"
            return "retrieved text"

        @staticmethod
        def get_blobs(office_id, blob_id_like):
            assert blob_id_like == "/REPORTS/REL-BLB"
            return FakeBlobListing()

    monkeypatch.setitem(sys.modules, "cwms", FakeCwms)

    class FakeHTTPError(Exception):
        pass

    monkeypatch.setitem(
        sys.modules, "requests", types.SimpleNamespace(HTTPError=FakeHTTPError)
    )

    monkeypatch.chdir(tmp_path)

    download_cmd(
        blob_id="/reports/rel-blb",
        dest=None,
        office="SWT",
        api_root="https://example.test/",
        api_key="x",
        dry_run=False,
    )

    saved = tmp_path / "REPORTS" / "REL-BLB.txt"
    assert saved.exists()
    assert saved.read_text(encoding="utf-8") == "retrieved text"


def test_download_cmd_initializes_session_with_api_key(tmp_path, monkeypatch):
    dest = tmp_path / "downloaded"
    calls = []

    class FakeBlobListing:
        df = pd.DataFrame(
            [{"id": "TEST_TXT", "media-type-id": "text/plain", "description": "x"}]
        )

    class FakeCwms:
        @staticmethod
        def init_session(api_root, api_key):
            calls.append(("init_session", api_root, api_key))
            return None

        @staticmethod
        def get_blob(office_id, blob_id):
            return "retrieved text"

        @staticmethod
        def get_blobs(office_id, blob_id_like):
            return FakeBlobListing()

    monkeypatch.setitem(sys.modules, "cwms", FakeCwms)

    class FakeHTTPError(Exception):
        pass

    monkeypatch.setitem(
        sys.modules, "requests", types.SimpleNamespace(HTTPError=FakeHTTPError)
    )

    download_cmd(
        blob_id="test_txt",
        dest=str(dest),
        office="SWT",
        api_root="https://example.test/",
        api_key="apikey 123",
        dry_run=False,
    )

    assert calls == [("init_session", "https://example.test/", "apikey 123")]


def test_list_cmd_initializes_session_with_api_key(monkeypatch):
    calls = []

    class FakeCwms:
        @staticmethod
        def init_session(api_root, api_key):
            calls.append(("init_session", api_root, api_key))
            return None

        @staticmethod
        def get_blobs(office_id, blob_id_like, page_size=None):
            calls.append(("get_blobs", office_id, blob_id_like, page_size))
            return pd.DataFrame(
                [{"id": "TEST_TXT", "media-type-id": "text/plain", "description": "x"}]
            )

    monkeypatch.setitem(sys.modules, "cwms", FakeCwms)

    list_cmd(
        blob_id_like="TEST_.*",
        columns=[],
        sort_by=[],
        desc=False,
        limit=None,
        page_size=None,
        to_csv=None,
        office="SWT",
        api_root="https://example.test/",
        api_key="apikey 123",
    )

    assert calls == [
        ("init_session", "https://example.test/", "apikey 123"),
        ("get_blobs", "SWT", "TEST_.*", None),
    ]


def test_list_cmd_uses_limit_as_fetch_page_size(monkeypatch):
    calls = []

    class FakeCwms:
        @staticmethod
        def init_session(api_root, api_key):
            return None

        @staticmethod
        def get_blobs(office_id, blob_id_like, page_size=None):
            calls.append((office_id, blob_id_like, page_size))
            return pd.DataFrame(
                [
                    {"id": "A", "media-type-id": "text/plain", "description": "x"},
                    {"id": "B", "media-type-id": "text/plain", "description": "y"},
                ]
            )

    monkeypatch.setitem(sys.modules, "cwms", FakeCwms)

    list_cmd(
        blob_id_like="TEST_.*",
        columns=[],
        sort_by=[],
        desc=False,
        limit=25,
        page_size=None,
        to_csv=None,
        office="SWT",
        api_root="https://example.test/",
        api_key="apikey 123",
    )

    assert calls == [("SWT", "TEST_.*", 25)]


def test_list_cmd_page_size_overrides_limit_for_fetch(monkeypatch):
    calls = []

    class FakeCwms:
        @staticmethod
        def init_session(api_root, api_key):
            return None

        @staticmethod
        def get_blobs(office_id, blob_id_like, page_size=None):
            calls.append((office_id, blob_id_like, page_size))
            return pd.DataFrame(
                [{"id": "A", "media-type-id": "text/plain", "description": "x"}]
            )

    monkeypatch.setitem(sys.modules, "cwms", FakeCwms)

    list_cmd(
        blob_id_like="TEST_.*",
        columns=[],
        sort_by=[],
        desc=False,
        limit=25,
        page_size=200,
        to_csv=None,
        office="SWT",
        api_root="https://example.test/",
        api_key="apikey 123",
    )

    assert calls == [("SWT", "TEST_.*", 200)]


def test_download_cmd_anonymous_skips_api_key(tmp_path, monkeypatch):
    dest = tmp_path / "downloaded"
    calls = []

    class FakeBlobListing:
        df = pd.DataFrame(
            [{"id": "TEST_TXT", "media-type-id": "text/plain", "description": "x"}]
        )

    class FakeCwms:
        @staticmethod
        def init_session(api_root, api_key):
            calls.append(("init_session", api_root, api_key))
            return None

        @staticmethod
        def get_blob(office_id, blob_id):
            return "retrieved text"

        @staticmethod
        def get_blobs(office_id, blob_id_like):
            return FakeBlobListing()

    monkeypatch.setitem(sys.modules, "cwms", FakeCwms)

    class FakeHTTPError(Exception):
        pass

    monkeypatch.setitem(
        sys.modules, "requests", types.SimpleNamespace(HTTPError=FakeHTTPError)
    )

    download_cmd(
        blob_id="test_txt",
        dest=str(dest),
        office="SWT",
        api_root="https://example.test/",
        api_key="apikey 123",
        dry_run=False,
        anonymous=True,
    )

    assert calls == [("init_session", "https://example.test/", None)]


def test_list_cmd_anonymous_skips_api_key(monkeypatch):
    calls = []

    class FakeCwms:
        @staticmethod
        def init_session(api_root, api_key):
            calls.append(("init_session", api_root, api_key))
            return None

        @staticmethod
        def get_blobs(office_id, blob_id_like, page_size=None):
            calls.append(("get_blobs", office_id, blob_id_like, page_size))
            return pd.DataFrame(
                [{"id": "TEST_TXT", "media-type-id": "text/plain", "description": "x"}]
            )

    monkeypatch.setitem(sys.modules, "cwms", FakeCwms)

    list_cmd(
        blob_id_like="TEST_.*",
        columns=[],
        sort_by=[],
        desc=False,
        limit=None,
        page_size=None,
        to_csv=None,
        office="SWT",
        api_root="https://example.test/",
        api_key="apikey 123",
        anonymous=True,
    )

    assert calls == [
        ("init_session", "https://example.test/", None),
        ("get_blobs", "SWT", "TEST_.*", None),
    ]
