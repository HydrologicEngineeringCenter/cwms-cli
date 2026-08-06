from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, Optional, Set

import click

from cwmscli.utils import colors


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


def _friendly_http_error(response) -> Optional[UserFacingError]:
    status = getattr(response, "status_code", None)
    if status is None:
        return None

    api_message = _response_json_field(response, "message")
    incident_id = _response_json_field(response, "incidentIdentifier")

    if status == 400:
        return UserFacingError(
            _trim_message(api_message or "CWMS rejected the request"),
            "Check the command arguments and input values, then try again.",
            exit_code=2,
        )
    if status in (401, 403):
        return UserFacingError(
            _trim_message(api_message or "Authentication failed while calling CWMS"),
            "Check CDA_API_KEY, --api-key, and whether the account can access the requested office.",
            exit_code=2,
        )
    if status == 404:
        return UserFacingError(
            _trim_message(api_message or "Requested CWMS resource was not found"),
            "Verify the identifier, office, and any category or group arguments.",
        )
    if status == 409:
        return UserFacingError(
            _trim_message(api_message or "CWMS reported a conflict for this request"),
            "Review overwrite or replace options and confirm the resource state before retrying.",
        )
    if status == 429:
        return UserFacingError(
            _trim_message(api_message or "CWMS rate limited the request"),
            "Wait briefly and retry. If this persists, reduce request frequency.",
        )
    if isinstance(status, int) and status >= 500:
        hint = "Retry later or contact the service owner."
        if incident_id:
            hint += f" Include incidentIdentifier {incident_id}."
        return UserFacingError(
            _trim_message(api_message or "CWMS returned a server error"),
            hint,
        )

    return UserFacingError(
        _trim_message(api_message or f"CWMS request failed with HTTP {status}"),
        "Re-run with `CWMS_CLI_DEBUG=1` or `cwms-cli --log-level DEBUG ...etc` for a traceback if you need the raw exception details.",
    )


def _is_requests_exception(exc: BaseException, name: str) -> bool:
    try:
        import requests
    except Exception:
        return False

    return isinstance(exc, getattr(requests.exceptions, name, ()))


def to_user_facing_error(exc: BaseException) -> Optional[UserFacingError]:
    for candidate in _walk_exception_chain(exc):
        response = getattr(candidate, "response", None)
        if response is not None:
            friendly = _friendly_http_error(response)
            if friendly is not None:
                return friendly

        if _is_requests_exception(candidate, "Timeout"):
            return UserFacingError(
                "Timed out while waiting for CWMS to respond.",
                "Confirm the service is reachable and try again.",
            )

        if _is_requests_exception(candidate, "ConnectionError"):
            return UserFacingError(
                "Could not reach the CWMS API endpoint.",
                "Check --api-root, network connectivity, and whether the server is running.",
            )

    return None
