from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, Optional, Set
from urllib.parse import urlparse

import click

from cwmscli.utils import colors
from cwmscli.utils.ssl_errors import is_cert_verify_error


@dataclass(frozen=True)
class CdaStackTrace:
    message: Optional[str]
    incident_identifier: Optional[str]
    lines: tuple[str, ...]


class UserFacingError(click.ClickException):
    def __init__(
        self,
        message: str,
        hint: Optional[str] = None,
        *,
        exit_code: int = 1,
    ) -> None:
        self.hint = hint
        self.exit_code = exit_code
        full_message = message
        if hint:
            full_message = f"{full_message}\nHint: {hint}"
        super().__init__(full_message)


def _walk_exception_chain(exc: BaseException) -> Iterable[BaseException]:
    seen: Set[int] = set()
    cur: Optional[BaseException] = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        yield cur
        cur = cur.__cause__ or cur.__context__


def _response_text(response) -> str:
    text = getattr(response, "text", None)
    if text:
        return str(text).strip()

    content = getattr(response, "content", None)
    if isinstance(content, bytes):
        return content.decode("utf-8", errors="replace").strip()
    if content:
        return str(content).strip()
    return ""


def _response_json_field(response, field: str) -> Optional[str]:
    text = _response_text(response)
    if not text:
        return None
    try:
        payload = json.loads(text)
    except Exception:
        return None
    value = payload.get(field)
    if value in (None, ""):
        return None
    return str(value)


def _response_json(response) -> Optional[dict]:
    text = _response_text(response)
    if not text:
        return None
    try:
        payload = json.loads(text)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def cda_stack_trace(exc: BaseException) -> Optional[CdaStackTrace]:
    """Extract a CDA-provided server stack trace from an exception chain."""

    for candidate in _walk_exception_chain(exc):
        response = getattr(candidate, "response", None)
        if response is None:
            continue

        payload = _response_json(response)
        if payload is None:
            continue

        details = payload.get("details")
        if not isinstance(details, dict):
            continue

        stack_trace_lines = details.get("stackTraceLines")
        if not isinstance(stack_trace_lines, list):
            continue

        lines = tuple(str(line) for line in stack_trace_lines if line is not None)
        if not lines:
            continue

        message = payload.get("message")
        incident_identifier = payload.get("incidentIdentifier")
        return CdaStackTrace(
            message=str(message) if message not in (None, "") else None,
            incident_identifier=(
                str(incident_identifier)
                if incident_identifier not in (None, "")
                else None
            ),
            lines=lines,
        )

    return None


def format_cda_stack_trace(stack_trace: CdaStackTrace) -> str:
    """Format a CDA-provided server stack trace for terminal output."""

    heading = colors.err("CDA server stack trace")
    if stack_trace.incident_identifier:
        heading += (
            " "
            + colors.c("(incidentIdentifier: ", "yellow", bright=True)
            + colors.c(stack_trace.incident_identifier, "cyan", bright=True)
            + colors.c(")", "yellow", bright=True)
        )

    output = [heading]
    if stack_trace.message:
        output.append(colors.warn(stack_trace.message))

    for index, line in enumerate(stack_trace.lines):
        stripped = line.lstrip()
        if index == 0 or stripped.startswith("Caused by:"):
            output.append(colors.err(line))
        elif stripped.startswith("at ") or stripped.startswith("..."):
            output.append(colors.c(line, "cyan"))
        else:
            output.append(colors.dim(line))

    return "\n".join(output)


def _trim_message(message: str) -> str:
    message = message.strip()
    if not message:
        return message
    return message if message.endswith(".") else f"{message}."


def _service_name(response) -> str:
    url = str(getattr(response, "url", "") or "")
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if hostname == "usgs.gov" or hostname.endswith(".usgs.gov"):
        return "USGS"
    return "CWMS"


