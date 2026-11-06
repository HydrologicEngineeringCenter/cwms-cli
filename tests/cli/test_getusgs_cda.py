import logging
from datetime import datetime, timedelta
from unittest.mock import Mock

import pandas as pd
import pytest

import cwmscli.usgs.getusgs_cda as getusgs_cda_module


@pytest.fixture
def new_api_usgs_ts_df():
    """CWMS USGS acquisition configuration using null and UUID aliases."""

    return pd.DataFrame(
        {
            "timeseries-id": [
                "LOC1.Flow.Inst.~15Minutes.0.Raw-USGS",
                "LOC2.Stage.Inst.~15Minutes.0.Raw-USGS",
            ],
            "office-id": ["MVP", "MVP"],
            "USGS_St_Num": ["04213152", "04213160"],
            "USGS_PARAMETER": ["00060", "00065"],
            # Null means station + parameter lookup.
            # UUID means explicit new-USGS time_series_id lookup.
            "USGS_Time_Series_ID": [
                pd.NA,
                "f38a57ccac5a426e8388b8507fa9bbce",
            ],
        }
    )


@pytest.fixture
def new_api_usgs_data_df():
    """Long-format sample response from new USGS continuous endpoint."""

    return pd.DataFrame(
        {
            "time_series_id": [
                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "f38a57ccac5a426e8388b8507fa9bbce",
                "f38a57ccac5a426e8388b8507fa9bbce",
            ],
            "monitoring_location_id": [
                "USGS-04213152",
                "USGS-04213152",
                "USGS-04213160",
                "USGS-04213160",
            ],
            "parameter_code": [
                "00060",
                "00060",
                "00065",
                "00065",
            ],
            "statistic_id": [
                "00011",
                "00011",
                "00011",
                "00011",
            ],
            "time": pd.to_datetime(
                [
                    "2026-11-01T00:00:00Z",
                    "2026-11-01T00:15:00Z",
                    "2026-11-01T00:00:00Z",
                    "2026-11-01T00:15:00Z",
                ],
                utc=True,
            ),
            "value": [
                100.0,
                110.0,
                5.0,
                5.2,
            ],
            "unit_of_measure": [
                "ft^3/s",
                "ft^3/s",
                "ft",
                "ft",
            ],
            "approval_status": [
                "Provisional",
                "Provisional",
                "Approved",
                "Approved",
            ],
            "qualifier": [
                None,
                None,
                None,
                None,
            ],
        }
    )


@pytest.fixture
def mock_cwms_response_with_df():
    """Mock CWMS response object with a DataFrame property."""

    response = Mock()
    response.json = None
    return response


class TestGetUSGSParams:
    def test_returns_dataframe(self):
        result = getusgs_cda_module.get_USGS_params()

        assert isinstance(result, pd.DataFrame)

    def test_has_expected_columns(self):
        result = getusgs_cda_module.get_USGS_params()

        expected_columns = [
            "USGS_PARAMETER",
            "USGS_Alias",
            "CWMS_FACTOR",
            "CWMS_UNIT",
            "CWMS_TYPE",
        ]

        for column in expected_columns:
            assert column in result.columns

        assert result.index.name == "CWMS_PARAMETER"

    def test_contains_common_parameters(self):
        result = getusgs_cda_module.get_USGS_params()

        assert "Flow" in result.index
        assert "Stage" in result.index
        assert "Temp-Water" in result.index
        assert "Cond" in result.index

    def test_flow_parameter_values(self):
        result = getusgs_cda_module.get_USGS_params()
        flow_row = result.loc["Flow"]

        assert flow_row["USGS_PARAMETER"] == "00060"
        assert flow_row["CWMS_FACTOR"] == 1
        assert flow_row["CWMS_UNIT"] == "cfs"
        assert flow_row["CWMS_TYPE"] == "Inst"


class TestLogErrorAndExit:
    def test_raises_systemexit(self):
        with pytest.raises(SystemExit) as exc_info:
            getusgs_cda_module._log_error_and_exit("Test error")

        assert exc_info.value.code == 1

    def test_uses_custom_exit_code(self):
        with pytest.raises(SystemExit) as exc_info:
            getusgs_cda_module._log_error_and_exit(
                "Test error",
                exit_code=2,
            )

        assert exc_info.value.code == 2

    def test_logs_error(self, caplog):
        with pytest.raises(SystemExit):
            with caplog.at_level(logging.ERROR):
                getusgs_cda_module._log_error_and_exit(
                    "Test error message"
                )

        assert "Test error message" in caplog.text

    def test_logs_hint(self, caplog):
        with pytest.raises(SystemExit):
            with caplog.at_level(logging.ERROR):
                getusgs_cda_module._log_error_and_exit(
                    "Test error",
                    hint="Test hint",
                )

        assert "Test hint" in caplog.text


