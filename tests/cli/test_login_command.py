from pathlib import Path

from click.testing import CliRunner

from cwmscli.__main__ import cli
from cwmscli.utils.auth import (
    DEFAULT_CLIENT_ID,
    DEFAULT_OIDC_BASE_URL,
    DEFAULT_REDIRECT_HOST,
    DEFAULT_REDIRECT_PORT,
    DEFAULT_SCOPE,
    DEFAULT_TIMEOUT_SECONDS,
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
        "cwmscli.utils.auth.login_with_browser", fake_login_with_browser
    )
    monkeypatch.setattr("cwmscli.utils.auth.save_login", fake_save_login)

    result = runner.invoke(cli, ["login"])

    assert result.exit_code == 0
    assert "Visit this URL to authenticate:" in result.output
    assert "https://example.test/auth" in result.output
    assert "Saved login session to /tmp/federation-eams.json" in result.output
    assert "Refresh token is available for future reuse." in result.output

    config = saved["config"]
    assert config.provider == "federation-eams"
    assert config.client_id == DEFAULT_CLIENT_ID
    assert config.oidc_base_url == DEFAULT_OIDC_BASE_URL
    assert config.scope == DEFAULT_SCOPE
    assert config.redirect_host == DEFAULT_REDIRECT_HOST
    assert config.redirect_port == DEFAULT_REDIRECT_PORT
    assert config.timeout_seconds == DEFAULT_TIMEOUT_SECONDS
    assert saved["launch_browser"] is True
    assert saved["authorization_url_callback"] is None
    assert saved["token_file"] == Path("/tmp/federation-eams.json")
