from pathlib import Path

import pytest
from click.testing import CliRunner

from cwmscli.__main__ import cli
from cwmscli.utils.auth import (
    DEFAULT_CDA_API_ROOT,
    DEFAULT_CLIENT_ID,
    DEFAULT_OIDC_BASE_URL,
    DEFAULT_REDIRECT_HOST,
    DEFAULT_REDIRECT_PORT,
    DEFAULT_SCOPE,
    DEFAULT_TIMEOUT_SECONDS,
    CallbackBindError,
)


@pytest.fixture
def environment_logins(monkeypatch, tmp_path):
    from cwmscli.utils import auth

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("CDA_API_ROOT", raising=False)
    monkeypatch.setattr(
        auth,
        "discover_oidc_configuration",
        lambda **kwargs: {
            "oidc_base_url": DEFAULT_OIDC_BASE_URL,
            "authorization_endpoint": DEFAULT_OIDC_BASE_URL + "/auth",
            "token_endpoint": DEFAULT_OIDC_BASE_URL + "/token",
        },
    )
    monkeypatch.setattr(
        auth,
        "login_with_browser",
        lambda config, **kwargs: {
            "browser_opened": True,
            "config": config,
            "token": {
                "access_token": config.api_root + "-secret",
                "expires_at": 4102444800,
            },
        },
    )
    return CliRunner()


def test_login_preserves_sessions_when_switching_environments(
    environment_logins, monkeypatch
):
    from cwmscli.utils import init_cwms_session
    from cwmscli.utils.auth import environment_token_file, load_saved_login

    runner = environment_logins
    roots = ["https://dev.example/cwms-data", "https://prod.example/cwms-data"]
    for root in roots:
        monkeypatch.setenv("CDA_API_ROOT", root)
        result = runner.invoke(cli, ["login", "--provider", "login.gov"])
        assert result.exit_code == 0, result.output
        assert root + "-secret" not in result.output
        saved = load_saved_login(environment_token_file(root))
        assert saved["api_root"] == root
        assert saved["provider"] == "login.gov"

    calls = []

    class FakeCwms:
        @staticmethod
        def init_session(**kwargs):
            calls.append(kwargs)

    for root in [roots[0], roots[1], roots[0]]:
        init_cwms_session(FakeCwms, api_root=root + "/")
        assert calls[-1]["token"] == root + "-secret"
    init_cwms_session(FakeCwms, api_root="https://other.example/cwms-data")
    assert calls[-1]["api_key"] is None
    assert "token" not in calls[-1]


def test_login_refresh_only_changes_selected_environment(
    environment_logins, monkeypatch
):
    from cwmscli.utils import auth

    roots = ["https://dev.example/cwms-data", "https://prod.example/cwms-data"]
    for root in roots:
        auth.save_login(
            auth.environment_token_file(root),
            auth.OIDCLoginConfig(api_root=root),
            {"access_token": root, "refresh_token": root + "-refresh", "expires_at": 1},
        )
    other_before = auth.environment_token_file(roots[1]).read_bytes()
    monkeypatch.setattr(
        auth,
        "_request_token",
        lambda *args, **kwargs: {"access_token": "new-token", "expires_at": 4102444800},
    )
    result = environment_logins.invoke(
        cli, ["login", "--refresh", "--api-root", roots[0]]
    )
    assert result.exit_code == 0, result.output
    assert (
        auth.load_saved_login(auth.environment_token_file(roots[0]))["token"][
            "access_token"
        ]
        == "new-token"
    )
    assert auth.environment_token_file(roots[1]).read_bytes() == other_before


def test_explicit_token_file_cannot_refresh_other_environment(environment_logins):
    from cwmscli.utils import auth

    path = auth.environment_token_file("https://first.example")
    auth.save_login(
        path,
        auth.OIDCLoginConfig(api_root="https://first.example"),
        {"refresh_token": "secret"},
    )
    result = environment_logins.invoke(
        cli,
        [
            "login",
            "--refresh",
            "--api-root",
            "https://second.example",
            "--token-file",
            str(path),
        ],
    )
    assert result.exit_code == 1
    assert "different CDA API root" in result.output