class TestRequireGroupDataframe:
    def test_returns_dataframe_when_present(self, mock_cwms_response_with_df):
        expected_df = pd.DataFrame({"column": [1, 2, 3]})
        mock_cwms_response_with_df.df = expected_df

        result = getusgs_cda_module._require_group_dataframe(
            mock_cwms_response_with_df,
            resource_name="test resource",
            office="MVP",
        )

        pd.testing.assert_frame_equal(result, expected_df)

    def test_raises_when_df_is_none(self, mock_cwms_response_with_df):
        mock_cwms_response_with_df.df = None

        with pytest.raises(SystemExit):
            getusgs_cda_module._require_group_dataframe(
                mock_cwms_response_with_df,
                resource_name="test resource",
                office="MVP",
            )

    def test_returns_empty_dataframe_as_is(self, mock_cwms_response_with_df):
        mock_cwms_response_with_df.df = pd.DataFrame()

        result = getusgs_cda_module._require_group_dataframe(
            mock_cwms_response_with_df,
            resource_name="test resource",
            office="MVP",
        )

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_raises_when_df_attribute_missing_with_string_payload(self):
        response = Mock(spec=[])
        response.json = "CDA error response"

        with pytest.raises(SystemExit):
            getusgs_cda_module._require_group_dataframe(
                response,
                resource_name="test resource",
                office="MVP",
            )

    def test_reraises_attribute_error_for_non_string_payload(self):
        response = Mock(spec=[])

        with pytest.raises(AttributeError):
            getusgs_cda_module._require_group_dataframe(
                response,
                resource_name="test resource",
                office="MVP",
            )


