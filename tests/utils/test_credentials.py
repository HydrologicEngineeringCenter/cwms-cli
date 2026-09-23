from pathlib import Path

import pytest

from cwmscli.utils import get_saved_login_token, init_cwms_session


def test_legacy_provider_token_is_not_sent_to_another_api(monkeypatch, tmp_path):
    from cwmscli.utils.auth import OIDCLoginConfig, default_token_file, save_login

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    save_login(
        default_token_file("federation-eams"),
        OIDCLoginConfig(),
        {"access_token": "legacy-secret"},
    )
    assert get_saved_login_token(api_root="https://other.example") is None


def test_automatic_refresh_preserves_other_environment(monkeypatch, tmp_path):
    from cwmscli.utils import auth

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    roots = ["https://dev.example", "https://prod.example"]
    for root in roots:
        auth.save_login(
            auth.environment_token_file(root),
            auth.OIDCLoginConfig(
                api_root=root,
                token_endpoint_url="https://identity.example/custom-token",
            ),
            {
                "access_token": "expired",
                "expires_at": 1,
                "refresh_token": root + "-refresh",
                "refresh_expires_at": 4102444800,
            },
        )
    other_before = auth.environment_token_file(roots[1]).read_bytes()
    calls = []

    def request(url, data, verify=None):
        calls.append((url, data))
        return {"access_token": "refreshed", "expires_at": 4102444800}

    monkeypatch.setattr(auth, "_request_token", request)
    assert get_saved_login_token(api_root=roots[0]) == "refreshed"
    assert calls[0][0] == "https://identity.example/custom-token"
    assert calls[0][1]["refresh_token"] == roots[0] + "-refresh"
    assert auth.environment_token_file(roots[1]).read_bytes() == other_before
    saved = auth.load_saved_login(auth.environment_token_file(roots[0]))
    assert saved["api_root"] == roots[0]
    assert saved["token"]["refresh_expires_at"] == 4102444800


def test_refresh_network_failure_falls_back(monkeypatch, tmp_path):
    import requests

    from cwmscli.utils import auth

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    root = "https://dev.example"
    auth.save_login(
        auth.environment_token_file(root),
        auth.OIDCLoginConfig(api_root=root),
        {"access_token": "expired", "expires_at": 1, "refresh_token": "secret"},
    )

    def fail(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(requests, "post", fail)
    assert get_saved_login_token(api_root=root) is None


@pytest.mark.parametrize("expiry", ["bad", float("nan"), float("inf")])
def test_invalid_expiry_is_not_used(monkeypatch, tmp_path, expiry):
    from cwmscli.utils.auth import OIDCLoginConfig, environment_token_file, save_login

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    root = "https://example.test"
    save_login(
        environment_token_file(root),
        OIDCLoginConfig(api_root=root),
        {"access_token": "secret", "expires_at": expiry},
    )
    assert get_saved_login_token(api_root=root) is None


def test_get_saved_login_token_returns_access_token(monkeypatch):
    monkeypatch.setattr(
        "cwmscli.utils.auth.environment_token_file",
        lambda provider: Path("/tmp/test.json"),
    )
    monkeypatch.setattr(
        "cwmscli.utils.auth.load_saved_login",
        lambda path: {"token": {"access_token": "saved-token"}},
    )

    assert get_saved_login_token() == "saved-token"


def test_init_cwms_session_falls_back_to_api_key(monkeypatch):
    calls = []

    class FakeCwms:
        @staticmethod
        def init_session(api_root, api_key=None, token=None):
            calls.append((api_root, api_key, token))
            return "session"

    monkeypatch.setattr(
        "cwmscli.utils.get_saved_login_token", lambda *args, **kwargs: None
    )

    result = init_cwms_session(
        FakeCwms,
        api_root="https://example.test/cwms-data",
        api_key="apikey 123",
    )

    assert result == "session"
    assert calls == [("https://example.test/cwms-data", "apikey 123", None)]


def test_init_cwms_session_prefers_saved_token(monkeypatch):
    calls = []

    class FakeCwms:
        @staticmethod
        def init_session(api_root, api_key=None, token=None):
            calls.append((api_root, api_key, token))
            return "session"

    monkeypatch.setattr(
        "cwmscli.utils.get_saved_login_token", lambda *args, **kwargs: "saved-token"
    )

    result = init_cwms_session(
        FakeCwms,
        api_root="https://example.test/cwms-data",
        api_key="apikey 123",
    )

    assert result == "session"
    assert calls == [("https://example.test/cwms-data", None, "saved-token")]


def test_get_saved_login_token_ignores_expired_token(monkeypatch):
    monkeypatch.setattr(
        "cwmscli.utils.auth.environment_token_file",
        lambda provider: Path("/tmp/test.json"),
    )
    monkeypatch.setattr(
        "cwmscli.utils.auth.load_saved_login",
        lambda path: {"token": {"access_token": "saved-token", "expires_at": 1}},
    )

    assert get_saved_login_token() is None


def test_get_saved_login_token_refreshes_expired_token(monkeypatch):
    saved = {}

    monkeypatch.setattr(
        "cwmscli.utils.auth.environment_token_file",
        lambda provider: Path("/tmp/test.json"),
    )
    monkeypatch.setattr(
        "cwmscli.utils.auth.load_saved_login",
        lambda path: {"token": {"access_token": "stale-token", "expires_at": 1}},
    )
    monkeypatch.setattr(
        "cwmscli.utils.auth.refresh_saved_login",
        lambda token_file: {
            "config": "config-object",
            "token": {"access_token": "fresh-token", "refresh_token": "refresh"},
        },
    )
    monkeypatch.setattr(
        "cwmscli.utils.auth.save_login",
        lambda token_file, config, token: saved.update(
            {"token_file": token_file, "config": config, "token": token}
        ),
    )

    assert get_saved_login_token() == "fresh-token"
    assert saved == {
        "token_file": Path("/tmp/test.json"),
        "config": "config-object",
        "token": {"access_token": "fresh-token", "refresh_token": "refresh"},
    }


def test_get_saved_login_token_falls_back_when_refresh_fails(monkeypatch):
    monkeypatch.setattr(
        "cwmscli.utils.auth.environment_token_file",
        lambda provider: Path("/tmp/test.json"),
    )
    monkeypatch.setattr(
        "cwmscli.utils.auth.load_saved_login",
        lambda path: {"token": {"access_token": "stale-token", "expires_at": 1}},
    )

    class FakeAuthError(Exception):
        pass

    monkeypatch.setattr("cwmscli.utils.auth.AuthError", FakeAuthError)

    def fail_refresh(token_file):
        raise FakeAuthError("invalid_grant")

    monkeypatch.setattr("cwmscli.utils.auth.refresh_saved_login", fail_refresh)

    assert get_saved_login_token() is None