def test_login_status_is_offline_and_shows_remaining_time(
    environment_logins, monkeypatch
):
    from cwmscli.utils import auth

    root = "https://dev.example/cwms-data"
    monkeypatch.setenv("CDA_API_ROOT", root)
    monkeypatch.setattr(auth.time, "time", lambda: 1800000000)
    path = auth.environment_token_file(root)
    auth.save_login(
        path,
        auth.OIDCLoginConfig(api_root=root),
        {
            "access_token": "access-secret",
            "refresh_token": "refresh-secret",
            "expires_at": 1800000300,
            "refresh_expires_at": 1800093723,
        },
    )
    before = path.read_bytes()
    for name in (
        "login_with_browser",
        "discover_oidc_configuration",
        "refresh_saved_login",
    ):
        monkeypatch.setattr(
            auth, name, lambda *a, **kw: pytest.fail("Status must be offline")
        )
    result = environment_logins.invoke(cli, ["login", "--status"])
    assert result.exit_code == 0, result.output
    assert "Login: saved (not verified)" in result.output
    assert "Access lifetime: 5m remaining" in result.output
    assert "Refresh session: 1d 2h 2m 3s remaining" in result.output
    assert "Refresh expires:" in result.output
    assert str(path.resolve()) in result.output
    assert "secret" not in result.output
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "token, expected",
    [
        ({"access_token": "secret"}, "not available"),
        ({"refresh_token": "secret"}, "unknown (expiry not provided)"),
        ({"refresh_token": "secret", "refresh_expires_at": 1}, "expired"),
        (
            {"refresh_token": "secret", "refresh_expires_at": "bad"},
            "unknown (invalid expiry)",
        ),
        (
            {"refresh_token": "secret", "refresh_expires_at": float("inf")},
            "unknown (invalid expiry)",
        ),
    ],
)
def test_login_status_refresh_states(environment_logins, tmp_path, token, expected):
    from cwmscli.utils import auth

    path = tmp_path / "custom.json"
    auth.save_login(path, auth.OIDCLoginConfig(), token)
    result = environment_logins.invoke(
        cli, ["login", "--status", "--token-file", str(path)]
    )
    assert result.exit_code == 0, result.output
    assert "Refresh session: " + expected in result.output
    assert "secret" not in result.output


def test_login_status_missing_and_corrupt(environment_logins, tmp_path):
    path = tmp_path / "missing.json"
    args = ["login", "--status", "--token-file", str(path)]
    result = environment_logins.invoke(cli, args)
    assert result.exit_code == 0
    assert "Login: not logged in" in result.output
    assert "Refresh session: not available" in result.output
    assert not path.exists()
    path.write_text("invalid json")
    result = environment_logins.invoke(cli, args)
    assert result.exit_code == 0
    assert "Login: unreadable" in result.output


def test_login_token_location_selects_root_without_reading(
    environment_logins, monkeypatch
):
    from cwmscli.utils import auth

    monkeypatch.setenv("CDA_API_ROOT", "https://other.example")
    monkeypatch.setattr(
        auth, "load_saved_login", lambda *a: pytest.fail("Must not read tokens")
    )
    result = environment_logins.invoke(
        cli, ["login", "--token-location", "--api-root", "https://dev.example/"]
    )
    assert result.exit_code == 0
    assert (
        str(auth.environment_token_file("https://dev.example").resolve())
        in result.output
    )


@pytest.mark.parametrize(
    "flags",
    [
        ["--status", "--refresh"],
        ["--token-location", "--refresh"],
        ["--status", "--token-location"],
    ],
)
def test_login_inspection_options_are_exclusive(environment_logins, flags):
    result = environment_logins.invoke(cli, ["login", *flags])
    assert result.exit_code == 2
    assert "Use only one" in result.output


