import datetime as dt
import hashlib
import http.server
import json
import os
import secrets
import socketserver
import time
import urllib.parse
import webbrowser
from base64 import urlsafe_b64encode
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
DEFAULT_TIMEOUT_SECONDS = 30
PROVIDER_IDP_HINTS = {
    "federation-eams": "federation-eams",
    "login.gov": "login.gov",
}


class AuthError(Exception):
    pass


class LoginTimeoutError(AuthError):
    pass


class CallbackBindError(AuthError):
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


def _is_address_in_use_error(error: OSError) -> bool:
    if getattr(error, "errno", None) in {98, 10048}:
        return True
    if getattr(error, "winerror", None) == 10048:
        return True
    return "address already in use" in str(error).lower()


def _generate_token(length: int) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _create_s256_code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _token_expiry_timestamp(expires_in: Any) -> Optional[float]:
    try:
        seconds = int(expires_in)
    except (TypeError, ValueError):
        return None
    return time.time() + seconds


def _normalize_token_payload(token: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(token)
    if "expires_at" not in normalized:
        expires_at = _token_expiry_timestamp(normalized.get("expires_in"))
        if expires_at is not None:
            normalized["expires_at"] = expires_at
    return normalized


def _request_token(
    url: str,
    data: Dict[str, Any],
    verify: Optional[str] = None,
) -> Dict[str, Any]:
    import requests

    response = requests.post(
        url,
        data=data,
        verify=_verify_setting(verify),
        timeout=30,
    )
    try:
        payload = response.json()
    except ValueError as e:
        raise AuthError(
            f"Token endpoint returned non-JSON response with status {response.status_code}"
        ) from e
    if response.ok:
        return _normalize_token_payload(payload)

    if isinstance(payload, dict):
        error = payload.get("error")
        description = payload.get("error_description")
    else:
        error = None
        description = None
    details = error or f"HTTP {response.status_code}"
    if description:
        details = f"{details}: {description}"
    raise AuthError(f"Token request failed: {details}")


def _receive_callback(config: OIDCLoginConfig) -> Dict[str, str]:
    try:
        with _SingleRequestServer(
            (config.redirect_host, config.redirect_port), _CallbackHandler
        ) as server:
            server.timeout = 1
            deadline = time.monotonic() + config.timeout_seconds
            while server.callback_params is None:
                server.handle_request()
                if time.monotonic() >= deadline:
                    raise LoginTimeoutError(
                        f"Timed out waiting for the login callback on {config.redirect_uri}"
                    )
            return server.callback_params
    except OSError as e:
        if _is_address_in_use_error(e):
            raise CallbackBindError(
                f"Could not listen on {config.redirect_uri} because that port is already in use. "
                "Another `cwms-cli login` instance may still be running. Stop it before continuing, "
                "or try a different callback port with --redirect-port, for example "
                "`cwms-cli login --redirect-port 5555`."
            ) from e
        raise CallbackBindError(
            f"Could not listen on {config.redirect_uri}. "
            "Try a different callback port with --redirect-port, for example "
            "`cwms-cli login --redirect-port 5555`."
        ) from e


def login_with_browser(
    config: OIDCLoginConfig,
    launch_browser: bool = True,
    authorization_url_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    code_verifier = _generate_token(48)
    code_challenge = _create_s256_code_challenge(code_verifier)
    state = _generate_token(30)
    authorization_params = {
        "response_type": "code",
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "scope": config.scope,
        "state": state,
        "code_challenge_method": "S256",
        "code_challenge": code_challenge,
        "kc_idp_hint": config.provider_hint,
    }
    authorization_url = (
        f"{config.authorization_endpoint}?"
        f"{urllib.parse.urlencode(authorization_params)}"
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

    token = _request_token(
        config.token_endpoint,
        data={
            "grant_type": "authorization_code",
            "client_id": config.client_id,
            "code": callback_params["code"],
            "redirect_uri": config.redirect_uri,
            "code_verifier": code_verifier,
        },
        verify=config.verify,
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
    saved = load_saved_login(token_file)
    token = saved.get("token", {})
    refresh_token = token.get("refresh_token")
    if not refresh_token:
        raise AuthError(f"No refresh token is stored in {token_file}")

    refreshed = _request_token(
        f"{saved['oidc_base_url']}/token",
        data={
            "grant_type": "refresh_token",
            "client_id": saved["client_id"],
            "refresh_token": refresh_token,
            "scope": saved.get("scope"),
        },
        verify=verify,
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
