from pathlib import Path

from cwmscli.utils import get_saved_login_token, init_cwms_session


def test_get_saved_login_token_returns_access_token(monkeypatch):
    monkeypatch.setattr(
        "cwmscli.utils.auth.default_token_file", lambda provider: Path("/tmp/test.json")
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
        "cwmscli.utils.auth.default_token_file", lambda provider: Path("/tmp/test.json")
    )
    monkeypatch.setattr(
        "cwmscli.utils.auth.load_saved_login",
        lambda path: {"token": {"access_token": "saved-token", "expires_at": 1}},
    )

    assert get_saved_login_token() is None


def test_get_saved_login_token_refreshes_expired_token(monkeypatch):
    saved = {}

    monkeypatch.setattr(
        "cwmscli.utils.auth.default_token_file", lambda provider: Path("/tmp/test.json")
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
        "cwmscli.utils.auth.default_token_file", lambda provider: Path("/tmp/test.json")
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