def test_login_defaults_can_start_and_prompt(monkeypatch):
    runner = CliRunner()
    saved = {}

    def fake_import_module(name):
        if name == "requests":
            return object()
        return __import__(name)

    def fake_version(_package):
        return "999.0.0"

    def fake_environment_token_file(api_root):
        return Path("/tmp/environment-login.json")

    def fake_login_with_browser(
        config, launch_browser=True, authorization_url_callback=None
    ):
        saved["config"] = config
        saved["launch_browser"] = launch_browser
        saved["authorization_url_callback"] = authorization_url_callback
        return {
            "authorization_url": "https://example.test/auth",
            "browser_opened": False,
            "token": {
                "access_token": "access",
                "refresh_token": "refresh",
                "refresh_expires_at": 2234567890,
            },
        }

    def fake_save_login(token_file, config, token):
        saved["token_file"] = token_file
        saved["saved_config"] = config
        saved["token"] = token

    monkeypatch.setattr(
        "cwmscli.utils.deps.importlib.import_module", fake_import_module
    )
    monkeypatch.setattr("cwmscli.utils.deps.importlib.metadata.version", fake_version)
    monkeypatch.setattr(
        "cwmscli.utils.auth.environment_token_file", fake_environment_token_file
    )
    monkeypatch.setattr(
        "cwmscli.utils.auth.discover_oidc_configuration",
        lambda api_root, verify=None: {
            "oidc_base_url": DEFAULT_OIDC_BASE_URL,
            "authorization_endpoint": f"{DEFAULT_OIDC_BASE_URL}/auth",
            "token_endpoint": f"{DEFAULT_OIDC_BASE_URL}/token",
        },
    )
    monkeypatch.setattr(
        "cwmscli.utils.auth.login_with_browser", fake_login_with_browser
    )
    monkeypatch.setattr("cwmscli.utils.auth.save_login", fake_save_login)
    monkeypatch.setattr(
        "cwmscli.utils.auth.refresh_token_expiry_text",
        lambda token: "October 22, 2040 at 8:18 PM CDT",
    )

    result = runner.invoke(cli, ["login"])

    assert result.exit_code == 0
    assert "Visit this URL to authenticate:" in result.output
    assert "https://example.test/auth" in result.output
    assert "You have successfully authenticated against CWBI." in result.output
    assert (
        "Your refresh session is good until October 22, 2040 at 8:18 PM CDT."
        in result.output
    )
    assert "Saved login session to /tmp/environment-login.json" not in result.output
    assert "Refresh token is available for future reuse." not in result.output

    config = saved["config"]
    assert config.provider == "federation-eams"
    assert config.client_id == DEFAULT_CLIENT_ID
    assert saved["config"].oidc_base_url == DEFAULT_OIDC_BASE_URL
    assert config.oidc_base_url == DEFAULT_OIDC_BASE_URL
    assert config.scope == DEFAULT_SCOPE
    assert config.redirect_host == DEFAULT_REDIRECT_HOST
    assert config.redirect_port == DEFAULT_REDIRECT_PORT
    assert config.timeout_seconds == DEFAULT_TIMEOUT_SECONDS
    assert saved["launch_browser"] is True
    assert saved["authorization_url_callback"] is None
    assert saved["token_file"] == Path("/tmp/environment-login.json")


