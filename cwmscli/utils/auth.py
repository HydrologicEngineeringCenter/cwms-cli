import datetime as dt
import hashlib
import http.server
import json
import os
import re
import secrets
import socketserver
import time
import urllib.parse
import webbrowser
from base64 import urlsafe_b64encode
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_CLIENT_ID = "cwms"
DEFAULT_CDA_API_ROOT = "https://cwms-data.usace.army.mil/cwms-data"
DEFAULT_OIDC_BASE_URL = (
    "https://identity-test.cwbi.us/auth/realms/cwbi/protocol/openid-connect"
)
DEFAULT_REDIRECT_HOST = "localhost"
DEFAULT_REDIRECT_PORT = 5555
DEFAULT_SCOPE = "openid profile"
DEFAULT_TIMEOUT_SECONDS = 30
PORT_SEARCH_ATTEMPTS = 4
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
    authorization_endpoint_url: Optional[str] = None
    token_endpoint_url: Optional[str] = None
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
        if self.authorization_endpoint_url:
            return self.authorization_endpoint_url
        return f"{self.oidc_base_url}/auth"

    @property
    def token_endpoint(self) -> str:
        if self.token_endpoint_url:
            return self.token_endpoint_url
        return f"{self.oidc_base_url}/token"

    @property
    def provider_hint(self) -> str:
        return PROVIDER_IDP_HINTS[self.provider]


class _SingleRequestServer(socketserver.TCPServer):
    allow_reuse_address = True

    def __init__(self, server_address, handler_cls):
        super().__init__(server_address, handler_cls)
        self.callback_params: Optional[Dict[str, str]] = None


def _callback_success_page() -> bytes:
    template_path = Path(__file__).with_name("callback_success.html")
    return template_path.read_bytes()


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed_path = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_path.query)
        flattened = {key: values[0] for key, values in query_params.items() if values}
        self.server.callback_params = flattened  # type: ignore[attr-defined]

        self.send_response(200, "OK")
        body = _callback_success_page()
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def default_token_file(provider: str) -> Path:
    config_root = os.getenv("XDG_CONFIG_HOME")
    if config_root:
        base_dir = Path(config_root)
    else:
        base_dir = Path.home() / ".config"
    return base_dir / "cwms-cli" / "auth" / f"{provider}.json"


def _oidc_cache_file() -> Path:
    return default_token_file("discovery").with_name("oidc-cache.json")


def _normalize_api_root(api_root: str) -> str:
    return api_root.rstrip("/")


def _swagger_docs_url(api_root: str) -> str:
    return f"{_normalize_api_root(api_root)}/swagger-docs"


def _is_local_host(hostname: Optional[str]) -> bool:
    return hostname in {"localhost", "127.0.0.1", "::1"}


def _realm_base_from_url(candidate: str) -> Optional[str]:
    if not candidate:
        return None
    parsed = urllib.parse.urlparse(candidate)
    if not parsed.scheme or not parsed.netloc:
        return None
    matches = re.findall(
        r"(/auth/realms/[^/]+/protocol/openid-connect)(?:/(?:auth|token))?$",
        parsed.path,
    )
    if matches:
        return f"{parsed.scheme}://{parsed.netloc}{matches[-1]}"

    if "/.well-known/openid-configuration" in parsed.path:
        base_path = parsed.path.split("/.well-known/openid-configuration", 1)[0]
        if base_path:
            return (
                f"{parsed.scheme}://{parsed.netloc}{base_path}/protocol/openid-connect"
            )
    return None


def _extract_oidc_base_url_from_openapi(document: Dict[str, Any]) -> str:
    schemes = document.get("components", {}).get("securitySchemes", {})
    oidc = schemes.get("OpenIDConnect", {})

    candidates = []
    openid_url = oidc.get("openIdConnectUrl")
    if isinstance(openid_url, str):
        candidates.append(openid_url)

    flows = oidc.get("flows", {})
    for flow in flows.values():
        if not isinstance(flow, dict):
            continue
        authorization_url = flow.get("authorizationUrl")
        token_url = flow.get("tokenUrl")
        if isinstance(authorization_url, str):
            candidates.append(authorization_url)
        if isinstance(token_url, str):
            candidates.append(token_url)

    for candidate in candidates:
        base = _realm_base_from_url(candidate)
        if base:
            return base

    raise AuthError(
        "CDA OpenAPI spec did not contain a usable OpenID Connect configuration."
    )


