import importlib.metadata

import pytest
from click.testing import CliRunner

from cwmscli.__main__ import cli


@pytest.fixture(autouse=True)
def mock_cwms_python_version(monkeypatch):
    monkeypatch.setattr(importlib.metadata, "version", lambda pkg: "1.0.7")


class _FakeData:
    def __init__(self, payload):
        self.json = payload

    def get(self, key, default=None):
        return self.json.get(key, default)


def test_users_roles_lists_available_roles(monkeypatch):
    monkeypatch.setattr(
        "cwmscli.utils.get_api_key", lambda api_key, api_key_loc: "test-key"
    )

    class _FakeCwms:
        class api:
            class ApiError(Exception):
                pass

        @staticmethod
        def init_session(api_root, api_key):
            return None

        @staticmethod
        def get_roles():
            return ["Viewer", "CWMS User Admins", "Analyst"]

    monkeypatch.setitem(__import__("sys").modules, "cwms", _FakeCwms)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "users",
            "roles",
            "list-all",
            "--api-root",
            "https://example.test/cda/",
            "--api-key",
            "ignored",
            "--api-key-loc",
            "header",
        ],
    )

    assert result.exit_code == 0
    output = result.output
    assert "Available roles for user management: 3" in output
    assert "CWMS User Admins" in output
    assert "Analyst" in output
    assert "Viewer" in output


def test_users_roles_surfaces_handled_api_errors_without_traceback(monkeypatch):
    monkeypatch.setattr(
        "cwmscli.utils.get_api_key", lambda api_key, api_key_loc: "test-key"
    )

    class _FakeApiError(Exception):
        pass

    class _FakePermissionError(_FakeApiError):
        pass

    class _FakeApi:
        ApiError = _FakeApiError
        PermissionError = _FakePermissionError

    class _FakeCwms:
        api = _FakeApi

        @staticmethod
        def init_session(api_root, api_key):
            return None

        @staticmethod
        def get_roles():
            raise _FakePermissionError(
                "User role lookup could not be completed because the current credentials "
                "are not authorized for user-management access or are missing the "
                "required role assignment. CDA responded with 403 Forbidden."
            )

    monkeypatch.setitem(__import__("sys").modules, "cwms", _FakeCwms)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "users",
            "roles",
            "list-all",
            "--api-root",
            "https://example.test/cda/",
            "--api-key",
            "ignored",
            "--api-key-loc",
            "header",
        ],
    )

    assert result.exit_code == 1
    assert "User role lookup could not be completed" in result.output
    assert "CDA responded with 403 Forbidden." in result.output
    assert "Use an admin API key or sign in as a user" in result.output
    assert "Traceback" not in result.output


def test_users_roles_add_shortcut_roles_expand(monkeypatch):
    monkeypatch.setattr(
        "cwmscli.utils.get_api_key", lambda api_key, api_key_loc: "test-key"
    )

    calls = {"store_user": []}

    class _FakeCwms:
        class api:
            class ApiError(Exception):
                pass

            class PermissionError(ApiError):
                pass

        @staticmethod
        def init_session(api_root, api_key):
            return None

        @staticmethod
        def get_users(office_id=None, username_like=None, page_size=None):
            return _FakeData({"users": [{"user-name": "q0hectest"}], "next-page": None})

        @staticmethod
        def get_roles():
            return ["All Users", "CWMS Users", "TS ID Creator", "CWMS User Admins"]

        @staticmethod
        def store_user(user_name, office_id, roles):
            calls["store_user"].append((user_name, office_id, roles))

    monkeypatch.setitem(__import__("sys").modules, "cwms", _FakeCwms)

    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "users",
            "roles",
            "add",
            "--office",
            "SPK",
            "--api-root",
            "https://example.test/cda/",
            "--api-key",
            "ignored",
            "--api-key-loc",
            "header",
            "--user-name",
            "q0hectest",
            "--roles",
            "readonly",
        ],
    )
    assert result.exit_code == 0
    assert calls["store_user"][0] == (
        "q0hectest",
        "SPK",
        ["All Users", "CWMS Users"],
    )

    result = runner.invoke(
        cli,
        [
            "users",
            "roles",
            "add",
            "--office",
            "SPK",
            "--api-root",
            "https://example.test/cda/",
            "--api-key",
            "ignored",
            "--api-key-loc",
            "header",
            "--user-name",
            "q0hectest",
            "--roles",
            "readwrite",
        ],
    )
    assert result.exit_code == 0
    assert calls["store_user"][1] == (
        "q0hectest",
        "SPK",
        ["All Users", "CWMS Users", "TS ID Creator"],
    )

    result = runner.invoke(
        cli,
        [
            "users",
            "roles",
            "add",
            "--office",
            "SPK",
            "--api-root",
            "https://example.test/cda/",
            "--api-key",
            "ignored",
            "--user-name",
            "q0hectest",
            "--roles",
            "admin",
        ],
    )
    assert result.exit_code == 0
    assert calls["store_user"][2] == (
        "q0hectest",
        "SPK",
        ["All Users", "CWMS Users", "TS ID Creator", "CWMS User Admins"],
    )

    result = runner.invoke(
        cli,
        [
            "users",
            "roles",
            "add",
            "--office",
            "SPK",
            "--api-root",
            "https://example.test/cda/",
            "--api-key",
            "ignored",
            "--user-name",
            "q0hectest",
            "--roles",
            "readonly|TS ID Creator",
        ],
    )
    assert result.exit_code == 0
    assert calls["store_user"][3] == (
        "q0hectest",
        "SPK",
        ["All Users", "CWMS Users", "TS ID Creator"],
    )