class TestGetCMWSTSLocData:
    def test_combines_timeseries_and_location_data(self, monkeypatch):
        ts_response = Mock()
        ts_response.df = pd.DataFrame(
            {
                "office-id": ["MVP", "MVP"],
                "timeseries-id": [
                    "LOC1.Flow.Inst.~15Minutes.0.Raw-USGS",
                    "LOC2.Stage.Inst.~15Minutes.0.Raw-USGS",
                ],
                "alias-id": [
                    pd.NA,
                    "f38a57ccac5a426e8388b8507fa9bbce",
                ],
                "attribute": [0, 0],
            }
        )

        loc_response = Mock()
        loc_response.df = pd.DataFrame(
            {
                "location-id": ["LOC1", "LOC2"],
                "office-id": ["MVP", "MVP"],
                "alias-id": ["04213152", "04213160"],
                "attribute": [0, 0],
            }
        )

        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "get_timeseries_group",
            lambda **kwargs: ts_response,
        )

        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "get_location_group",
            lambda **kwargs: loc_response,
        )

        result = getusgs_cda_module.get_CMWS_TS_Loc_Data("MVP")

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert "USGS_St_Num" in result.columns
        assert "USGS_PARAMETER" in result.columns
        assert "USGS_Time_Series_ID" in result.columns

        assert set(result["USGS_St_Num"]) == {
            "04213152",
            "04213160",
        }

        assert set(result["USGS_PARAMETER"]) == {
            "00060",
            "00065",
        }

    def test_normalizes_blank_alias_to_null(self, monkeypatch):
        ts_response = Mock()
        ts_response.df = pd.DataFrame(
            {
                "office-id": ["MVP"],
                "timeseries-id": [
                    "LOC1.Flow.Inst.~15Minutes.0.Raw-USGS"
                ],
                "alias-id": ["   "],
                "attribute": [0],
            }
        )

        loc_response = Mock()
        loc_response.df = pd.DataFrame(
            {
                "location-id": ["LOC1"],
                "office-id": ["MVP"],
                "alias-id": ["04213152"],
                "attribute": [0],
            }
        )

        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "get_timeseries_group",
            lambda **kwargs: ts_response,
        )

        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "get_location_group",
            lambda **kwargs: loc_response,
        )

        result = getusgs_cda_module.get_CMWS_TS_Loc_Data("MVP")

        assert "USGS_Time_Series_ID" in result.columns
        assert "USGS_Method_TS" not in result.columns
        assert pd.isna(result.iloc[0]["USGS_Time_Series_ID"])

    def test_filters_timeseries_by_office(self, monkeypatch):
        ts_response = Mock()
        ts_response.df = pd.DataFrame(
            {
                "office-id": ["MVP", "LRL"],
                "timeseries-id": [
                    "LOC1.Flow.Inst.~15Minutes.0.Raw-USGS",
                    "LOC2.Stage.Inst.~15Minutes.0.Raw-USGS",
                ],
                "alias-id": [pd.NA, pd.NA],
                "attribute": [0, 0],
            }
        )

        loc_response = Mock()
        loc_response.df = pd.DataFrame(
            {
                "location-id": ["LOC1", "LOC2"],
                "office-id": ["MVP", "LRL"],
                "alias-id": ["04213152", "04213160"],
                "attribute": [0, 0],
            }
        )

        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "get_timeseries_group",
            lambda **kwargs: ts_response,
        )

        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "get_location_group",
            lambda **kwargs: loc_response,
        )

        result = getusgs_cda_module.get_CMWS_TS_Loc_Data("MVP")

        assert len(result) == 1
        assert (result["office-id"] == "MVP").all()

    def test_raises_when_timeseries_group_empty(self, monkeypatch):
        ts_response = Mock()
        ts_response.df = pd.DataFrame()

        loc_response = Mock()
        loc_response.df = pd.DataFrame(
            {
                "location-id": ["LOC1"],
                "office-id": ["MVP"],
                "alias-id": ["04213152"],
                "attribute": [0],
            }
        )

        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "get_timeseries_group",
            lambda **kwargs: ts_response,
        )

        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "get_location_group",
            lambda **kwargs: loc_response,
        )

        with pytest.raises(SystemExit):
            getusgs_cda_module.get_CMWS_TS_Loc_Data("MVP")

    def test_raises_when_no_usgs_location_aliases(self, monkeypatch):
        ts_response = Mock()
        ts_response.df = pd.DataFrame(
            {
                "office-id": ["MVP"],
                "timeseries-id": [
                    "LOC1.Flow.Inst.~15Minutes.0.Raw-USGS"
                ],
                "alias-id": [pd.NA],
                "attribute": [0],
            }
        )

        loc_response = Mock()
        loc_response.df = pd.DataFrame(
            {
                "location-id": ["LOC1"],
                "office-id": ["MVP"],
                "alias-id": [pd.NA],
                "attribute": [0],
            }
        )

        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "get_timeseries_group",
            lambda **kwargs: ts_response,
        )

        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "get_location_group",
            lambda **kwargs: loc_response,
        )

        with pytest.raises(SystemExit):
            getusgs_cda_module.get_CMWS_TS_Loc_Data("MVP")


class TestNormalizeUSGSUnit:
    def test_normalizes_cubic_feet_per_second(self):
        assert (
            getusgs_cda_module._normalize_usgs_unit("ft^3/s")
            == "ft3/s"
        )

    def test_normalizes_superscript_cubic_feet_per_second(self):
        assert (
            getusgs_cda_module._normalize_usgs_unit("ft³/s")
            == "ft3/s"
        )

    def test_preserves_stage_unit(self):
        assert getusgs_cda_module._normalize_usgs_unit("ft") == "ft"

    def test_returns_none_for_none(self):
        assert getusgs_cda_module._normalize_usgs_unit(None) is None


