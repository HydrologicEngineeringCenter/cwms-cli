import json
import logging
import sys

import click
import pytest

import cwmscli.__main__ as cli_main
from cwmscli.utils.links import BUG_REPORT_URL


class _FakeResponse:
    def __init__(
        self,
        status_code,
        message,
        *,
        reason="",
        url="https://example.test/cwms-data/resource",
        incident=None,
        stack_trace_lines=None,
    ):
        self.status_code = status_code
        self.reason = reason
        self.url = url
        payload = {"message": message}
        if incident is not None:
            payload["incidentIdentifier"] = incident
        if stack_trace_lines is not None:
            payload["details"] = {"stackTraceLines": stack_trace_lines}
        self.text = json.dumps(payload)
        self.content = self.text.encode("utf-8")


def test_main_formats_api_404_without_traceback(monkeypatch, capsys):
    from cwms.api import ApiError

    def fake_cli(*args, **kwargs):
        raise ApiError(
            _FakeResponse(
                404,
                "Unable to find group based on parameters given",
                reason="Not Found",
            )
        )

    monkeypatch.setattr(cli_main, "cli", fake_cli)
    monkeypatch.setattr(sys, "argv", ["cwms-cli", "dummy"])
    monkeypatch.delenv("CWMS_CLI_DEBUG", raising=False)

    with pytest.raises(SystemExit) as exc:
        cli_main.main()

    captured = capsys.readouterr()
    assert exc.value.code == 1
    assert "Unable to find group based on parameters given." in captured.err
    assert (
        "Hint: Verify the identifier, office, and any category or group arguments."
        in captured.err
    )
    assert "Traceback" not in captured.err


def test_main_formats_connection_error_without_traceback(monkeypatch, capsys):
    import requests

    def fake_cli(*args, **kwargs):
        raise requests.exceptions.ConnectionError("connection refused")

    monkeypatch.setattr(cli_main, "cli", fake_cli)
    monkeypatch.setattr(sys, "argv", ["cwms-cli", "dummy"])
    monkeypatch.delenv("CWMS_CLI_DEBUG", raising=False)

    with pytest.raises(SystemExit) as exc:
        cli_main.main()

    captured = capsys.readouterr()
    assert exc.value.code == 1
    assert "Could not reach the CWMS API endpoint." in captured.err
    assert "Traceback" not in captured.err


def test_main_formats_auth_error_without_traceback(monkeypatch, capsys):
    from cwms.api import ApiError

    def fake_cli(*args, **kwargs):
        raise ApiError(
            _FakeResponse(
                401,
                "API key is invalid",
                reason="Unauthorized",
            )
        )

    monkeypatch.setattr(cli_main, "cli", fake_cli)
    monkeypatch.setattr(sys, "argv", ["cwms-cli", "dummy"])
    monkeypatch.delenv("CWMS_CLI_DEBUG", raising=False)

    with pytest.raises(SystemExit) as exc:
        cli_main.main()

    captured = capsys.readouterr()
    assert exc.value.code == 2
    assert "API key is invalid." in captured.err
    assert (
        "Check CDA_API_KEY, --api-key, and whether the account can access the requested office."
        in captured.err
    )
    assert "Traceback" not in captured.err


def test_main_formats_server_error_with_incident_identifier(monkeypatch, capsys):
    from cwms.api import ApiError

    def fake_cli(*args, **kwargs):
        raise ApiError(
            _FakeResponse(
                503,
                "Service temporarily unavailable",
                reason="Service Unavailable",
                incident="12345",
            )
        )

    monkeypatch.setattr(cli_main, "cli", fake_cli)
    monkeypatch.setattr(sys, "argv", ["cwms-cli", "dummy"])
    monkeypatch.delenv("CWMS_CLI_DEBUG", raising=False)

    with pytest.raises(SystemExit) as exc:
        cli_main.main()

    captured = capsys.readouterr()
    assert exc.value.code == 1
    assert "Service temporarily unavailable." in captured.err
    assert "incidentIdentifier 12345" in captured.err