def test_users_roles_delete_shortcut_roles_expand(monkeypatch):
    monkeypatch.setattr(
        "cwmscli.utils.get_api_key", lambda api_key, api_key_loc: "test-key"
    )

    calls = {"delete_user_roles": []}

    class _FakeCwms:
        class api:
            class ApiError(Exception):
                pass

            class PermissionError(ApiError):
                pass

        @staticmethod
        def init_session(api_root, api_key):
            return None

        @staticmethod
        def get_users(office_id=None, username_like=None, page_size=None):
            return _FakeData({"users": [{"user-name": "q0hectest"}], "next-page": None})

        @staticmethod
        def get_roles():
            return ["All Users", "CWMS Users", "TS ID Creator", "CWMS User Admins"]

        @staticmethod
        def delete_user_roles(user_name, office_id, roles):
            calls["delete_user_roles"].append((user_name, office_id, roles))

    monkeypatch.setitem(__import__("sys").modules, "cwms", _FakeCwms)

    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "users",
            "roles",
            "delete",
            "--office",
            "SPK",
            "--api-root",
            "https://example.test/cda/",
            "--api-key",
            "ignored",
            "--user-name",
            "q0hectest",
            "--roles",
            "readonly",
        ],
    )
    assert result.exit_code == 0
    assert calls["delete_user_roles"][0] == (
        "q0hectest",
        "SPK",
        ["CWMS Users"],
    )

    result = runner.invoke(
        cli,
        [
            "users",
            "roles",
            "delete",
            "--office",
            "SPK",
            "--api-root",
            "https://example.test/cda/",
            "--api-key",
            "ignored",
            "--user-name",
            "q0hectest",
            "--roles",
            "admin",
        ],
    )
    assert result.exit_code == 0
    assert calls["delete_user_roles"][1] == (
        "q0hectest",
        "SPK",
        ["CWMS Users", "TS ID Creator", "CWMS User Admins"],
    )


def test_users_roles_delete_all_roles(monkeypatch):
    monkeypatch.setattr(
        "cwmscli.utils.get_api_key", lambda api_key, api_key_loc: "test-key"
    )

    calls = {"delete_user_roles": []}

    class _FakeCwms:
        class api:
            class ApiError(Exception):
                pass

            class PermissionError(ApiError):
                pass

        @staticmethod
        def init_session(api_root, api_key):
            return None

        @staticmethod
        def get_users(office_id=None, username_like=None, page_size=None):
            return _FakeData({"users": [{"user-name": "q0hectest"}], "next-page": None})

        @staticmethod
        def get_roles():
            return ["All Users", "CWMS Users", "TS ID Creator", "CWMS User Admins"]

        @staticmethod
        def get_user(user_name):
            return _FakeData(
                {
                    "roles": {
                        "SPK": ["All Users", "CWMS Users", "TS ID Creator"],
                        "HQ": ["All Users"],
                    }
                }
            )

        @staticmethod
        def delete_user_roles(user_name, office_id, roles):
            calls["delete_user_roles"].append((user_name, office_id, roles))

    monkeypatch.setitem(__import__("sys").modules, "cwms", _FakeCwms)

    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "users",
            "roles",
            "delete",
            "--office",
            "SPK",
            "--api-root",
            "https://example.test/cda/",
            "--api-key",
            "ignored",
            "--user-name",
            "q0hectest",
            "--roles",
            "all",
        ],
    )
    assert result.exit_code == 0
    assert calls["delete_user_roles"][0] == (
        "q0hectest",
        "SPK",
        ["CWMS Users", "TS ID Creator"],
    )


def test_users_roles_add_requires_all_add_args_or_none(monkeypatch):
    monkeypatch.setattr(
        "cwmscli.utils.get_api_key", lambda api_key, api_key_loc: "test-key"
    )

    class _FakeCwms:
        class api:
            class ApiError(Exception):
                pass

            class PermissionError(ApiError):
                pass

        @staticmethod
        def init_session(api_root, api_key):
            return None

        @staticmethod
        def get_roles():
            return ["All Users", "CWMS Users", "TS ID Creator", "CWMS User Admins"]

    monkeypatch.setitem(__import__("sys").modules, "cwms", _FakeCwms)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "users",
            "roles",
            "add",
            "--office",
            "SPK",
            "--api-root",
            "https://example.test/cda/",
            "--api-key",
            "ignored",
            "--user-name",
            "q0hectest",
        ],
    )

    assert result.exit_code == 1
    assert "Either specify all add arguments" in result.output
    assert "Traceback" not in result.output


def test_users_roles_delete_requires_all_delete_args_or_none(monkeypatch):
    monkeypatch.setattr(
        "cwmscli.utils.get_api_key", lambda api_key, api_key_loc: "test-key"
    )

    class _FakeCwms:
        class api:
            class ApiError(Exception):
                pass

            class PermissionError(ApiError):
                pass

        @staticmethod
        def init_session(api_root, api_key):
            return None

        @staticmethod
        def get_roles():
            return ["All Users", "CWMS Users", "TS ID Creator", "CWMS User Admins"]

    monkeypatch.setitem(__import__("sys").modules, "cwms", _FakeCwms)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "users",
            "roles",
            "delete",
            "--office",
            "SPK",
            "--api-root",
            "https://example.test/cda/",
            "--api-key",
            "ignored",
            "--user-name",
            "q0hectest",
        ],
    )

    assert result.exit_code == 1
    assert "Either specify all delete arguments" in result.output
    assert "Traceback" not in result.output