class TestGetContinuousData:
    def test_requests_expected_properties(self, monkeypatch):
        captured = {}

        api_data = pd.DataFrame(
            {
                "time_series_id": [
                    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                ],
                "monitoring_location_id": [
                    "USGS-04213152"
                ],
                "parameter_code": ["00060"],
                "statistic_id": ["00011"],
                "time": ["2026-11-01T00:00:00Z"],
                "value": ["100.0"],
                "unit_of_measure": ["ft^3/s"],
                "approval_status": ["Provisional"],
                "qualifier": [None],
            }
        )

        def fake_get_continuous(**kwargs):
            captured.update(kwargs)
            return api_data, Mock()

        monkeypatch.setattr(
            getusgs_cda_module.waterdata,
            "get_continuous",
            fake_get_continuous,
        )

        result = getusgs_cda_module._get_continuous_data(
            monitoring_location_id=["USGS-04213152"],
            parameter_code="00060",
            time=[
                "2026-11-01T00:00:00Z",
                "2026-11-02T00:00:00Z",
            ],
            last_modified="P2D",
        )

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["value"] == 100.0

        assert captured["monitoring_location_id"] == [
            "USGS-04213152"
        ]
        assert captured["parameter_code"] == "00060"
        assert captured["last_modified"] == "P2D"

        assert captured["properties"] == (
            getusgs_cda_module.USGS_CONTINUOUS_PROPERTIES
        )

    def test_returns_empty_dataframe_for_empty_api_response(self, monkeypatch):
        monkeypatch.setattr(
            getusgs_cda_module.waterdata,
            "get_continuous",
            lambda **kwargs: (pd.DataFrame(), Mock()),
        )

        result = getusgs_cda_module._get_continuous_data(
            monitoring_location_id=["USGS-04213152"],
            parameter_code="00060",
            time=[
                "2026-11-01T00:00:00Z",
                "2026-11-02T00:00:00Z",
            ],
        )

        assert result.empty

    def test_raises_for_missing_required_columns(self, monkeypatch):
        incomplete_data = pd.DataFrame(
            {
                "time": ["2026-11-01T00:00:00Z"],
                "value": [100.0],
            }
        )

        monkeypatch.setattr(
            getusgs_cda_module.waterdata,
            "get_continuous",
            lambda **kwargs: (incomplete_data, Mock()),
        )

        with pytest.raises(
            RuntimeError,
            match="missing required columns",
        ):
            getusgs_cda_module._get_continuous_data(
                monitoring_location_id=["USGS-04213152"],
                parameter_code="00060",
                time=[
                    "2026-11-01T00:00:00Z",
                    "2026-11-02T00:00:00Z",
                ],
            )