def test_main_preserves_raw_exception_and_prints_report_link(monkeypatch, capsys):
    def fake_cli(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli_main, "cli", fake_cli)
    monkeypatch.setattr(sys, "argv", ["cwms-cli", "dummy"])
    monkeypatch.setenv("CWMS_CLI_DEBUG", "1")

    with pytest.raises(RuntimeError, match="boom"):
        cli_main.main()

    assert f"Unexpected error. Report it at {BUG_REPORT_URL}" in capsys.readouterr().err


def test_main_formats_cda_stack_trace_when_debug_env_enabled(monkeypatch, capsys):
    from cwms.api import ApiError

    def fake_cli(*args, **kwargs):
        raise ApiError(
            _FakeResponse(
                400,
                "Text 'not-a-date' could not be parsed at index 0",
                reason="Bad Request",
                incident="trace-123",
                stack_trace_lines=[
                    "java.time.format.DateTimeParseException: invalid date",
                    "\tat cwms.cda.helpers.DateUtils.parseUserDate(DateUtils.java:91)",
                ],
            )
        )

    monkeypatch.setattr(cli_main, "cli", fake_cli)
    monkeypatch.setattr(sys, "argv", ["cwms-cli", "dummy"])
    monkeypatch.setenv("CWMS_CLI_DEBUG", "1")

    with pytest.raises(SystemExit) as exc:
        cli_main.main()

    captured = capsys.readouterr()
    assert exc.value.code == 1
    assert "CDA server stack trace" in captured.err
    assert "incidentIdentifier: trace-123" in captured.err
    assert "java.time.format.DateTimeParseException" in captured.err
    assert "DateUtils.parseUserDate" in captured.err
    assert "Traceback (most recent call last)" not in captured.err


def test_main_log_level_debug_formats_cda_stack_trace(monkeypatch, capsys):
    from cwms.api import ApiError

    previous_level = logging.getLogger().level

    def fake_cli(*args, **kwargs):
        logging.getLogger().setLevel(logging.DEBUG)
        raise ApiError(
            _FakeResponse(
                500,
                "System Error",
                incident="trace-456",
                stack_trace_lines=["java.lang.RuntimeException: boom"],
            )
        )

    monkeypatch.setattr(cli_main, "cli", fake_cli)
    monkeypatch.setattr(sys, "argv", ["cwms-cli", "--log-level", "DEBUG", "dummy"])
    monkeypatch.delenv("CWMS_CLI_DEBUG", raising=False)

    try:
        with pytest.raises(SystemExit) as exc:
            cli_main.main()
    finally:
        logging.getLogger().setLevel(previous_level)

    captured = capsys.readouterr()
    assert exc.value.code == 1
    assert "CDA server stack trace" in captured.err
    assert "java.lang.RuntimeException: boom" in captured.err


def test_main_debug_finds_cda_stack_behind_click_exception(monkeypatch, capsys):
    from cwms.api import ApiError

    def fake_cli(*args, **kwargs):
        try:
            raise ApiError(
                _FakeResponse(
                    500,
                    "System Error",
                    incident="trace-789",
                    stack_trace_lines=["java.lang.NullPointerException: missing"],
                )
            )
        except ApiError:
            raise click.ClickException("Friendly command error") from None

    monkeypatch.setattr(cli_main, "cli", fake_cli)
    monkeypatch.setattr(sys, "argv", ["cwms-cli", "dummy"])
    monkeypatch.setenv("CWMS_CLI_DEBUG", "1")

    with pytest.raises(SystemExit) as exc:
        cli_main.main()

    captured = capsys.readouterr()
    assert exc.value.code == 1
    assert "CDA server stack trace" in captured.err
    assert "incidentIdentifier: trace-789" in captured.err
    assert "java.lang.NullPointerException: missing" in captured.err
    assert "Friendly command error" not in captured.err
