import urllib.parse

from cwmscli.utils.auth import OIDCLoginConfig, login_with_browser


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
        "redirect_uri": "http://127.0.0.1:5000",
        "code_verifier": "verifier-token",
    }