def _well_known_url_from_oidc_base_url(oidc_base_url: str) -> Optional[str]:
    parsed = urllib.parse.urlparse(oidc_base_url)
    marker = "/protocol/openid-connect"
    if marker not in parsed.path:
        return None
    realm_path = parsed.path.split(marker, 1)[0]
    return urllib.parse.urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            f"{realm_path}/.well-known/openid-configuration",
            "",
            "",
            "",
        )
    )


def _oidc_base_url_from_well_known_url(well_known_url: str) -> Optional[str]:
    parsed = urllib.parse.urlparse(well_known_url)
    marker = "/.well-known/openid-configuration"
    if marker not in parsed.path:
        return None
    realm_path = parsed.path.split(marker, 1)[0]
    return urllib.parse.urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            f"{realm_path}/protocol/openid-connect",
            "",
            "",
            "",
        )
    )


def _local_oidc_base_url_candidates(api_root: str, oidc_base_url: str) -> list[str]:
    candidates = [oidc_base_url]
    parsed_root = urllib.parse.urlparse(api_root)
    parsed_oidc = urllib.parse.urlparse(oidc_base_url)

    if not _is_local_host(parsed_root.hostname):
        return candidates
    if _is_local_host(parsed_oidc.hostname):
        return candidates

    ports = []
    for port in (parsed_oidc.port, parsed_root.port, 8082, 8081):
        if port and port not in ports:
            ports.append(port)

    scheme = parsed_root.scheme or parsed_oidc.scheme or "http"
    host = parsed_root.hostname or "localhost"
    for port in ports:
        local_candidate = urllib.parse.urlunparse(
            (
                scheme,
                f"{host}:{port}",
                parsed_oidc.path,
                "",
                "",
                "",
            )
        )
        if local_candidate not in candidates:
            candidates.append(local_candidate)
    return candidates