class TestGetUSGSTimeseries:
    def test_requests_null_alias_by_location_and_parameter(
        self,
        monkeypatch,
        new_api_usgs_ts_df,
        new_api_usgs_data_df,
    ):
        captured_calls = []

        def fake_get_continuous_data(**kwargs):
            captured_calls.append(kwargs)

            return new_api_usgs_data_df.loc[
                new_api_usgs_data_df["monitoring_location_id"].eq(
                    "USGS-04213152"
                )
            ].copy()

        monkeypatch.setattr(
            getusgs_cda_module,
            "_get_continuous_data",
            fake_get_continuous_data,
        )

        unaliased_ts = new_api_usgs_ts_df.loc[
            new_api_usgs_ts_df["USGS_Time_Series_ID"].isna()
        ].copy()

        result = getusgs_cda_module.getUSGS_ts(
            usgs_ts=unaliased_ts,
            observation_start_dt=datetime(2026, 10, 1),
            observation_end_dt=datetime(2026, 11, 1),
            modified_start_dt=datetime(2026, 10, 30),
            modified_end_dt=datetime(2026, 11, 1),
        )

        assert len(captured_calls) == 1

        assert captured_calls[0]["monitoring_location_id"] == [
            "USGS-04213152"
        ]

        assert captured_calls[0]["parameter_code"] == "00060"

        assert captured_calls[0]["last_modified"] == (
            "2026-10-30T00:00:00/"
            "2026-11-01T00:00:00"
        )

        assert len(result) == 2

        assert (
            result["monitoring_location_id"]
            == "USGS-04213152"
        ).all()

    def test_requests_uuid_alias_by_timeseries_id(
        self,
        monkeypatch,
        new_api_usgs_ts_df,
        new_api_usgs_data_df,
    ):
        captured_calls = []

        def fake_get_continuous_data(**kwargs):
            captured_calls.append(kwargs)

            return new_api_usgs_data_df.loc[
                new_api_usgs_data_df["time_series_id"].eq(
                    "f38a57ccac5a426e8388b8507fa9bbce"
                )
            ].copy()

        monkeypatch.setattr(
            getusgs_cda_module,
            "_get_continuous_data",
            fake_get_continuous_data,
        )

        aliased_ts = new_api_usgs_ts_df.loc[
            new_api_usgs_ts_df["USGS_Time_Series_ID"].notna()
        ].copy()

        result = getusgs_cda_module.getUSGS_ts(
            usgs_ts=aliased_ts,
            observation_start_dt=datetime(2026, 10, 1),
            observation_end_dt=datetime(2026, 11, 1),
            modified_start_dt=datetime(2026, 10, 30),
            modified_end_dt=datetime(2026, 11, 1),
        )

        assert len(captured_calls) == 1

        assert captured_calls[0]["time_series_id"] == [
            "f38a57ccac5a426e8388b8507fa9bbce"
        ]

        assert "monitoring_location_id" not in captured_calls[0]

        assert len(result) == 2

        assert (
            result["time_series_id"]
            == "f38a57ccac5a426e8388b8507fa9bbce"
        ).all()

    def test_passes_last_modified_window_to_all_requests(
        self,
        monkeypatch,
        new_api_usgs_ts_df,
        new_api_usgs_data_df,
    ):
        captured_calls = []

        def fake_get_continuous_data(**kwargs):
            captured_calls.append(kwargs)
            return new_api_usgs_data_df.copy()

        monkeypatch.setattr(
            getusgs_cda_module,
            "_get_continuous_data",
            fake_get_continuous_data,
        )

        getusgs_cda_module.getUSGS_ts(
            usgs_ts=new_api_usgs_ts_df,
            observation_start_dt=datetime(2026, 10, 1),
            observation_end_dt=datetime(2026, 11, 1),
            modified_start_dt=datetime(2026, 10, 30),
            modified_end_dt=datetime(2026, 11, 1),
        )

        assert len(captured_calls) == 2

        expected_last_modified = (
            "2026-10-30T00:00:00/"
            "2026-11-01T00:00:00"
        )

        for call in captured_calls:
            assert call["last_modified"] == expected_last_modified

    def test_returns_empty_dataframe_when_no_usgs_data(
        self,
        monkeypatch,
        new_api_usgs_ts_df,
    ):
        monkeypatch.setattr(
            getusgs_cda_module,
            "_get_continuous_data",
            lambda **kwargs: pd.DataFrame(
                columns=getusgs_cda_module.USGS_CONTINUOUS_PROPERTIES
            ),
        )

        result = getusgs_cda_module.getUSGS_ts(
            usgs_ts=new_api_usgs_ts_df,
            observation_start_dt=datetime(2026, 10, 1),
            observation_end_dt=datetime(2026, 11, 1),
            modified_start_dt=datetime(2026, 10, 30),
            modified_end_dt=datetime(2026, 11, 1),
        )

        assert result.empty


class TestReplaceTSVersion:
    def test_replaces_version_component(self):
        result = getusgs_cda_module._replace_ts_version(
            "DWGN8.Stage.Inst.~15Minutes.0.Raw-USGS",
            "Rev-USGS",
        )

        assert result == (
            "DWGN8.Stage.Inst.~15Minutes.0.Rev-USGS"
        )

    def test_returns_original_when_no_period_present(self):
        result = getusgs_cda_module._replace_ts_version(
            "SimpleID",
            "Rev-USGS",
        )

        assert result == "SimpleID"


class TestValidateBackfillVersionTimeseries:
    def test_removes_missing_backfill_timeseries(self, monkeypatch, caplog):
        mock_response = Mock()
        mock_response.df = pd.DataFrame(
            {
                "timeseries-id": [
                    "LOC1.Flow.Inst.~15Minutes.0.Rev-USGS"
                ]
            }
        )

        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "get_timeseries_identifiers",
            lambda office_id, timeseries_id_regex: mock_response,
        )

        usgs_ts = pd.DataFrame(
            {
                "timeseries-id": [
                    "LOC1.Flow.Inst.~15Minutes.0.Raw-USGS",
                    "LOC2.Stage.Inst.~15Minutes.0.Raw-USGS",
                ],
                "office-id": ["MVP", "MVP"],
            }
        )

        with caplog.at_level(logging.WARNING):
            result = (
                getusgs_cda_module._validate_backfill_version_timeseries(
                    usgs_ts,
                    "Rev-USGS",
                    "MVP",
                )
            )

        assert "do not exist in CWMS" in caplog.text
        assert len(result) == 1

        assert result.iloc[0]["timeseries-id"] == (
            "LOC1.Flow.Inst.~15Minutes.0.Raw-USGS"
        )

    def test_returns_original_when_backfill_version_is_none(
        self,
        monkeypatch,
    ):
        mock_get_identifiers = Mock()

        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "get_timeseries_identifiers",
            mock_get_identifiers,
        )

        usgs_ts = pd.DataFrame(
            {
                "timeseries-id": [
                    "LOC1.Flow.Inst.~15Minutes.0.Raw-USGS"
                ],
                "office-id": ["MVP"],
            }
        )

        result = getusgs_cda_module._validate_backfill_version_timeseries(
            usgs_ts,
            None,
            "MVP",
        )

        mock_get_identifiers.assert_not_called()

        pd.testing.assert_frame_equal(result, usgs_ts)


