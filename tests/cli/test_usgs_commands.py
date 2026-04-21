import sys
import types

from click.testing import CliRunner

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


def test_usgs_timeseries_backfill_version_passed_through(monkeypatch):
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
            "-bv",
            "Rev-USGS",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["backfill_version"] == "Rev-USGS"


def test_usgs_timeseries_v2_backfill_version_passed_through(monkeypatch):
    captured = {}
    fake_module = types.ModuleType("cwmscli.usgs.getusgs_cda")

    def fake_getusgs_cda_ogc(**kwargs):
        captured.update(kwargs)

    fake_module.getusgs_cda_ogc = fake_getusgs_cda_ogc

    monkeypatch.setitem(sys.modules, "cwmscli.usgs.getusgs_cda", fake_module)
    monkeypatch.setattr(deps.importlib, "import_module", lambda name: object())
    monkeypatch.setattr(deps.importlib.metadata, "version", lambda name: "999.0.0")

    result = CliRunner().invoke(
        cli,
        [
            "usgs",
            "timeseries-v2",
            "-o",
            "spl",
            "-d",
            "30",
            "-a",
            "https://example.test/cda/",
            "-k",
            "test-api-key",
            "-bv",
            "Rev-USGS",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["backfill_version"] == "Rev-USGS"
