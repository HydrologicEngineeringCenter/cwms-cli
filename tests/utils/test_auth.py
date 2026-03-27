import urllib.parse
from http.client import HTTPConnection
from threading import Thread

import pytest

from cwmscli.utils.auth import (
    CallbackBindError,
    OIDCLoginConfig,
    _receive_callback,
    login_with_browser,
)


def test_login_with_browser_includes_pkce_parameters(monkeypatch):
    config = OIDCLoginConfig()
    generated = iter(["verifier-token", "state-token"])
    captured = {}

    def fake_generate_token(_length):
        return next(generated)

    def fake_receive_callback(_config):
        return {
            "state": "state-token",
            "code": "auth-code",
            "session_state": "session-state",
        }

    def fake_request_token(url, data, verify=None):
        captured["request_token"] = {
            "url": url,
            "data": data,
            "verify": verify,
        }
        return {"access_token": "access", "refresh_token": "refresh"}

    monkeypatch.setattr("cwmscli.utils.auth._generate_token", fake_generate_token)
    monkeypatch.setattr("cwmscli.utils.auth._request_token", fake_request_token)
    monkeypatch.setattr("cwmscli.utils.auth._receive_callback", fake_receive_callback)

    result = login_with_browser(config, launch_browser=False)

    parsed = urllib.parse.urlparse(result["authorization_url"])
    params = urllib.parse.parse_qs(parsed.query)

    assert params["client_id"] == ["cwms"]
    assert params["response_type"] == ["code"]
    assert params["redirect_uri"] == [config.redirect_uri]
    assert params["scope"] == ["openid profile"]
    assert params["state"] == ["state-token"]
    assert params["kc_idp_hint"] == ["federation-eams"]
    assert params["code_challenge_method"] == ["S256"]
    assert params["code_challenge"] == ["m_r6OIumhSE9k2Tx2xDwPs3q2ppJMPnPEp5--b1wOKc"]

    assert captured["request_token"]["url"] == config.token_endpoint
    assert captured["request_token"]["verify"] is None
    assert captured["request_token"]["data"] == {
        "grant_type": "authorization_code",
        "client_id": "cwms",
        "code": "auth-code",
        "redirect_uri": "http://127.0.0.1:5555",
        "code_verifier": "verifier-token",
    }


def test_receive_callback_reports_port_already_in_use(monkeypatch):
    config = OIDCLoginConfig()

    def fake_server(_server_address, _handler_cls):
        error = OSError(
            10048, "Only one usage of each socket address is normally permitted"
        )
        error.winerror = 10048
        raise error

    monkeypatch.setattr("cwmscli.utils.auth._SingleRequestServer", fake_server)

    with pytest.raises(CallbackBindError) as excinfo:
        _receive_callback(config)

    assert "port is already in use" in str(excinfo.value)
    assert "Another `cwms-cli login` instance may still be running" in str(
        excinfo.value
    )


def test_receive_callback_serves_branded_html_page():
    config = OIDCLoginConfig(redirect_port=5567, timeout_seconds=5)
    captured = {}

    def receive_callback():
        captured["params"] = _receive_callback(config)

    thread = Thread(target=receive_callback, daemon=True)
    thread.start()

    connection = HTTPConnection(config.redirect_host, config.redirect_port, timeout=5)
    connection.request("GET", "/?state=example-state&code=example-code")
    response = connection.getresponse()
    body = response.read().decode("utf-8")
    connection.close()
    thread.join(timeout=5)

    assert response.status == 200
    assert response.getheader("Content-Type") == "text/html; charset=utf-8"
    assert "U.S. Army Corps of Engineers" in body
    assert "Login complete." in body
    assert "Return to the terminal" in body
    assert "Close this tab" in body
    assert "#c1121f" in body
    assert captured["params"] == {"state": "example-state", "code": "example-code"}