class TestCWMSWriteData:
    def test_writes_null_alias_station_parameter_data(
        self,
        monkeypatch,
        new_api_usgs_ts_df,
        new_api_usgs_data_df,
        caplog,
    ):
        captured = {}

        def fake_timeseries_df_to_json(data, ts_id, units, office_id):
            captured["data"] = data.copy()
            captured["ts_id"] = ts_id
            captured["units"] = units
            captured["office_id"] = office_id
            return {"success": True}

        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "timeseries_df_to_json",
            fake_timeseries_df_to_json,
        )

        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "store_timeseries",
            Mock(return_value=None),
        )

        unaliased_ts = new_api_usgs_ts_df.loc[
            new_api_usgs_ts_df["USGS_Time_Series_ID"].isna()
        ].copy()

        with caplog.at_level(logging.INFO):
            getusgs_cda_module.CWMS_writeData(
                usgs_ts=unaliased_ts,
                usgs_data=new_api_usgs_data_df,
                days_back=30,
            )

        assert captured["ts_id"] == (
            "LOC1.Flow.Inst.~15Minutes.0.Raw-USGS"
        )

        assert captured["units"] == "ft3/s"
        assert captured["office_id"] == "MVP"
        assert len(captured["data"]) == 2

        assert "SUCCESS: Stored 2 USGS observation(s)" in caplog.text

    def test_writes_only_requested_uuid_timeseries(
        self,
        monkeypatch,
        new_api_usgs_ts_df,
        new_api_usgs_data_df,
    ):
        captured = {}

        def fake_timeseries_df_to_json(data, ts_id, units, office_id):
            captured["data"] = data.copy()
            captured["ts_id"] = ts_id
            captured["units"] = units
            captured["office_id"] = office_id
            return {"success": True}

        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "timeseries_df_to_json",
            fake_timeseries_df_to_json,
        )

        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "store_timeseries",
            Mock(return_value=None),
        )

        aliased_ts = new_api_usgs_ts_df.loc[
            new_api_usgs_ts_df["USGS_Time_Series_ID"].notna()
        ].copy()

        getusgs_cda_module.CWMS_writeData(
            usgs_ts=aliased_ts,
            usgs_data=new_api_usgs_data_df,
            days_back=30,
        )

        assert captured["ts_id"] == (
            "LOC2.Stage.Inst.~15Minutes.0.Raw-USGS"
        )

        assert captured["units"] == "ft"

        assert captured["data"]["value"].tolist() == [
            5.0,
            5.2,
        ]

    def test_does_not_write_null_alias_when_multiple_series_return(
        self,
        monkeypatch,
        caplog,
    ):
        mock_store = Mock(return_value=None)

        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "store_timeseries",
            mock_store,
        )

        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "timeseries_df_to_json",
            Mock(return_value={"success": True}),
        )

        usgs_ts = pd.DataFrame(
            {
                "timeseries-id": [
                    "LOC1.Flow.Inst.~15Minutes.0.Raw-USGS"
                ],
                "office-id": ["MVP"],
                "USGS_St_Num": ["04213152"],
                "USGS_PARAMETER": ["00060"],
                "USGS_Time_Series_ID": [pd.NA],
            }
        )

        usgs_data = pd.DataFrame(
            {
                "time_series_id": [
                    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                ],
                "monitoring_location_id": [
                    "USGS-04213152",
                    "USGS-04213152",
                ],
                "parameter_code": [
                    "00060",
                    "00060",
                ],
                "time": pd.to_datetime(
                    [
                        "2026-11-01T00:00:00Z",
                        "2026-11-01T00:00:00Z",
                    ],
                    utc=True,
                ),
                "value": [100.0, 0.0],
                "unit_of_measure": [
                    "ft^3/s",
                    "ft^3/s",
                ],
            }
        )

        with caplog.at_level(logging.ERROR):
            getusgs_cda_module.CWMS_writeData(
                usgs_ts=usgs_ts,
                usgs_data=usgs_data,
                days_back=30,
            )

        mock_store.assert_not_called()

        assert "returned multiple USGS time_series_id values" in caplog.text

    def test_applies_backfill_version_when_storing(
        self,
        monkeypatch,
        new_api_usgs_ts_df,
        new_api_usgs_data_df,
    ):
        captured = {}

        def fake_timeseries_df_to_json(data, ts_id, units, office_id):
            captured["ts_id"] = ts_id
            return {"success": True}

        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "timeseries_df_to_json",
            fake_timeseries_df_to_json,
        )

        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "store_timeseries",
            Mock(return_value=None),
        )

        aliased_ts = new_api_usgs_ts_df.loc[
            new_api_usgs_ts_df["USGS_Time_Series_ID"].notna()
        ].copy()

        getusgs_cda_module.CWMS_writeData(
            usgs_ts=aliased_ts,
            usgs_data=new_api_usgs_data_df,
            days_back=30,
            backfill_version="Rev-USGS",
        )

        assert captured["ts_id"] == (
            "LOC2.Stage.Inst.~15Minutes.0.Rev-USGS"
        )


