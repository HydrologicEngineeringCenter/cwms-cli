import sys
import types

import pandas as pd
from click.testing import CliRunner

import cwmscli.utils.deps as deps
from cwmscli.__main__ import cli
from cwmscli.usgs.getusgs_cda import get_CMWS_TS_Loc_Data


def test_get_cwms_ts_loc_data_errors_when_timeseries_group_is_empty(
    monkeypatch, caplog
):
    class FakeGroup:
        df = pd.DataFrame()

    class FakeCwms:
        @staticmethod
        def get_timeseries_group(**kwargs):
            return FakeGroup()

    monkeypatch.setattr("cwmscli.usgs.getusgs_cda.cwms", FakeCwms)

    try:
        get_CMWS_TS_Loc_Data("SWT")
        raise AssertionError("Expected SystemExit")
    except SystemExit as exc:
        assert exc.code == 1
    assert (
        "No time series are defined in Data Acquisition / USGS TS Data Acquisition for office SWT."
        in caplog.text
    )


def test_get_cwms_ts_loc_data_errors_when_api_root_returns_html(monkeypatch, caplog):
    class FakeGroup:
        json = "<!doctype html><html><body>water data app</body></html>"

        @property
        def df(self):
            raise AttributeError("'str' object has no attribute 'keys'")

    class FakeCwms:
        @staticmethod
        def get_timeseries_group(**kwargs):
            return FakeGroup()

    monkeypatch.setattr("cwmscli.usgs.getusgs_cda.cwms", FakeCwms)

    try:
        get_CMWS_TS_Loc_Data("SWT")
        raise AssertionError("Expected SystemExit")
    except SystemExit as exc:
        assert exc.code == 1
    assert "returned an HTML page" in caplog.text
    assert "/cwms-data" in caplog.text


def test_get_cwms_ts_loc_data_errors_when_alias_group_is_empty(monkeypatch, caplog):
    class FakeTimeseriesGroup:
        df = pd.DataFrame(
            [
                {
                    "timeseries-id": "TEST.Flow.Inst.0.0.raw",
                    "office-id": "SWT",
                }
            ]
        )

    class FakeLocationGroup:
        df = pd.DataFrame(columns=["location-id", "office-id", "alias-id"])

    class FakeCwms:
        @staticmethod
        def get_timeseries_group(**kwargs):
            return FakeTimeseriesGroup()

        @staticmethod
        def get_location_group(**kwargs):
            return FakeLocationGroup()

    monkeypatch.setattr("cwmscli.usgs.getusgs_cda.cwms", FakeCwms)

    try:
        get_CMWS_TS_Loc_Data("SWT")
        raise AssertionError("Expected SystemExit")
    except SystemExit as exc:
        assert exc.code == 1
    assert (
        "No USGS location aliases are defined in Agency Aliases / USGS Station Number for office SWT."
        in caplog.text
    )


def test_usgs_timeseries_command_shows_friendly_message_for_missing_configuration(
    monkeypatch,
):
    fake_module = types.ModuleType("cwmscli.usgs.getusgs_cda")

    def fake_getusgs_cda(**kwargs):
        raise SystemExit(1)

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
            "SWT",
            "-d",
            "1",
            "-a",
            "https://example.test/cda/",
            "-k",
            "test-api-key",
        ],
    )

    assert result.exit_code == 1
    assert "Traceback" not in result.output