def test_login_debug_output_includes_saved_session_details(monkeypatch):
    runner = CliRunner()

    def fake_import_module(name):
        if name == "requests":
            return object()
        return __import__(name)

    def fake_version(_package):
        return "999.0.0"

    def fake_environment_token_file(api_root):
        return Path("/tmp/environment-login.json")

    def fake_login_with_browser(
        config, launch_browser=True, authorization_url_callback=None
    ):
        return {
            "authorization_url": "https://example.test/auth",
            "browser_opened": False,
            "token": {
                "access_token": "access",
                "refresh_token": "refresh",
                "expires_at": 1234567890,
                "refresh_expires_at": 2234567890,
            },
        }

    def fake_save_login(token_file, config, token):
        return None

    monkeypatch.setattr(
        "cwmscli.utils.deps.importlib.import_module", fake_import_module
    )
    monkeypatch.setattr("cwmscli.utils.deps.importlib.metadata.version", fake_version)
    monkeypatch.setattr(
        "cwmscli.utils.auth.environment_token_file", fake_environment_token_file
    )
    monkeypatch.setattr(
        "cwmscli.utils.auth.discover_oidc_configuration",
        lambda api_root, verify=None: {
            "oidc_base_url": DEFAULT_OIDC_BASE_URL,
            "authorization_endpoint": f"{DEFAULT_OIDC_BASE_URL}/auth",
            "token_endpoint": f"{DEFAULT_OIDC_BASE_URL}/token",
        },
    )
    monkeypatch.setattr(
        "cwmscli.utils.auth.login_with_browser", fake_login_with_browser
    )
    monkeypatch.setattr("cwmscli.utils.auth.save_login", fake_save_login)
    monkeypatch.setattr(
        "cwmscli.utils.auth.refresh_token_expiry_text",
        lambda token: "October 22, 2040 at 8:18 PM CDT",
    )

    result = runner.invoke(cli, ["--log-level", "DEBUG", "login"])

    assert result.exit_code == 0
    assert "You have successfully authenticated against CWBI." in result.output
    assert (
        "Your refresh session is good until October 22, 2040 at 8:18 PM CDT."
        in result.output
    )
    assert "Saved login session to" in result.output
    assert "environment-login.json" in result.output
    assert "Access token expires at 2009-02-13T23:31:30+00:00" in result.output
    assert "A refresh token is available for future reuse." in result.output


def test_login_saves_selected_fallback_callback_port(monkeypatch):
    runner = CliRunner()
    saved = {}

    def fake_import_module(name):
        if name == "requests":
            return object()
        return __import__(name)

    def fake_version(_package):
        return "999.0.0"

    def fake_environment_token_file(api_root):
        return Path("/tmp/environment-login.json")

    def fake_login_with_browser(
        config, launch_browser=True, authorization_url_callback=None
    ):
        saved["requested_config"] = config
        return {
            "authorization_url": "https://example.test/auth",
            "browser_opened": False,
            "config": config.__class__(
                client_id=config.client_id,
                oidc_base_url=config.oidc_base_url,
                redirect_host=config.redirect_host,
                redirect_port=5556,
                scope=config.scope,
                provider=config.provider,
                timeout_seconds=config.timeout_seconds,
                verify=config.verify,
            ),
            "token": {
                "access_token": "access",
                "refresh_token": "refresh",
            },
        }

    def fake_save_login(token_file, config, token):
        saved["token_file"] = token_file
        saved["saved_config"] = config
        saved["token"] = token

    monkeypatch.setattr(
        "cwmscli.utils.deps.importlib.import_module", fake_import_module
    )
    monkeypatch.setattr("cwmscli.utils.deps.importlib.metadata.version", fake_version)
    monkeypatch.setattr(
        "cwmscli.utils.auth.environment_token_file", fake_environment_token_file
    )
    monkeypatch.setattr(
        "cwmscli.utils.auth.discover_oidc_configuration",
        lambda api_root, verify=None: {
            "oidc_base_url": DEFAULT_OIDC_BASE_URL,
            "authorization_endpoint": f"{DEFAULT_OIDC_BASE_URL}/auth",
            "token_endpoint": f"{DEFAULT_OIDC_BASE_URL}/token",
        },
    )
    monkeypatch.setattr(
        "cwmscli.utils.auth.login_with_browser", fake_login_with_browser
    )
    monkeypatch.setattr("cwmscli.utils.auth.save_login", fake_save_login)

    result = runner.invoke(cli, ["login"])

    assert result.exit_code == 0
    assert saved["requested_config"].redirect_port == DEFAULT_REDIRECT_PORT
    assert saved["saved_config"].redirect_port == 5556


