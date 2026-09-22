import importlib
import sys
import types

import pandas as pd
import pytest
import requests
from click.testing import CliRunner

import cwmscli.utils.deps as deps
from cwmscli.__main__ import cli
from cwmscli.usgs.getusgs_cda import get_CMWS_TS_Loc_Data


def _load_measurements_module(monkeypatch):
    dataretrieval = types.ModuleType("dataretrieval")
    dataretrieval.nwis = types.SimpleNamespace()
    monkeypatch.setitem(sys.modules, "dataretrieval", dataretrieval)
    monkeypatch.delitem(
        sys.modules, "cwmscli.usgs.getusgs_measurements_cda", raising=False
    )
    return importlib.import_module("cwmscli.usgs.getusgs_measurements_cda")


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
    assert "returned an unexpected response" in caplog.text
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
    monkeypatch.setattr(
        deps.importlib.metadata,
        "version",
        lambda name: "1.0.7" if name == "cwms-python" else "999.0.0",
    )

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


def test_usgs_measurements_propagates_cwms_401(monkeypatch):
    from cwms.api import ApiError

    measurements = _load_measurements_module(monkeypatch)

    class FakeResponse:
        status_code = 401
        reason = "Unauthorized"
        url = "https://example.test/cwms-data/location/group"
        text = '{"message":"Invalid User"}'
        content = text.encode("utf-8")

    def fail_group_lookup(**kwargs):
        raise ApiError(FakeResponse())

    monkeypatch.setattr(measurements, "init_cwms_session", lambda *args, **kwargs: None)
    monkeypatch.setattr(measurements.cwms, "get_location_group", fail_group_lookup)

    with pytest.raises(ApiError):
        measurements.getusgs_measurement_cda(
            api_root="https://example.test/cwms-data",
            office_id="SWT",
            api_key="expired",
        )


def test_usgs_measurements_propagates_ssl_error(monkeypatch):
    measurements = _load_measurements_module(monkeypatch)

    def fail_usgs_request(**kwargs):
        raise requests.exceptions.SSLError(
            "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed"
        )

    monkeypatch.setattr(
        measurements.nwis,
        "get_discharge_measurements",
        fail_usgs_request,
        raising=False,
    )

    with pytest.raises(requests.exceptions.SSLError):
        measurements.realtime_mode(1, 1, pd.DataFrame())