class TestGetUSGSCDA:
    def test_routes_to_new_api_with_last_modified_window(
        self,
        monkeypatch,
        new_api_usgs_ts_df,
    ):
        captured = {}

        monkeypatch.setattr(
            getusgs_cda_module,
            "init_cwms_session",
            lambda *args, **kwargs: None,
        )

        monkeypatch.setattr(
            getusgs_cda_module,
            "get_CMWS_TS_Loc_Data",
            lambda office_id: new_api_usgs_ts_df.copy(),
        )

        monkeypatch.setattr(
            getusgs_cda_module,
            "_validate_backfill_version_timeseries",
            lambda usgs_ts, backfill_version, office_id: usgs_ts,
        )

        def fake_get_usgs_ts(**kwargs):
            captured["get_usgs_ts"] = kwargs

            return pd.DataFrame(
                columns=getusgs_cda_module.USGS_CONTINUOUS_PROPERTIES
            )

        monkeypatch.setattr(
            getusgs_cda_module,
            "getUSGS_ts",
            fake_get_usgs_ts,
        )

        def fake_write_data(**kwargs):
            captured["write_data"] = kwargs

        monkeypatch.setattr(
            getusgs_cda_module,
            "CWMS_writeData",
            fake_write_data,
        )

        getusgs_cda_module.getusgs_cda(
            api_root="https://example.test/cwms-data",
            office_id="MVP",
            days_back=2,
            api_key="test-api-key",
        )

        assert "get_usgs_ts" in captured
        assert "write_data" in captured

        get_usgs_args = captured["get_usgs_ts"]

        assert set(
            get_usgs_args["usgs_ts"]["timeseries-id"]
        ) == {
            "LOC1.Flow.Inst.~15Minutes.0.Raw-USGS",
            "LOC2.Stage.Inst.~15Minutes.0.Raw-USGS",
        }

        modified_delta = (
            get_usgs_args["modified_end_dt"]
            - get_usgs_args["modified_start_dt"]
        )

        assert modified_delta == timedelta(days=2)

        observation_delta = (
            get_usgs_args["observation_end_dt"]
            - get_usgs_args["observation_start_dt"]
        )

        # When revision_observation_lookback_days is omitted, it defaults
        # to days_back. This preserves the prior behavior.
        expected_observation_delta = timedelta(
            days=2,
            hours=2,
        )

        assert observation_delta == expected_observation_delta

    def test_uses_explicit_revision_observation_lookback(
        self,
        monkeypatch,
        new_api_usgs_ts_df,
    ):
        captured = {}

        monkeypatch.setattr(
            getusgs_cda_module,
            "init_cwms_session",
            lambda *args, **kwargs: None,
        )

        monkeypatch.setattr(
            getusgs_cda_module,
            "get_CMWS_TS_Loc_Data",
            lambda office_id: new_api_usgs_ts_df.copy(),
        )

        monkeypatch.setattr(
            getusgs_cda_module,
            "_validate_backfill_version_timeseries",
            lambda usgs_ts, backfill_version, office_id: usgs_ts,
        )

        def fake_get_usgs_ts(**kwargs):
            captured.update(kwargs)

            return pd.DataFrame(
                columns=getusgs_cda_module.USGS_CONTINUOUS_PROPERTIES
            )

        monkeypatch.setattr(
            getusgs_cda_module,
            "getUSGS_ts",
            fake_get_usgs_ts,
        )

        monkeypatch.setattr(
            getusgs_cda_module,
            "CWMS_writeData",
            lambda **kwargs: None,
        )

        getusgs_cda_module.getusgs_cda(
            api_root="https://example.test/cwms-data",
            office_id="MVP",
            days_back=2,
            revision_lookback_days=30,
            api_key="test-api-key",
        )

        modified_delta = (
            captured["modified_end_dt"]
            - captured["modified_start_dt"]
        )

        observation_delta = (
            captured["observation_end_dt"]
            - captured["observation_start_dt"]
        )

        assert modified_delta == timedelta(days=2)

        assert observation_delta == timedelta(
            days=30,
            hours=2,
        )

    def test_skips_numeric_legacy_method_aliases(
        self,
        monkeypatch,
        new_api_usgs_ts_df,
        caplog,
    ):
        legacy_config = new_api_usgs_ts_df.copy()

        legacy_config.loc[
            legacy_config["timeseries-id"].eq(
                "LOC2.Stage.Inst.~15Minutes.0.Raw-USGS"
            ),
            "USGS_Time_Series_ID",
        ] = "220645"

        captured = {}

        monkeypatch.setattr(
            getusgs_cda_module,
            "init_cwms_session",
            lambda *args, **kwargs: None,
        )

        monkeypatch.setattr(
            getusgs_cda_module,
            "get_CMWS_TS_Loc_Data",
            lambda office_id: legacy_config.copy(),
        )

        monkeypatch.setattr(
            getusgs_cda_module,
            "_validate_backfill_version_timeseries",
            lambda usgs_ts, backfill_version, office_id: usgs_ts,
        )

        monkeypatch.setattr(
            getusgs_cda_module,
            "getUSGS_ts",
            lambda **kwargs: pd.DataFrame(
                columns=getusgs_cda_module.USGS_CONTINUOUS_PROPERTIES
            ),
        )

        monkeypatch.setattr(
            getusgs_cda_module,
            "CWMS_writeData",
            lambda **kwargs: captured.update(kwargs),
        )

        with caplog.at_level(logging.WARNING):
            getusgs_cda_module.getusgs_cda(
                api_root="https://example.test/cwms-data",
                office_id="MVP",
                days_back=2,
                api_key="test-api-key",
            )

        assert "numeric legacy USGS method IDs" in caplog.text

        remaining_tsids = set(
            captured["usgs_ts"]["timeseries-id"].tolist()
        )

        assert remaining_tsids == {
            "LOC1.Flow.Inst.~15Minutes.0.Raw-USGS"
        }