def _friendly_http_error(response) -> Optional[UserFacingError]:
    status = getattr(response, "status_code", None)
    if status is None:
        return None

    api_message = _response_json_field(response, "message")
    incident_id = _response_json_field(response, "incidentIdentifier")
    service = _service_name(response)

    if status == 400:
        return UserFacingError(
            _trim_message(api_message or f"{service} rejected the request"),
            "Check the command arguments and input values, then try again.",
            exit_code=2,
        )
    if status == 401:
        hint = (
            "Your API key or saved login may be missing, invalid, or expired. "
            "Run `cwms-cli login`, or update CDA_API_KEY, --api-key, or "
            "--api-key-loc, then retry."
            if service == "CWMS"
            else (
                "Check whether this USGS endpoint requires credentials and whether "
                "those credentials are current, then retry."
            )
        )
        return UserFacingError(
            _trim_message(
                f"{service} rejected the credentials (HTTP 401)"
                + (f": {api_message}" if api_message else "")
            ),
            hint,
            exit_code=2,
        )
    if status == 403:
        hint = (
            "The credentials were recognized but are not authorized for this office "
            "or operation. Confirm the account's roles and office access, or contact "
            "a CWMS administrator."
            if service == "CWMS"
            else (
                "The credentials were recognized but are not authorized for this "
                "USGS resource. Confirm the account's permissions, then retry."
            )
        )
        return UserFacingError(
            _trim_message(
                f"{service} denied access (HTTP 403)"
                + (f": {api_message}" if api_message else "")
            ),
            hint,
            exit_code=2,
        )
    if status == 408:
        return UserFacingError(
            f"{service} timed out while processing the request (HTTP 408).",
            "Try again. If this persists, reduce the request size or contact the service owner.",
        )
    if status == 404:
        return UserFacingError(
            _trim_message(
                api_message or f"The requested {service} resource was not found"
            ),
            "Verify the identifier, office, and any category or group arguments.",
        )
    if status == 409:
        return UserFacingError(
            _trim_message(
                api_message or f"{service} reported a conflict for this request"
            ),
            "Review overwrite or replace options and confirm the resource state before retrying.",
        )
    if status == 429:
        return UserFacingError(
            _trim_message(api_message or f"{service} rate limited the request"),
            "Wait briefly and retry. If this persists, reduce request frequency.",
        )
    if isinstance(status, int) and status >= 500:
        hint = "Retry later or contact the service owner."
        if incident_id:
            hint += f" Include incidentIdentifier {incident_id}."
        return UserFacingError(
            _trim_message(api_message or f"{service} returned a server error"),
            hint,
        )

    return UserFacingError(
        _trim_message(api_message or f"{service} request failed with HTTP {status}"),
        "Re-run with `CWMS_CLI_DEBUG=1` or `cwms-cli --log-level DEBUG ...etc` for a traceback if you need the raw exception details.",
    )


def _is_requests_exception(exc: BaseException, name: str) -> bool:
    try:
        import requests
    except Exception:
        return False

    exceptions = getattr(requests, "exceptions", None)
    if exceptions is None:
        return False
    return isinstance(exc, getattr(exceptions, name, ()))


def _is_httpx_exception(exc: BaseException, name: str) -> bool:
    try:
        import httpx
    except Exception:
        return False

    return isinstance(exc, getattr(httpx, name, ()))


def is_actionable_service_error(exc: BaseException) -> bool:
    """Return whether the CLI can replace this service failure with useful guidance."""

    return is_cert_verify_error(exc) or to_user_facing_error(exc) is not None


def is_fatal_service_error(exc: BaseException) -> bool:
    """Return whether a batch operation should stop instead of logging and continuing."""

    if is_cert_verify_error(exc):
        return True

    for candidate in _walk_exception_chain(exc):
        response = getattr(candidate, "response", None)
        status = (
            getattr(response, "status_code", None) if response is not None else None
        )
        if status in {401, 403, 407, 408, 425, 429}:
            return True
        if isinstance(status, int) and status >= 500:
            return True
        if any(
            _is_requests_exception(candidate, name)
            for name in ("Timeout", "ConnectionError", "ProxyError")
        ) or any(
            _is_httpx_exception(candidate, name)
            for name in ("TimeoutException", "NetworkError", "ProxyError")
        ):
            return True

    return False


def to_user_facing_error(exc: BaseException) -> Optional[UserFacingError]:
    for candidate in _walk_exception_chain(exc):
        response = getattr(candidate, "response", None)
        if response is not None:
            friendly = _friendly_http_error(response)
            if friendly is not None:
                return friendly

        if _is_requests_exception(candidate, "Timeout") or _is_httpx_exception(
            candidate, "TimeoutException"
        ):
            return UserFacingError(
                "Timed out while waiting for the remote service to respond.",
                "Confirm the service is reachable and try again.",
            )

        if _is_requests_exception(candidate, "ConnectionError") or _is_httpx_exception(
            candidate, "NetworkError"
        ):
            return UserFacingError(
                "Could not reach the remote service.",
                "Check network connectivity and service availability. For CWMS requests, also check --api-root.",
            )

        if any(
            _is_requests_exception(candidate, name)
            for name in ("InvalidURL", "MissingSchema")
        ) or _is_httpx_exception(candidate, "InvalidURL"):
            return UserFacingError(
                "The service URL is invalid.",
                "Check --api-root and include the URL scheme, such as https://.",
                exit_code=2,
            )

        if _is_requests_exception(candidate, "TooManyRedirects") or _is_httpx_exception(
            candidate, "TooManyRedirects"
        ):
            return UserFacingError(
                "The service redirected the request too many times.",
                "Check --api-root and use the direct CDA endpoint URL.",
                exit_code=2,
            )

    return None