def test_login_shows_actionable_message_when_callback_port_is_in_use(monkeypatch):
    runner = CliRunner()

    def fake_import_module(name):
        if name == "requests":
            return object()
        return __import__(name)

    def fake_version(_package):
        return "999.0.0"

    def fake_login_with_browser(
        config, launch_browser=True, authorization_url_callback=None
    ):
        raise CallbackBindError(
            "Could not listen on http://localhost:5555 through http://localhost:5558 because those ports are already in use. "
            "Another `cwms-cli login` instance may still be running. Stop it before continuing, "
            "or try a different callback port with --redirect-port, for example "
            "`cwms-cli login --redirect-port 5559`."
        )

    monkeypatch.setattr(
        "cwmscli.utils.deps.importlib.import_module", fake_import_module
    )
    monkeypatch.setattr("cwmscli.utils.deps.importlib.metadata.version", fake_version)
    monkeypatch.setattr(
        "cwmscli.utils.auth.discover_oidc_configuration",
        lambda api_root, verify=None: {
            "oidc_base_url": DEFAULT_OIDC_BASE_URL,
            "authorization_endpoint": f"{DEFAULT_OIDC_BASE_URL}/auth",
            "token_endpoint": f"{DEFAULT_OIDC_BASE_URL}/token",
        },
    )
    monkeypatch.setattr(
        "cwmscli.utils.auth.login_with_browser", fake_login_with_browser
    )

    result = runner.invoke(cli, ["login"])

    assert result.exit_code == 1
    assert "ports are already in use" in result.output
    assert "Another `cwms-cli login` instance may still be running" in result.output


def test_login_discovers_oidc_config_from_api_root(monkeypatch):
    runner = CliRunner()
    saved = {}

    def fake_import_module(name):
        if name == "requests":
            return object()
        return __import__(name)

    def fake_version(_package):
        return "999.0.0"

    def fake_environment_token_file(api_root):
        return Path("/tmp/environment-login.json")

    def fake_discover_oidc_configuration(api_root, verify=None):
        saved["api_root"] = api_root
        saved["verify"] = verify
        return {
            "oidc_base_url": "https://identityc.sec.usace.army.mil/auth/realms/cwbi/protocol/openid-connect",
            "authorization_endpoint": "https://identityc.sec.usace.army.mil/auth/realms/cwbi/protocol/openid-connect/auth",
            "token_endpoint": "https://identityc.sec.usace.army.mil/auth/realms/cwbi/protocol/openid-connect/token",
        }

    def fake_login_with_browser(
        config, launch_browser=True, authorization_url_callback=None
    ):
        saved["config"] = config
        return {
            "authorization_url": "https://example.test/auth",
            "browser_opened": False,
            "token": {
                "access_token": "access",
                "refresh_token": "refresh",
            },
        }

    monkeypatch.setattr(
        "cwmscli.utils.deps.importlib.import_module", fake_import_module
    )
    monkeypatch.setattr("cwmscli.utils.deps.importlib.metadata.version", fake_version)
    monkeypatch.setattr(
        "cwmscli.utils.auth.environment_token_file", fake_environment_token_file
    )
    monkeypatch.setattr(
        "cwmscli.utils.auth.discover_oidc_configuration",
        fake_discover_oidc_configuration,
    )
    monkeypatch.setattr(
        "cwmscli.utils.auth.login_with_browser", fake_login_with_browser
    )
    monkeypatch.setattr("cwmscli.utils.auth.save_login", lambda *args, **kwargs: None)

    result = runner.invoke(cli, ["login", "--api-root", DEFAULT_CDA_API_ROOT])

    assert result.exit_code == 0
    assert saved["api_root"] == DEFAULT_CDA_API_ROOT
    assert saved["verify"] is None
    assert (
        saved["config"].oidc_base_url
        == "https://identityc.sec.usace.army.mil/auth/realms/cwbi/protocol/openid-connect"
    )
