import sys
import types

import pandas as pd
import pytest

from cwmscli.commands.blob import (
    _blob_id_for_path,
    _list_matching_files,
    _save_blob_content,
    download_cmd,
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


def test_save_blob_content_writes_raw_text(tmp_path):
    dest = tmp_path / "blob.txt"

    written = _save_blob_content("plain text payload", str(dest), "text/plain")

    assert written == str(dest)
    assert dest.read_text(encoding="utf-8") == "plain text payload"


def test_download_cmd_uses_media_type_to_write_text(tmp_path, monkeypatch):
    dest = tmp_path / "downloaded"

    class FakeBlobListing:
        df = pd.DataFrame(
            [{"id": "TEST_TXT", "media-type-id": "text/plain", "description": "x"}]
        )

    class FakeCwms:
        @staticmethod
        def init_session(api_root):
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
