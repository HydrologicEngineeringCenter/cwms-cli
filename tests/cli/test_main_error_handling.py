import json
import sys

import pytest

import cwmscli.__main__ as cli_main


class _FakeResponse:
    def __init__(
        self,
        status_code,
        message,
        *,
        reason="",
        url="https://example.test/cwms-data/resource",
        incident=None
    ):
        self.status_code = status_code
        self.reason = reason
        self.url = url
        payload = {"message": message}
        if incident is not None:
            payload["incidentIdentifier"] = incident
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


def test_main_preserves_raw_exception_when_debug_enabled(monkeypatch):
    def fake_cli(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli_main, "cli", fake_cli)
    monkeypatch.setattr(sys, "argv", ["cwms-cli", "dummy"])
    monkeypatch.setenv("CWMS_CLI_DEBUG", "1")

    with pytest.raises(RuntimeError, match="boom"):
        cli_main.main()
