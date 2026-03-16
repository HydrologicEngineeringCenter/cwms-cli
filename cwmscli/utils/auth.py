import datetime as dt
import http.server
import json
import os
import socketserver
import time
import urllib.parse
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_CLIENT_ID = "cwms"
DEFAULT_OIDC_BASE_URL = (
    "https://identity-test.cwbi.us/auth/realms/cwbi/protocol/openid-connect"
)
DEFAULT_REDIRECT_HOST = "127.0.0.1"
DEFAULT_REDIRECT_PORT = 5000
DEFAULT_SCOPE = "openid profile"
DEFAULT_TIMEOUT_SECONDS = 180
PROVIDER_IDP_HINTS = {
    "federation-eams": "federation-eams",
    "login.gov": "login.gov",
}


class AuthError(Exception):
    pass


@dataclass(frozen=True)
class OIDCLoginConfig:
    client_id: str = DEFAULT_CLIENT_ID
    oidc_base_url: str = DEFAULT_OIDC_BASE_URL
    redirect_host: str = DEFAULT_REDIRECT_HOST
    redirect_port: int = DEFAULT_REDIRECT_PORT
    scope: str = DEFAULT_SCOPE
    provider: str = "federation-eams"
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    verify: Optional[str] = None

    @property
    def redirect_uri(self) -> str:
        return f"http://{self.redirect_host}:{self.redirect_port}"

    @property
    def authorization_endpoint(self) -> str:
        return f"{self.oidc_base_url}/auth"

    @property
    def token_endpoint(self) -> str:
        return f"{self.oidc_base_url}/token"

    @property
    def provider_hint(self) -> str:
        return PROVIDER_IDP_HINTS[self.provider]


class _SingleRequestServer(socketserver.TCPServer):
    allow_reuse_address = True

    def __init__(self, server_address, handler_cls):
        super().__init__(server_address, handler_cls)
        self.callback_params: Optional[Dict[str, str]] = None


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed_path = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_path.query)
        flattened = {key: values[0] for key, values in query_params.items() if values}
        self.server.callback_params = flattened  # type: ignore[attr-defined]

        self.send_response(200, "OK")
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Authentication complete. You can close this window.")

    def log_message(self, format: str, *args: Any) -> None:
        return


def default_token_file(provider: str) -> Path:
    config_root = os.getenv("XDG_CONFIG_HOME")
    if config_root:
        base_dir = Path(config_root)
    else:
        base_dir = Path.home() / ".config"
    return base_dir / "cwms-cli" / "auth" / f"{provider}.json"


def token_expiry_text(token: Dict[str, Any]) -> Optional[str]:
    expires_at = token.get("expires_at")
    if expires_at is None:
        return None
    try:
        expiry = dt.datetime.fromtimestamp(float(expires_at), tz=dt.timezone.utc)
    except (TypeError, ValueError, OSError):
        return None
    return expiry.isoformat()


def load_saved_login(token_file: Path) -> Dict[str, Any]:
    try:
        with token_file.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as e:
        raise AuthError(f"No saved login found at {token_file}") from e
    except json.JSONDecodeError as e:
        raise AuthError(f"Saved login file is not valid JSON: {token_file}") from e


def save_login(
    token_file: Path, config: OIDCLoginConfig, token: Dict[str, Any]
) -> None:
    token_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "saved_at": dt.datetime.now(tz=dt.timezone.utc).isoformat(),
        "client_id": config.client_id,
        "oidc_base_url": config.oidc_base_url,
        "provider": config.provider,
        "scope": config.scope,
        "redirect_uri": config.redirect_uri,
        "token": token,
    }
    with token_file.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")
    os.chmod(token_file, 0o600)


def _verify_setting(verify: Optional[str]) -> Any:
    if verify:
        return verify
    return True


def _receive_callback(config: OIDCLoginConfig) -> Dict[str, str]:
    with _SingleRequestServer(
        (config.redirect_host, config.redirect_port), _CallbackHandler
    ) as server:
        server.timeout = 1
        deadline = time.monotonic() + config.timeout_seconds
        while server.callback_params is None:
            server.handle_request()
            if time.monotonic() >= deadline:
                raise AuthError(
                    f"Timed out waiting for the login callback on {config.redirect_uri}"
                )
        return server.callback_params


def login_with_browser(
    config: OIDCLoginConfig,
    launch_browser: bool = True,
    authorization_url_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    from authlib.common.security import generate_token
    from authlib.integrations.requests_client import OAuth2Session

    client = OAuth2Session(
        client_id=config.client_id,
        scope=config.scope,
        redirect_uri=config.redirect_uri,
    )
    code_verifier = generate_token(48)
    authorization_url, state = client.create_authorization_url(
        config.authorization_endpoint,
        code_verifier=code_verifier,
        kc_idp_hint=config.provider_hint,
        response_type="code",
    )
    if authorization_url_callback is not None:
        authorization_url_callback(authorization_url)

    if launch_browser:
        opened = webbrowser.open(authorization_url)
        if not opened:
            launch_browser = False

    callback_params = _receive_callback(config)
    if callback_params.get("error"):
        raise AuthError(
            f"Identity provider returned an error: {callback_params['error']}"
        )
    if callback_params.get("state") != state:
        raise AuthError("OIDC state mismatch in login callback")
    if "code" not in callback_params:
        raise AuthError("OIDC callback did not include an authorization code")

    callback_url = (
        f"{config.redirect_uri}?{urllib.parse.urlencode(callback_params, doseq=False)}"
    )
    token_client = OAuth2Session(
        client_id=config.client_id,
        scope=config.scope,
        redirect_uri=config.redirect_uri,
        state=state,
    )
    token_client.verify = _verify_setting(config.verify)
    token = token_client.fetch_token(
        config.token_endpoint,
        authorization_response=callback_url,
        code_verifier=code_verifier,
    )
    return {
        "authorization_url": authorization_url,
        "browser_opened": launch_browser,
        "token": token,
    }


def refresh_saved_login(
    token_file: Path,
    verify: Optional[str] = None,
) -> Dict[str, Any]:
    from authlib.integrations.requests_client import OAuth2Session

    saved = load_saved_login(token_file)
    token = saved.get("token", {})
    refresh_token = token.get("refresh_token")
    if not refresh_token:
        raise AuthError(f"No refresh token is stored in {token_file}")

    client = OAuth2Session(
        client_id=saved["client_id"],
        token=token,
        scope=saved.get("scope"),
        redirect_uri=saved.get("redirect_uri"),
    )
    client.verify = _verify_setting(verify)
    refreshed = client.refresh_token(
        f"{saved['oidc_base_url']}/token",
        refresh_token=refresh_token,
    )
    if "refresh_token" not in refreshed:
        refreshed["refresh_token"] = refresh_token
    return {
        "config": OIDCLoginConfig(
            client_id=saved["client_id"],
            oidc_base_url=saved["oidc_base_url"],
            provider=saved["provider"],
            scope=saved["scope"],
            redirect_host=urllib.parse.urlparse(saved["redirect_uri"]).hostname
            or DEFAULT_REDIRECT_HOST,
            redirect_port=urllib.parse.urlparse(saved["redirect_uri"]).port
            or DEFAULT_REDIRECT_PORT,
            verify=verify,
        ),
        "token": refreshed,
    }