class TestResampleToTSIDInterval:
    def test_does_not_resample_irregular_timeseries(self):
        values = pd.DataFrame(
            {
                "date-time": pd.to_datetime(
                    [
                        "2026-11-01T00:00:00Z",
                        "2026-11-01T00:05:00Z",
                    ],
                    utc=True,
                ),
                "value": [1.0, 2.0],
                "quality-code": [0, 0],
            }
        )

        result = getusgs_cda_module.resample_to_tsid_interval(
            values,
            "LOC.Flow.Inst.~15Minutes.0.Raw-USGS",
        )

        assert len(result) == 2
        assert result["value"].tolist() == [1.0, 2.0]

    def test_resamples_to_requested_interval(self):
        values = pd.DataFrame(
            {
                "date-time": pd.to_datetime(
                    [
                        "2026-11-01T00:00:00Z",
                        "2026-11-01T00:05:00Z",
                        "2026-11-01T00:10:00Z",
                        "2026-11-01T00:15:00Z",
                    ],
                    utc=True,
                ),
                "value": [1.0, 2.0, 3.0, 4.0],
                "quality-code": [0, 0, 0, 0],
            }
        )

        result = getusgs_cda_module.resample_to_tsid_interval(
            values,
            "LOC.Flow.Inst.15Minutes.0.Raw-USGS",
        )

        assert len(result) == 2
        assert result["value"].tolist() == [1.0, 4.0]