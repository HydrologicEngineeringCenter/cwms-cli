from pathlib import Path

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


def test_login_defaults_can_start_and_prompt(monkeypatch):
    runner = CliRunner()
    saved = {}

    def fake_import_module(name):
        if name == "requests":
            return object()
        return __import__(name)

    def fake_version(_package):
        return "999.0.0"

    def fake_default_token_file(provider):
        return Path(f"/tmp/{provider}.json")

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
        "cwmscli.utils.auth.default_token_file", fake_default_token_file
    )
    monkeypatch.setattr(
        "cwmscli.utils.auth.discover_oidc_base_url",
        lambda api_root, verify=None: DEFAULT_OIDC_BASE_URL,
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
    assert "Saved login session to /tmp/federation-eams.json" not in result.output
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
    assert saved["token_file"] == Path("/tmp/federation-eams.json")


def test_login_debug_output_includes_saved_session_details(monkeypatch):
    runner = CliRunner()

    def fake_import_module(name):
        if name == "requests":
            return object()
        return __import__(name)

    def fake_version(_package):
        return "999.0.0"

    def fake_default_token_file(provider):
        return Path(f"/tmp/{provider}.json")

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
        "cwmscli.utils.auth.default_token_file", fake_default_token_file
    )
    monkeypatch.setattr(
        "cwmscli.utils.auth.discover_oidc_base_url",
        lambda api_root, verify=None: DEFAULT_OIDC_BASE_URL,
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
    assert "federation-eams.json" in result.output
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

    def fake_default_token_file(provider):
        return Path(f"/tmp/{provider}.json")

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
        "cwmscli.utils.auth.default_token_file", fake_default_token_file
    )
    monkeypatch.setattr(
        "cwmscli.utils.auth.discover_oidc_base_url",
        lambda api_root, verify=None: DEFAULT_OIDC_BASE_URL,
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
            "Could not listen on http://127.0.0.1:5555 through http://127.0.0.1:5558 because those ports are already in use. "
            "Another `cwms-cli login` instance may still be running. Stop it before continuing, "
            "or try a different callback port with --redirect-port, for example "
            "`cwms-cli login --redirect-port 5559`."
        )

    monkeypatch.setattr(
        "cwmscli.utils.deps.importlib.import_module", fake_import_module
    )
    monkeypatch.setattr("cwmscli.utils.deps.importlib.metadata.version", fake_version)
    monkeypatch.setattr(
        "cwmscli.utils.auth.discover_oidc_base_url",
        lambda api_root, verify=None: DEFAULT_OIDC_BASE_URL,
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

    def fake_default_token_file(provider):
        return Path(f"/tmp/{provider}.json")

    def fake_discover_oidc_base_url(api_root, verify=None):
        saved["api_root"] = api_root
        saved["verify"] = verify
        return "https://identityc.sec.usace.army.mil/auth/realms/cwbi/protocol/openid-connect"

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
        "cwmscli.utils.auth.default_token_file", fake_default_token_file
    )
    monkeypatch.setattr(
        "cwmscli.utils.auth.discover_oidc_base_url", fake_discover_oidc_base_url
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
