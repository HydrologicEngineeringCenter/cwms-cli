import sys
import types

from click.testing import CliRunner

import cwmscli.usgs as usgs_cli
import cwmscli.utils.deps as deps
from cwmscli.__main__ import cli


def test_usgs_timeseries_backfill_preserves_internal_spaces(monkeypatch):
    captured = {}
    fake_module = types.ModuleType("cwmscli.usgs.getusgs_cda")

    def fake_getusgs_cda(**kwargs):
        captured.update(kwargs)

    fake_module.getusgs_cda = fake_getusgs_cda

    monkeypatch.setitem(sys.modules, "cwmscli.usgs.getusgs_cda", fake_module)
    monkeypatch.setattr(deps.importlib, "import_module", lambda name: object())
    monkeypatch.setattr(deps.importlib.metadata, "version", lambda name: "999.0.0")

    result = CliRunner().invoke(
        cli,
        [
            "usgs",
            "timeseries",
            "-o",
            "spl",
            "-d",
            "30",
            "-a",
            "https://example.test/cda/",
            "-k",
            "test-api-key",
            "-b",
            " Prado DS-SAR.Flow.Inst.0.0.usgs-raw, Other Location.Stage.Inst.0.0.usgs-raw ",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["office_id"] == "SPL"
    assert captured["backfill_tsids"] == [
        "Prado DS-SAR.Flow.Inst.0.0.usgs-raw",
        "Other Location.Stage.Inst.0.0.usgs-raw",
    ]


def test_usgs_ratings_dry_run_is_forwarded(monkeypatch):
    captured = {}
    fake_module = types.ModuleType("cwmscli.usgs.getUSGS_ratings_cda")

    def fake_getusgs_rating_cda(**kwargs):
        captured.update(kwargs)

    fake_module.getusgs_rating_cda = fake_getusgs_rating_cda

    monkeypatch.setitem(sys.modules, "cwmscli.usgs.getUSGS_ratings_cda", fake_module)
    monkeypatch.setattr(deps.importlib, "import_module", lambda name: object())
    monkeypatch.setattr(deps.importlib.metadata, "version", lambda name: "999.0.0")

    result = CliRunner().invoke(
        cli,
        [
            "usgs",
            "ratings",
            "-o",
            "spl",
            "-a",
            "https://example.test/cda/",
            "-k",
            "test-api-key",
            "--usgs-api-key",
            "test-usgs-api-key",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["office_id"] == "SPL"
    assert captured["usgs_api_key"] == "test-usgs-api-key"
    assert captured["dry_run"] is True


def test_usgs_ratings_reads_usgs_api_key_from_environment(monkeypatch):
    captured = {}
    fake_module = types.ModuleType("cwmscli.usgs.getUSGS_ratings_cda")

    def fake_getusgs_rating_cda(**kwargs):
        captured.update(kwargs)

    fake_module.getusgs_rating_cda = fake_getusgs_rating_cda

    monkeypatch.setitem(sys.modules, "cwmscli.usgs.getUSGS_ratings_cda", fake_module)
    monkeypatch.setattr(deps.importlib, "import_module", lambda name: object())
    monkeypatch.setattr(deps.importlib.metadata, "version", lambda name: "999.0.0")
    monkeypatch.delenv("API_USGS_PAT", raising=False)
    monkeypatch.setenv("API_USGS_PAT", "environment-usgs-key")

    result = CliRunner().invoke(
        cli,
        [
            "usgs",
            "ratings",
            "-o",
            "spl",
            "-a",
            "https://example.test/cda/",
            "-k",
            "test-api-key",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["usgs_api_key"] == "environment-usgs-key"


def test_usgs_ratings_warns_and_runs_without_usgs_api_key(monkeypatch):
    captured = {}
    warning_messages = []
    fake_module = types.ModuleType("cwmscli.usgs.getUSGS_ratings_cda")

    def fake_getusgs_rating_cda(**kwargs):
        captured.update(kwargs)

    fake_module.getusgs_rating_cda = fake_getusgs_rating_cda

    monkeypatch.setitem(sys.modules, "cwmscli.usgs.getUSGS_ratings_cda", fake_module)
    monkeypatch.setattr(deps.importlib, "import_module", lambda name: object())
    monkeypatch.setattr(deps.importlib.metadata, "version", lambda name: "999.0.0")
    monkeypatch.delenv("API_USGS_PAT", raising=False)
    monkeypatch.setattr(
        usgs_cli.logging,
        "warning",
        lambda message, *args: warning_messages.append(
            message % args if args else message
        ),
    )

    result = CliRunner().invoke(
        cli,
        [
            "usgs",
            "ratings",
            "-o",
            "spl",
            "-a",
            "https://example.test/cda/",
            "-k",
            "test-api-key",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["usgs_api_key"] is None
    assert captured["dry_run"] is True
    assert any(
        "https://api.waterdata.usgs.gov/signup/" in message
        for message in warning_messages
    )
