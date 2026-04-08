import urllib.parse
from http.client import HTTPConnection
from threading import Thread

import pytest

from cwmscli.utils.auth import (
    CallbackBindError,
    OIDCLoginConfig,
    _extract_oidc_base_url_from_openapi,
    _receive_callback,
    discover_oidc_base_url,
    discover_oidc_configuration,
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
        "redirect_uri": "http://localhost:5555",
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


def test_extract_oidc_base_url_from_openapi_prefers_usable_flow_url():
    document = {
        "components": {
            "securitySchemes": {
                "OpenIDConnect": {
                    "type": "openIdConnect",
                    "openIdConnectUrl": "https://identityc.sec.usace.army.mil/auth/realms/cwbi/.well-known/openid-configuration/auth/realms/cwbi/.well-known/openid-configuration",
                    "flows": {
                        "authorizationCode": {
                            "authorizationUrl": "https://identityc.sec.usace.army.mil/auth/realms/cwbi/.well-known/openid-configuration/auth/realms/cwbi/protocol/openid-connect/auth",
                            "tokenUrl": "https://identityc.sec.usace.army.mil/auth/realms/cwbi/.well-known/openid-configuration/auth/realms/cwbi/protocol/openid-connect/token",
                        }
                    },
                }
            }
        }
    }

    assert (
        _extract_oidc_base_url_from_openapi(document)
        == "https://identityc.sec.usace.army.mil/auth/realms/cwbi/protocol/openid-connect"
    )


def test_discover_oidc_base_url_uses_cache_on_request_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "cwmscli.utils.auth._oidc_cache_file", lambda: tmp_path / "oidc-cache.json"
    )
    (tmp_path / "oidc-cache.json").write_text(
        '{"entries":{"https://example.test/cwms-data":"https://cached.example/auth/realms/cwbi/protocol/openid-connect"}}',
        encoding="utf-8",
    )

    class FakeRequests:
        class RequestException(Exception):
            pass

        @staticmethod
        def get(*args, **kwargs):
            raise FakeRequests.RequestException("boom")

    monkeypatch.setitem(__import__("sys").modules, "requests", FakeRequests)

    assert (
        discover_oidc_base_url("https://example.test/cwms-data")
        == "https://cached.example/auth/realms/cwbi/protocol/openid-connect"
    )


def test_discover_oidc_configuration_uses_discovery_document(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "cwmscli.utils.auth._oidc_cache_file", lambda: tmp_path / "oidc-cache.json"
    )

    swagger_document = {
        "components": {
            "securitySchemes": {
                "OpenIDConnect": {
                    "type": "openIdConnect",
                    "openIdConnectUrl": "http://auth:8081/auth/realms/cwms/.well-known/openid-configuration",
                }
            }
        }
    }

    class FakeResponse:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code >= 400:
                raise FakeRequests.RequestException(f"HTTP {self.status_code}")

        def json(self):
            return self._payload

    class FakeRequests:
        class RequestException(Exception):
            pass

        @staticmethod
        def get(url, verify=True, timeout=30):
            if url == "http://localhost:8081/cwms-data/swagger-docs":
                return FakeResponse(swagger_document)
            if (
                url
                == "http://auth:8081/auth/realms/cwms/.well-known/openid-configuration"
            ):
                raise FakeRequests.RequestException("unreachable")
            if (
                url
                == "http://localhost:8081/auth/realms/cwms/.well-known/openid-configuration"
            ):
                raise FakeRequests.RequestException("still unreachable")
            if (
                url
                == "http://localhost:8082/auth/realms/cwms/.well-known/openid-configuration"
            ):
                return FakeResponse(
                    {
                        "issuer": "http://localhost:8082/auth/realms/cwms",
                        "authorization_endpoint": "http://localhost:8082/auth/realms/cwms/protocol/openid-connect/auth",
                        "token_endpoint": "http://localhost:8082/auth/realms/cwms/protocol/openid-connect/token",
                    }
                )
            raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setitem(__import__("sys").modules, "requests", FakeRequests)

    assert discover_oidc_configuration("http://localhost:8081/cwms-data") == {
        "oidc_base_url": "http://localhost:8082/auth/realms/cwms/protocol/openid-connect",
        "authorization_endpoint": "http://localhost:8082/auth/realms/cwms/protocol/openid-connect/auth",
        "token_endpoint": "http://localhost:8082/auth/realms/cwms/protocol/openid-connect/token",
    }


def test_discover_oidc_base_url_prefers_reachable_localhost_oidc_endpoint(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        "cwmscli.utils.auth._oidc_cache_file", lambda: tmp_path / "oidc-cache.json"
    )

    swagger_document = {
        "components": {
            "securitySchemes": {
                "OpenIDConnect": {
                    "type": "openIdConnect",
                    "openIdConnectUrl": "http://auth:8081/auth/realms/cwms/.well-known/openid-configuration",
                }
            }
        }
    }

    class FakeResponse:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code >= 400:
                raise FakeRequests.RequestException(f"HTTP {self.status_code}")

        def json(self):
            return self._payload

    class FakeRequests:
        class RequestException(Exception):
            pass

        @staticmethod
        def get(url, verify=True, timeout=30):
            if url == "http://localhost:8081/cwms-data/swagger-docs":
                return FakeResponse(swagger_document)
            if (
                url
                == "http://auth:8081/auth/realms/cwms/.well-known/openid-configuration"
            ):
                raise FakeRequests.RequestException("unreachable")
            if (
                url
                == "http://localhost:8081/auth/realms/cwms/.well-known/openid-configuration"
            ):
                raise FakeRequests.RequestException("still unreachable")
            if (
                url
                == "http://localhost:8082/auth/realms/cwms/.well-known/openid-configuration"
            ):
                return FakeResponse(
                    {
                        "authorization_endpoint": "http://localhost:8082/auth/realms/cwms/protocol/openid-connect/auth",
                        "token_endpoint": "http://localhost:8082/auth/realms/cwms/protocol/openid-connect/token",
                    }
                )
            raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setitem(__import__("sys").modules, "requests", FakeRequests)

    assert (
        discover_oidc_base_url("http://localhost:8081/cwms-data")
        == "http://localhost:8082/auth/realms/cwms/protocol/openid-connect"
    )
