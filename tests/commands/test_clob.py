import sys
import types

import pandas as pd

from cwmscli.commands import commands_cwms
from cwmscli.commands.clob import (
    _clob_endpoint_id,
    delete_cmd,
    download_cmd,
    list_cmd,
    update_cmd,
)


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


def test_clob_endpoint_id_uses_ignored_path_for_special_chars():
    assert _clob_endpoint_id("plain_id") == ("PLAIN_ID", None)
    assert _clob_endpoint_id("path/id") == ("ignored", "PATH/ID")


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


def test_download_cmd_uses_query_override_for_special_char_ids(tmp_path, monkeypatch):
    calls = []

    class FakeCwms:
        @staticmethod
        def init_session(api_root, api_key):
            calls.append(("init_session", api_root, api_key))
            return None

        @staticmethod
        def get_clob(office_id, clob_id, clob_id_query=None):
            calls.append(("get_clob", office_id, clob_id, clob_id_query))
            raise AssertionError("special-char path should use direct SESSION.get")

    class FakeResponse:
        text = "retrieved clob text"

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def raise_for_status(self):
            return None

    class FakeSession:
        @staticmethod
        def get(endpoint, params=None, headers=None):
            calls.append(("session.get", endpoint, params, headers))
            return FakeResponse()

    monkeypatch.setitem(sys.modules, "cwms", FakeCwms)
    monkeypatch.setattr("cwmscli.commands.clob.cwms", FakeCwms)
    monkeypatch.setattr("cwmscli.commands.clob.cwms_api.SESSION", FakeSession())

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
        clob_id="path/id",
        dest=str(tmp_path / "downloaded.txt"),
        office="SWT",
        api_root="https://example.test/",
        api_key="apikey 123",
        dry_run=False,
    )

    assert calls == [
        ("init_session", "https://example.test/", "apikey 123"),
        (
            "session.get",
            "clobs/ignored",
            {"office": "SWT", "clob-id": "PATH/ID"},
            {"Accept": "text/plain"},
        ),
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
        def get_clobs(office_id, clob_id_like, page_size=None):
            calls.append(("get_clobs", office_id, clob_id_like, page_size))
            return pd.DataFrame([{"id": "TEST_CLOB", "description": "x"}])

    monkeypatch.setitem(sys.modules, "cwms", FakeCwms)
    monkeypatch.setattr("cwmscli.commands.clob.cwms", FakeCwms)

    list_cmd(
        clob_id_like="TEST_.*",
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
        ("get_clobs", "SWT", "TEST_.*", None),
    ]


def test_list_cmd_uses_limit_as_fetch_page_size(monkeypatch):
    calls = []

    class FakeCwms:
        @staticmethod
        def init_session(api_root, api_key):
            return None

        @staticmethod
        def get_clobs(office_id, clob_id_like, page_size=None):
            calls.append((office_id, clob_id_like, page_size))
            return pd.DataFrame(
                [
                    {"id": "A", "description": "x"},
                    {"id": "B", "description": "y"},
                ]
            )

    monkeypatch.setitem(sys.modules, "cwms", FakeCwms)
    monkeypatch.setattr("cwmscli.commands.clob.cwms", FakeCwms)

    list_cmd(
        clob_id_like="TEST_.*",
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
        def get_clobs(office_id, clob_id_like, page_size=None):
            calls.append((office_id, clob_id_like, page_size))
            return pd.DataFrame([{"id": "A", "description": "x"}])

    monkeypatch.setitem(sys.modules, "cwms", FakeCwms)
    monkeypatch.setattr("cwmscli.commands.clob.cwms", FakeCwms)

    list_cmd(
        clob_id_like="TEST_.*",
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


def test_list_cmd_anonymous_skips_api_key(monkeypatch):
    calls = []

    class FakeCwms:
        @staticmethod
        def init_session(api_root, api_key):
            calls.append(("init_session", api_root, api_key))
            return None

        @staticmethod
        def get_clobs(office_id, clob_id_like, page_size=None):
            calls.append(("get_clobs", office_id, clob_id_like, page_size))
            return pd.DataFrame([{"id": "TEST_CLOB", "description": "x"}])

    monkeypatch.setitem(sys.modules, "cwms", FakeCwms)
    monkeypatch.setattr("cwmscli.commands.clob.cwms", FakeCwms)

    list_cmd(
        clob_id_like="TEST_.*",
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
        ("get_clobs", "SWT", "TEST_.*", None),
    ]


def test_delete_cmd_uses_query_override_for_special_char_ids(monkeypatch):
    calls = []

    class FakeCwms:
        @staticmethod
        def init_session(api_root, api_key):
            calls.append(("init_session", api_root, api_key))
            return None

        @staticmethod
        def delete_clob(office_id, clob_id):
            calls.append(("delete_clob", office_id, clob_id))

    class FakeApi:
        @staticmethod
        def delete(endpoint, params=None):
            calls.append(("api.delete", endpoint, params))

    monkeypatch.setitem(sys.modules, "cwms", FakeCwms)
    monkeypatch.setattr("cwmscli.commands.clob.cwms", FakeCwms)
    monkeypatch.setattr("cwmscli.commands.clob.cwms_api", FakeApi)

    delete_cmd(
        clob_id="path/id",
        office="SWT",
        api_root="https://example.test/",
        api_key="apikey 123",
        dry_run=False,
    )

    assert calls == [
        ("init_session", "https://example.test/", "apikey 123"),
        (
            "api.delete",
            "clobs/ignored",
            {"office": "SWT", "clob-id": "PATH/ID"},
        ),
    ]


def test_update_cmd_uses_query_override_for_special_char_ids(tmp_path, monkeypatch):
    calls = []
    file_path = tmp_path / "updated.txt"
    file_path.write_text("updated clob text", encoding="utf-8")

    class FakeCwms:
        @staticmethod
        def init_session(api_root, api_key):
            calls.append(("init_session", api_root, api_key))
            return None

        @staticmethod
        def update_clob(data, clob_id, ignore_nulls=True):
            calls.append(("update_clob", data, clob_id, ignore_nulls))

    class FakeApi:
        @staticmethod
        def patch(endpoint, data=None, params=None):
            calls.append(("api.patch", endpoint, data, params))

    monkeypatch.setitem(sys.modules, "cwms", FakeCwms)
    monkeypatch.setattr("cwmscli.commands.clob.cwms", FakeCwms)
    monkeypatch.setattr("cwmscli.commands.clob.cwms_api", FakeApi)

    update_cmd(
        input_file=str(file_path),
        clob_id="path/id",
        description="updated description",
        ignore_nulls=False,
        dry_run=False,
        office="SWT",
        api_root="https://example.test/",
        api_key="apikey 123",
    )

    assert calls == [
        ("init_session", "https://example.test/", "apikey 123"),
        (
            "api.patch",
            "clobs/ignored",
            {
                "office-id": "SWT",
                "id": "PATH/ID",
                "description": "updated description",
                "value": "updated clob text",
            },
            {"clob-id": "PATH/ID", "ignore-nulls": False},
        ),
    ]