def _select_reachable_oidc_discovery(
    api_root: str,
    discovery_url: str,
    verify: Optional[str] = None,
) -> Dict[str, Any]:
    import requests

    base_url = _oidc_base_url_from_well_known_url(discovery_url)
    candidates = [discovery_url]
    if base_url:
        candidates = [
            _well_known_url_from_oidc_base_url(candidate) or discovery_url
            for candidate in _local_oidc_base_url_candidates(api_root, base_url)
        ]

    for candidate in candidates:
        try:
            response = requests.get(
                candidate,
                verify=_verify_setting(verify),
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            continue

        if (
            isinstance(payload, dict)
            and payload.get("authorization_endpoint")
            and payload.get("token_endpoint")
        ):
            return payload
    raise AuthError(
        "OpenID discovery document was not reachable from any candidate URL."
    )


def _load_oidc_cache() -> Dict[str, str]:
    cache_file = _oidc_cache_file()
    if not cache_file.exists():
        return {}
    try:
        with cache_file.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    entries = payload.get("entries", {})
    return entries if isinstance(entries, dict) else {}


def _save_oidc_cache(entries: Dict[str, str]) -> None:
    cache_file = _oidc_cache_file()
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with cache_file.open("w", encoding="utf-8") as f:
        json.dump(
            {"saved_at": time.time(), "entries": entries}, f, indent=2, sort_keys=True
        )
        f.write("\n")


def discover_oidc_configuration(
    api_root: str,
    verify: Optional[str] = None,
) -> Dict[str, str]:
    import requests

    normalized_root = _normalize_api_root(api_root)
    cache = _load_oidc_cache()

    try:
        response = requests.get(
            _swagger_docs_url(normalized_root),
            verify=_verify_setting(verify),
            timeout=30,
        )
        response.raise_for_status()
        document = response.json()
        oidc_base_url = _extract_oidc_base_url_from_openapi(document)
        discovery_url = _well_known_url_from_oidc_base_url(oidc_base_url)
        if not discovery_url:
            raise AuthError(
                "Could not derive an OpenID discovery URL from CDA metadata."
            )
        discovery = _select_reachable_oidc_discovery(
            normalized_root,
            discovery_url,
            verify=verify,
        )
        discovered_base_url = _realm_base_from_url(
            str(discovery.get("authorization_endpoint", ""))
        )
        if not discovered_base_url:
            issuer = discovery.get("issuer")
            if isinstance(issuer, str) and issuer:
                discovered_base_url = _oidc_base_url_from_well_known_url(
                    issuer.rstrip("/") + "/.well-known/openid-configuration"
                )
        if not discovered_base_url:
            discovered_base_url = _oidc_base_url_from_well_known_url(discovery_url)
        if not discovered_base_url:
            discovered_base_url = oidc_base_url
        cache[normalized_root] = oidc_base_url
        _save_oidc_cache(cache)
        return {
            "oidc_base_url": discovered_base_url,
            "authorization_endpoint": discovery["authorization_endpoint"],
            "token_endpoint": discovery["token_endpoint"],
        }
    except requests.RequestException as e:
        cached = cache.get(normalized_root)
        if cached:
            return {
                "oidc_base_url": cached,
                "authorization_endpoint": f"{cached}/auth",
                "token_endpoint": f"{cached}/token",
            }
        raise AuthError(
            f"Could not retrieve CDA OpenAPI spec from {_swagger_docs_url(normalized_root)}: {e}"
        ) from e
    except ValueError as e:
        cached = cache.get(normalized_root)
        if cached:
            return {
                "oidc_base_url": cached,
                "authorization_endpoint": f"{cached}/auth",
                "token_endpoint": f"{cached}/token",
            }
        raise AuthError(
            f"CDA OpenAPI spec at {_swagger_docs_url(normalized_root)} was not valid JSON."
        ) from e


def discover_oidc_base_url(
    api_root: str,
    verify: Optional[str] = None,
) -> str:
    return discover_oidc_configuration(api_root=api_root, verify=verify)[
        "oidc_base_url"
    ]


def token_expiry_text(token: Dict[str, Any]) -> Optional[str]:
    expires_at = token.get("expires_at")
    if expires_at is None:
        return None
    try:
        expiry = dt.datetime.fromtimestamp(float(expires_at), tz=dt.timezone.utc)
    except (TypeError, ValueError, OSError):
        return None
    return expiry.isoformat()


def _local_timestamp_text(expires_at: Any) -> Optional[str]:
    try:
        expiry = dt.datetime.fromtimestamp(float(expires_at), tz=dt.timezone.utc)
    except (TypeError, ValueError, OSError):
        return None
    local_expiry = expiry.astimezone()
    hour = local_expiry.hour % 12 or 12
    return (
        f"{local_expiry:%B} {local_expiry.day}, {local_expiry.year} "
        f"at {hour}:{local_expiry:%M %p} {local_expiry:%Z}"
    )


def refresh_token_expiry_text(token: Dict[str, Any]) -> Optional[str]:
    return _local_timestamp_text(token.get("refresh_expires_at"))


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
        "authorization_endpoint": config.authorization_endpoint,
        "token_endpoint": config.token_endpoint,
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


def _select_callback_config(config: OIDCLoginConfig) -> OIDCLoginConfig:
    last_error: Optional[OSError] = None
    for offset in range(PORT_SEARCH_ATTEMPTS):
        candidate = replace(config, redirect_port=config.redirect_port + offset)
        try:
            with _SingleRequestServer(
                (candidate.redirect_host, candidate.redirect_port), _CallbackHandler
            ):
                return candidate
        except OSError as e:
            if not _is_address_in_use_error(e):
                raise CallbackBindError(
                    f"Could not listen on {candidate.redirect_uri}. "
                    "Try a different callback port with --redirect-port, for example "
                    "`cwms-cli login --redirect-port 5555`."
                ) from e
            last_error = e

    final_port = config.redirect_port + PORT_SEARCH_ATTEMPTS - 1
    raise CallbackBindError(
        f"Could not listen on http://{config.redirect_host}:{config.redirect_port} "
        f"through http://{config.redirect_host}:{final_port} because those ports are already in use. "
        "Another `cwms-cli login` instance may still be running. Stop it before continuing, "
        "or try a different callback port with --redirect-port, for example "
        f"`cwms-cli login --redirect-port {final_port + 1}`."
    ) from last_error


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
    if "refresh_expires_at" not in normalized:
        refresh_expires_at = _token_expiry_timestamp(
            normalized.get("refresh_expires_in")
        )
        if refresh_expires_at is not None:
            normalized["refresh_expires_at"] = refresh_expires_at
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
    config = _select_callback_config(config)
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
        "config": config,
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
            authorization_endpoint_url=saved.get("authorization_endpoint"),
            token_endpoint_url=saved.get("token_endpoint"),
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
