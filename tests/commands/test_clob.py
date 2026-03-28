import sys
import types

import pandas as pd

from cwmscli.commands import commands_cwms
from cwmscli.commands.clob import download_cmd, list_cmd


def test_blob_and_clob_upload_keep_no_overwrite_flag():
    blob_overwrite = next(
        param
        for param in commands_cwms.blob_upload.params
        if getattr(param, "name", None) == "overwrite"
    )
    clob_overwrite = next(
        param
        for param in commands_cwms.clob_upload.params
        if getattr(param, "name", None) == "overwrite"
    )

    assert "--overwrite" in blob_overwrite.opts
    assert "--no-overwrite" in blob_overwrite.secondary_opts
    assert "--overwrite" in clob_overwrite.opts
    assert "--no-overwrite" in clob_overwrite.secondary_opts


def test_download_cmd_uses_default_dest_and_writes_text(tmp_path, monkeypatch):
    calls = []

    class FakeClobResponse:
        json = {"value": "retrieved clob text"}

    class FakeCwms:
        @staticmethod
        def init_session(api_root, api_key):
            calls.append(("init_session", api_root, api_key))
            return None

        @staticmethod
        def get_clob(office_id, clob_id):
            calls.append(("get_clob", office_id, clob_id))
            return FakeClobResponse()

    monkeypatch.setitem(sys.modules, "cwms", FakeCwms)
    monkeypatch.setattr("cwmscli.commands.clob.cwms", FakeCwms)

    class FakeHTTPError(Exception):
        pass

    monkeypatch.setitem(
        sys.modules, "requests", types.SimpleNamespace(HTTPError=FakeHTTPError)
    )
    monkeypatch.setattr(
        "cwmscli.commands.clob.requests",
        types.SimpleNamespace(HTTPError=FakeHTTPError),
    )

    monkeypatch.chdir(tmp_path)

    download_cmd(
        clob_id="test_clob",
        dest=None,
        office="SWT",
        api_root="https://example.test/",
        api_key="apikey 123",
        dry_run=False,
    )

    saved = tmp_path / "TEST_CLOB"
    assert saved.exists()
    assert saved.read_text(encoding="utf-8") == "retrieved clob text"
    assert calls == [
        ("init_session", "https://example.test/", "apikey 123"),
        ("get_clob", "SWT", "TEST_CLOB"),
    ]


def test_download_cmd_anonymous_skips_api_key(tmp_path, monkeypatch):
    calls = []

    class FakeClobResponse:
        json = {"value": "retrieved clob text"}

    class FakeCwms:
        @staticmethod
        def init_session(api_root, api_key):
            calls.append(("init_session", api_root, api_key))
            return None

        @staticmethod
        def get_clob(office_id, clob_id):
            return FakeClobResponse()

    monkeypatch.setitem(sys.modules, "cwms", FakeCwms)
    monkeypatch.setattr("cwmscli.commands.clob.cwms", FakeCwms)

    class FakeHTTPError(Exception):
        pass

    monkeypatch.setitem(
        sys.modules, "requests", types.SimpleNamespace(HTTPError=FakeHTTPError)
    )
    monkeypatch.setattr(
        "cwmscli.commands.clob.requests",
        types.SimpleNamespace(HTTPError=FakeHTTPError),
    )

    download_cmd(
        clob_id="test_clob",
        dest=str(tmp_path / "downloaded.txt"),
        office="SWT",
        api_root="https://example.test/",
        api_key="apikey 123",
        dry_run=False,
        anonymous=True,
    )

    assert calls == [("init_session", "https://example.test/", None)]


def test_list_cmd_initializes_session_with_api_key(monkeypatch):
    calls = []

    class FakeCwms:
        @staticmethod
        def init_session(api_root, api_key):
            calls.append(("init_session", api_root, api_key))
            return None

        @staticmethod
        def get_clobs(office_id, clob_id_like):
            return pd.DataFrame([{"id": "TEST_CLOB", "description": "x"}])

    monkeypatch.setitem(sys.modules, "cwms", FakeCwms)
    monkeypatch.setattr("cwmscli.commands.clob.cwms", FakeCwms)

    list_cmd(
        clob_id_like="TEST_.*",
        columns=[],
        sort_by=[],
        desc=False,
        limit=None,
        to_csv=None,
        office="SWT",
        api_root="https://example.test/",
        api_key="apikey 123",
    )

    assert calls == [("init_session", "https://example.test/", "apikey 123")]


def test_list_cmd_anonymous_skips_api_key(monkeypatch):
    calls = []

    class FakeCwms:
        @staticmethod
        def init_session(api_root, api_key):
            calls.append(("init_session", api_root, api_key))
            return None

        @staticmethod
        def get_clobs(office_id, clob_id_like):
            return pd.DataFrame([{"id": "TEST_CLOB", "description": "x"}])

    monkeypatch.setitem(sys.modules, "cwms", FakeCwms)
    monkeypatch.setattr("cwmscli.commands.clob.cwms", FakeCwms)

    list_cmd(
        clob_id_like="TEST_.*",
        columns=[],
        sort_by=[],
        desc=False,
        limit=None,
        to_csv=None,
        office="SWT",
        api_root="https://example.test/",
        api_key="apikey 123",
        anonymous=True,
    )

    assert calls == [("init_session", "https://example.test/", None)]
