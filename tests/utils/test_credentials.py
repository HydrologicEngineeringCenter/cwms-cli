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
