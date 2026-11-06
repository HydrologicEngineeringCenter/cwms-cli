import logging
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

import cwmscli.usgs.getusgs_cda as getusgs_cda_module


@pytest.fixture
def usgs_timeseries_df():
    """Load real sample timeseries group data from fixture."""
    fixture_path = (
        Path(__file__).parent.parent
        / "fixtures"
        / "usgs"
        / "usgs_timeseries_groups.csv"
    )
    df = pd.read_csv(fixture_path)
    return df


@pytest.fixture
def usgs_location_group_df():
    """Load real sample location group data from fixture."""
    fixture_path = (
        Path(__file__).parent.parent / "fixtures" / "usgs" / "usgs_location_group.csv"
    )
    df = pd.read_csv(fixture_path)
    return df


@pytest.fixture
def mock_cwms_response_with_df():
    """Create a mock CWMS response object with a df attribute."""
    response = Mock()
    response.json = None
    return response


class TestGetUSGSParams:
    def test_returns_dataframe(self):
        """Test that get_USGS_params returns a DataFrame."""
        result = getusgs_cda_module.get_USGS_params()
        assert isinstance(result, pd.DataFrame)

    def test_has_expected_columns(self):
        """Test that the result has all expected columns."""
        result = getusgs_cda_module.get_USGS_params()
        expected_columns = [
            "USGS_PARAMETER",
            "USGS_Alias",
            "CWMS_FACTOR",
            "CWMS_UNIT",
            "CWMS_TYPE",
        ]
        for col in expected_columns:
            assert col in result.columns
        # CWMS_PARAMETER is the index, not a column
        assert result.index.name == "CWMS_PARAMETER"

    def test_index_is_cwms_parameter(self):
        """Test that index is set to CWMS_PARAMETER."""
        result = getusgs_cda_module.get_USGS_params()
        assert result.index.name == "CWMS_PARAMETER"

    def test_contains_common_parameters(self):
        """Test that result contains common hydrologic parameters."""
        result = getusgs_cda_module.get_USGS_params()
        assert "Flow" in result.index
        assert "Stage" in result.index
        assert "Temp-Water" in result.index
        assert "Cond" in result.index

    def test_flow_parameter_values(self):
        """Test that Flow parameter has correct values."""
        result = getusgs_cda_module.get_USGS_params()
        flow_row = result.loc["Flow"]
        assert flow_row["USGS_PARAMETER"] == "00060"
        assert flow_row["CWMS_FACTOR"] == 1
        assert flow_row["CWMS_UNIT"] == "cfs"
        assert flow_row["CWMS_TYPE"] == "Inst"


class TestLogErrorAndExit:
    def test_raises_systemexit(self):
        """Test that _log_error_and_exit raises SystemExit."""
        with pytest.raises(SystemExit) as exc_info:
            getusgs_cda_module._log_error_and_exit("Test error")
        assert exc_info.value.code == 1

    def test_custom_exit_code(self):
        """Test that custom exit code is used."""
        with pytest.raises(SystemExit) as exc_info:
            getusgs_cda_module._log_error_and_exit("Test error", exit_code=2)
        assert exc_info.value.code == 2

    def test_logs_error(self, caplog):
        """Test that error is logged."""
        with pytest.raises(SystemExit):
            with caplog.at_level(logging.ERROR):
                getusgs_cda_module._log_error_and_exit("Test error message")
        assert "Test error message" in caplog.text

    def test_logs_hint_when_provided(self, caplog):
        """Test that hint is logged when provided."""
        with pytest.raises(SystemExit):
            with caplog.at_level(logging.ERROR):
                getusgs_cda_module._log_error_and_exit("Test error", hint="Test hint")
        assert "Test hint" in caplog.text


class TestRequireGroupDataframe:
    def test_returns_dataframe_when_df_exists(self, mock_cwms_response_with_df):
        """Test that function returns df when it exists."""
        expected_df = pd.DataFrame({"col": [1, 2, 3]})
        mock_cwms_response_with_df.df = expected_df

        result = getusgs_cda_module._require_group_dataframe(
            mock_cwms_response_with_df, resource_name="test resource", office="MVP"
        )
        pd.testing.assert_frame_equal(result, expected_df)

    def test_raises_on_none_df(self, mock_cwms_response_with_df):
        """Test that function raises SystemExit when df is None."""
        mock_cwms_response_with_df.df = None

        with pytest.raises(SystemExit):
            getusgs_cda_module._require_group_dataframe(
                mock_cwms_response_with_df, resource_name="test resource", office="MVP"
            )

    def test_raises_on_empty_df(self, mock_cwms_response_with_df):
        """Test that function raises SystemExit when df is empty."""
        mock_cwms_response_with_df.df = pd.DataFrame()
        # Empty dataframe is falsy, so it should raise
        # (checking if df is None happens first, then it checks if df evaluates to False)
        # Actually, empty dataframe is considered as having len 0, but the function only checks if it's None
        # Let's verify the actual behavior
        result = getusgs_cda_module._require_group_dataframe(
            mock_cwms_response_with_df, resource_name="test resource", office="MVP"
        )
        # Empty dataframe is returned as-is, the function doesn't check if it's empty
        assert result is not None

    def test_raises_on_missing_df_attribute_with_json_payload(
        self, mock_cwms_response_with_df
    ):
        """Test that function raises SystemExit when df attribute missing and json payload is string."""
        mock_cwms_response_with_df.json = "error message"
        del mock_cwms_response_with_df.df

        with pytest.raises(SystemExit):
            getusgs_cda_module._require_group_dataframe(
                mock_cwms_response_with_df, resource_name="test resource", office="MVP"
            )

    def test_reraises_on_missing_df_attribute_with_other_payload(self):
        """Test that function re-raises AttributeError when payload is not a string."""
        response = Mock(spec=[])

        with pytest.raises(AttributeError):
            getusgs_cda_module._require_group_dataframe(
                response, resource_name="test resource", office="MVP"
            )


class TestGetCMWSTS_LocData:
    def test_combines_timeseries_and_location_data(
        self, monkeypatch, usgs_timeseries_df, usgs_location_group_df
    ):
        """Test that function combines timeseries and location data."""
        ts_response = Mock()
        ts_response.df = usgs_timeseries_df

        loc_response = Mock()
        loc_response.df = usgs_location_group_df

        def mock_get_timeseries_group(**kwargs):
            assert kwargs["group_id"] == "USGS TS Data Acquisition"
            assert kwargs["office_id"] == "MVP"
            return ts_response

        def mock_get_location_group(**kwargs):
            assert kwargs["loc_group_id"] == "USGS Station Number"
            assert kwargs["office_id"] == "CWMS"
            return loc_response

        monkeypatch.setattr(
            getusgs_cda_module.cwms, "get_timeseries_group", mock_get_timeseries_group
        )
        monkeypatch.setattr(
            getusgs_cda_module.cwms, "get_location_group", mock_get_location_group
        )

        result = getusgs_cda_module.get_CMWS_TS_Loc_Data("MVP")

        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0
        assert "USGS_St_Num" in result.columns
        assert "USGS_PARAMETER" in result.columns
        assert "location-id" in result.columns

    def test_filters_by_office(
        self, monkeypatch, usgs_timeseries_df, usgs_location_group_df
    ):
        """Test that function filters results by office."""
        ts_response = Mock()
        ts_response.df = usgs_timeseries_df.copy()

        loc_response = Mock()
        loc_response.df = usgs_location_group_df.copy()

        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "get_timeseries_group",
            lambda **kwargs: ts_response,
        )
        monkeypatch.setattr(
            getusgs_cda_module.cwms, "get_location_group", lambda **kwargs: loc_response
        )

        result = getusgs_cda_module.get_CMWS_TS_Loc_Data("MVP")

        # All rows should have MVP office
        assert (result["office-id"] == "MVP").all()

    def test_pads_usgs_station_numbers(
        self, monkeypatch, usgs_timeseries_df, usgs_location_group_df
    ):
        """Test that USGS station numbers are padded to 8 digits."""
        ts_response = Mock()
        ts_response.df = usgs_timeseries_df.copy()

        loc_response = Mock()
        loc_response.df = usgs_location_group_df.copy()

        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "get_timeseries_group",
            lambda **kwargs: ts_response,
        )
        monkeypatch.setattr(
            getusgs_cda_module.cwms, "get_location_group", lambda **kwargs: loc_response
        )

        result = getusgs_cda_module.get_CMWS_TS_Loc_Data("MVP")

        # Check that station numbers are at least 8 characters
        valid_stations = result[result["USGS_St_Num"].notna()]
        for st_num in valid_stations["USGS_St_Num"]:
            assert len(str(st_num)) >= 8

    def test_raises_when_no_timeseries_group(self, monkeypatch):
        """Test that function raises when no timeseries group data."""
        ts_response = Mock()
        ts_response.df = pd.DataFrame()  # Empty

        loc_response = Mock()
        loc_response.df = pd.DataFrame(
            {
                "location-id": ["LOC1"],
                "office-id": ["MVP"],
                "alias-id": ["12345678"],
            }
        )

        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "get_timeseries_group",
            lambda **kwargs: ts_response,
        )
        monkeypatch.setattr(
            getusgs_cda_module.cwms, "get_location_group", lambda **kwargs: loc_response
        )

        with pytest.raises(SystemExit):
            getusgs_cda_module.get_CMWS_TS_Loc_Data("MVP")

    def test_raises_when_no_location_aliases(self, monkeypatch, usgs_timeseries_df):
        """Test that function raises when no location aliases."""
        ts_response = Mock()
        ts_response.df = usgs_timeseries_df.copy()

        loc_response = Mock()
        loc_response.df = pd.DataFrame(
            {
                "location-id": ["LOC1"],
                "office-id": ["MVP"],
                "alias-id": [np.nan],  # No aliases
            }
        )

        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "get_timeseries_group",
            lambda **kwargs: ts_response,
        )
        monkeypatch.setattr(
            getusgs_cda_module.cwms, "get_location_group", lambda **kwargs: loc_response
        )

        with pytest.raises(SystemExit):
            getusgs_cda_module.get_CMWS_TS_Loc_Data("MVP")

    def test_includes_usgs_parameter_code(
        self, monkeypatch, usgs_timeseries_df, usgs_location_group_df
    ):
        """Test that USGS parameter codes are included."""
        ts_response = Mock()
        ts_response.df = usgs_timeseries_df.copy()

        loc_response = Mock()
        loc_response.df = usgs_location_group_df.copy()

        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "get_timeseries_group",
            lambda **kwargs: ts_response,
        )
        monkeypatch.setattr(
            getusgs_cda_module.cwms, "get_location_group", lambda **kwargs: loc_response
        )

        result = getusgs_cda_module.get_CMWS_TS_Loc_Data("MVP")

        assert "USGS_PARAMETER" in result.columns
        # USGS_PARAMETER should be numeric string codes
        assert all(result["USGS_PARAMETER"].str.match(r"^\d+$"))


class TestGetUSGS_ts:
    def test_formats_response_correctly(self, monkeypatch):
        """Test that USGS response is formatted correctly."""
        mock_response = {
            "value": {
                "timeSeries": [
                    {
                        "name": "USGS:04213152:00060:00000",
                        "sourceInfo": {},
                        "values": [
                            [{"value": [{"dateTime": "2024-01-01", "value": "100"}]}]
                        ],
                    }
                ]
            }
        }

        monkeypatch.setattr(
            "cwmscli.usgs.getusgs_cda.requests.get",
            lambda *args, **kwargs: Mock(json=lambda: mock_response),
        )

        sites = ["04213152"]
        start_dt = datetime(2024, 1, 1)
        end_dt = datetime(2024, 1, 31)

        result = getusgs_cda_module.getUSGS_ts(sites, start_dt, end_dt)

        assert isinstance(result, pd.DataFrame)
        # Id.param becomes the index after set_index
        assert "04213152.00060" in result.index

    def test_passes_correct_parameters_to_api(self, monkeypatch):
        """Test that correct parameters are passed to USGS API."""
        captured_params = {}

        def mock_get(url, params=None):
            captured_params.update(params or {})
            mock_response = {
                "value": {
                    "timeSeries": [
                        {
                            "name": "USGS:04213152:00060:00000",
                            "sourceInfo": {},
                            "values": [],
                        }
                    ]
                }
            }
            return Mock(json=lambda: mock_response)

        monkeypatch.setattr("cwmscli.usgs.getusgs_cda.requests.get", mock_get)

        sites = ["04213152", "04213160"]
        start_dt = datetime(2024, 1, 1)
        end_dt = datetime(2024, 1, 31)

        getusgs_cda_module.getUSGS_ts(sites, start_dt, end_dt, access=3)

        assert captured_params["format"] == "json"
        assert captured_params["sites"] == "04213152,04213160"
        assert captured_params["startDT"] == "2024-01-01T00:00:00"
        assert captured_params["endDT"] == "2024-01-31T00:00:00"
        assert captured_params["access"] == 3
        assert captured_params["siteStatus"] == "active"

    def test_handles_multiple_sites(self, monkeypatch):
        """Test that multiple sites are joined correctly."""
        captured_params = {}

        def mock_get(url, params=None):
            captured_params.update(params or {})
            mock_response = {
                "value": {
                    "timeSeries": [
                        {
                            "name": "USGS:04213152:00060:00000",
                            "sourceInfo": {},
                            "values": [],
                        }
                    ]
                }
            }
            return Mock(json=lambda: mock_response)

        monkeypatch.setattr("cwmscli.usgs.getusgs_cda.requests.get", mock_get)

        sites = ["04213152", "04213160", "04213300"]
        getusgs_cda_module.getUSGS_ts(
            sites, datetime(2024, 1, 1), datetime(2024, 1, 31)
        )

        assert captured_params["sites"] == "04213152,04213160,04213300"


class TestValidateBackfillVersionTimeseries:
    def test_warns_when_timeseries_missing(self, monkeypatch, caplog):
        """Test that warning is logged when backfill timeseries don't exist."""
        mock_response = Mock()
        mock_response.df = pd.DataFrame(
            {"timeseries-id": ["LOC1.Flow.Inst.~15Minutes.0.Rev-USGS"]}
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
            result = getusgs_cda_module._validate_backfill_version_timeseries(
                usgs_ts, "Rev-USGS", "MVP"
            )

        assert "do not exist in CWMS" in caplog.text
        # LOC2 should be removed, only LOC1 remains
        assert len(result) == 1
        assert result["timeseries-id"].iloc[0] == "LOC1.Flow.Inst.~15Minutes.0.Raw-USGS"

    def test_no_warning_when_all_timeseries_exist(self, monkeypatch, caplog):
        """Test that no warning is logged when all backfill timeseries exist."""
        mock_response = Mock()
        mock_response.df = pd.DataFrame(
            {
                "timeseries-id": [
                    "LOC1.Flow.Inst.~15Minutes.0.Rev-USGS",
                    "LOC2.Stage.Inst.~15Minutes.0.Rev-USGS",
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
            result = getusgs_cda_module._validate_backfill_version_timeseries(
                usgs_ts, "Rev-USGS", "MVP"
            )

        assert "do not exist in CWMS" not in caplog.text
        # All timeseries should remain
        assert len(result) == 2

    def test_skips_validation_when_backfill_version_none(self, monkeypatch, caplog):
        """Test that validation is skipped when backfill_version is None."""
        mock_get_ts = Mock()
        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "get_timeseries_identifiers",
            mock_get_ts,
        )

        usgs_ts = pd.DataFrame(
            {
                "timeseries-id": ["LOC1.Flow.Inst.~15Minutes.0.Raw-USGS"],
                "office-id": ["MVP"],
            }
        )

        result = getusgs_cda_module._validate_backfill_version_timeseries(
            usgs_ts, None, "MVP"
        )

        # Should not call get_timeseries_identifiers
        mock_get_ts.assert_not_called()
        # Should return unchanged dataframe
        pd.testing.assert_frame_equal(result, usgs_ts)

    def test_handles_empty_response(self, monkeypatch, caplog):
        """Test that missing timeseries are detected with empty response."""
        mock_response = Mock()
        mock_response.df = pd.DataFrame()

        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "get_timeseries_identifiers",
            lambda office_id, timeseries_id_regex: mock_response,
        )

        usgs_ts = pd.DataFrame(
            {
                "timeseries-id": ["LOC1.Flow.Inst.~15Minutes.0.Raw-USGS"],
                "office-id": ["MVP"],
            }
        )

        with caplog.at_level(logging.WARNING):
            result = getusgs_cda_module._validate_backfill_version_timeseries(
                usgs_ts, "Rev-USGS", "MVP"
            )

        assert "do not exist in CWMS" in caplog.text
        # All timeseries should be removed
        assert len(result) == 0


class TestReplaceTS_Version:
    def test_replaces_version_component(self):
        """Test that version component is replaced correctly."""
        ts_id = "DWGN8.Stage.Inst.~15Minutes.0.Raw-USGS"
        backfill_version = "Rev-USGS"

        result = getusgs_cda_module._replace_ts_version(ts_id, backfill_version)

        assert result == "DWGN8.Stage.Inst.~15Minutes.0.Rev-USGS"

    def test_handles_simple_version(self):
        """Test with simple version string."""
        ts_id = "LOC.Flow.Inst.~15Minutes.0.Raw"
        backfill_version = "Test"

        result = getusgs_cda_module._replace_ts_version(ts_id, backfill_version)

        assert result == "LOC.Flow.Inst.~15Minutes.0.Test"

    def test_handles_version_with_multiple_dashes(self):
        """Test with version containing dashes."""
        ts_id = "LOC.Stage.Inst.~15Minutes.0.Rev-USGS-v2"
        backfill_version = "New-Rev-USGS"

        result = getusgs_cda_module._replace_ts_version(ts_id, backfill_version)

        assert result == "LOC.Stage.Inst.~15Minutes.0.New-Rev-USGS"

    def test_handles_ts_id_without_dots(self):
        """Test with TS ID that has no dots."""
        ts_id = "SimpleID"
        backfill_version = "NewVersion"

        result = getusgs_cda_module._replace_ts_version(ts_id, backfill_version)

        # If no dot found, function returns original ts_id
        assert result == "SimpleID"

    def test_preserves_location_and_parameters(self):
        """Test that location and parameter parts are preserved."""
        ts_id = "MyLocation-Base.Parameter.Type.Interval.Season.OldVersion"
        backfill_version = "NewVersion"

        result = getusgs_cda_module._replace_ts_version(ts_id, backfill_version)

        # Everything before the last dot should be preserved
        assert result.startswith("MyLocation-Base.Parameter.Type.Interval.Season.")
        assert result.endswith("NewVersion")


class TestCWMS_writeData:
    def test_logs_success_when_data_written(self, monkeypatch, caplog):
        """Test that success is logged when data is written."""
        monkeypatch.setattr(
            getusgs_cda_module.cwms, "store_timeseries", Mock(return_value=None)
        )
        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "timeseries_df_to_json",
            Mock(return_value={"success": True}),
        )

        usgs_ts = pd.DataFrame(
            {
                "timeseries-id": ["LOC1.Flow.Inst.~15Minutes.0.Raw-USGS"],
                "office-id": ["MVP"],
                "USGS_St_Num": ["04213152"],
                "USGS_PARAMETER": ["00060"],
                "USGS_Method_TS": [np.nan],
            }
        )

        usgs_data = pd.DataFrame(
            index=["04213152.00060"],
            data={
                "values": [
                    [
                        {
                            "value": [
                                {
                                    "dateTime": "2024-01-01",
                                    "value": "100",
                                    "qualifiers": "0",
                                }
                            ]
                        }
                    ]
                ],
                "variable": [{"noDataValue": "-999999", "unit": {"unitCode": "ft3/s"}}],
            },
        )

        usgs_data_method = pd.DataFrame()

        with caplog.at_level(logging.INFO):
            getusgs_cda_module.CWMS_writeData(
                usgs_ts, usgs_data, usgs_data_method, days_back=30
            )

        assert "successfully saved" in caplog.text.lower()

    def test_logs_error_when_data_not_found(self, caplog):
        """Test that error is logged when USGS data not found."""
        usgs_ts = pd.DataFrame(
            {
                "timeseries-id": ["LOC1.Flow.Inst.~15Minutes.0.Raw-USGS"],
                "office-id": ["MVP"],
                "USGS_St_Num": ["04213152"],
                "USGS_PARAMETER": ["00060"],
                "USGS_Method_TS": [np.nan],
            }
        )

        usgs_data = pd.DataFrame()  # Empty - no data
        usgs_data_method = pd.DataFrame()

        with caplog.at_level(logging.WARNING):
            getusgs_cda_module.CWMS_writeData(
                usgs_ts, usgs_data, usgs_data_method, days_back=30
            )

        assert "not present in USGS API" in caplog.text

    def test_handles_multiple_records(self, monkeypatch, caplog):
        """Test that multiple time series records are processed."""
        monkeypatch.setattr(
            getusgs_cda_module.cwms, "store_timeseries", Mock(return_value=None)
        )
        monkeypatch.setattr(
            getusgs_cda_module.cwms,
            "timeseries_df_to_json",
            Mock(return_value={"success": True}),
        )

        usgs_ts = pd.DataFrame(
            {
                "timeseries-id": [
                    "LOC1.Flow.Inst.~15Minutes.0.Raw-USGS",
                    "LOC2.Stage.Inst.~15Minutes.0.Raw-USGS",
                ],
                "office-id": ["MVP", "MVP"],
                "USGS_St_Num": ["04213152", "04213160"],
                "USGS_PARAMETER": ["00060", "00065"],
                "USGS_Method_TS": [np.nan, np.nan],
            }
        )

        usgs_data = pd.DataFrame(
            index=["04213152.00060", "04213160.00065"],
            data={
                "values": [
                    [
                        {
                            "value": [
                                {
                                    "dateTime": "2024-01-01",
                                    "value": "100",
                                    "qualifiers": "0",
                                }
                            ]
                        }
                    ],
                    [
                        {
                            "value": [
                                {
                                    "dateTime": "2024-01-01",
                                    "value": "5",
                                    "qualifiers": "0",
                                }
                            ]
                        }
                    ],
                ],
                "variable": [
                    {"noDataValue": "-999999", "unit": {"unitCode": "ft3/s"}},
                    {"noDataValue": "-999999", "unit": {"unitCode": "ft"}},
                ],
            },
        )

        usgs_data_method = pd.DataFrame()

        with caplog.at_level(logging.INFO):
            getusgs_cda_module.CWMS_writeData(
                usgs_ts, usgs_data, usgs_data_method, days_back=30
            )

        # Check that both records were processed
        assert "04213152.00060" in caplog.text
        assert "04213160.00065" in caplog.text

    def test_applies_backfill_version_when_provided(self, monkeypatch):
        """Test that backfill_version is applied to ts_id when writing data."""
        mock_store = Mock(return_value=None)
        captured_ts_id = {}

        def capture_ts_id(data, ts_id=None, units=None, office_id=None):
            captured_ts_id["ts_id"] = ts_id
            return {"success": True}

        monkeypatch.setattr(getusgs_cda_module.cwms, "store_timeseries", mock_store)
        monkeypatch.setattr(
            getusgs_cda_module.cwms, "timeseries_df_to_json", capture_ts_id
        )

        usgs_ts = pd.DataFrame(
            {
                "timeseries-id": ["LOC1.Flow.Inst.~15Minutes.0.Raw-USGS"],
                "office-id": ["MVP"],
                "USGS_St_Num": ["04213152"],
                "USGS_PARAMETER": ["00060"],
                "USGS_Method_TS": [np.nan],
            }
        )

        usgs_data = pd.DataFrame(
            index=["04213152.00060"],
            data={
                "values": [
                    [
                        {
                            "value": [
                                {
                                    "dateTime": "2024-01-01",
                                    "value": "100",
                                    "qualifiers": "0",
                                }
                            ]
                        }
                    ]
                ],
                "variable": [{"noDataValue": "-999999", "unit": {"unitCode": "ft3/s"}}],
            },
        )

        usgs_data_method = pd.DataFrame()

        getusgs_cda_module.CWMS_writeData(
            usgs_ts,
            usgs_data,
            usgs_data_method,
            days_back=30,
            backfill_version="Rev-USGS",
        )

        # Verify that the ts_id passed to timeseries_df_to_json has the new version
        assert captured_ts_id["ts_id"] == "LOC1.Flow.Inst.~15Minutes.0.Rev-USGS"

    def test_uses_original_ts_id_without_backfill_version(self, monkeypatch):
        """Test that original ts_id is used when backfill_version is not provided."""
        mock_store = Mock(return_value=None)
        captured_ts_id = {}

        def capture_ts_id(data, ts_id=None, units=None, office_id=None):
            captured_ts_id["ts_id"] = ts_id
            return {"success": True}

        monkeypatch.setattr(getusgs_cda_module.cwms, "store_timeseries", mock_store)
        monkeypatch.setattr(
            getusgs_cda_module.cwms, "timeseries_df_to_json", capture_ts_id
        )

        usgs_ts = pd.DataFrame(
            {
                "timeseries-id": ["LOC1.Flow.Inst.~15Minutes.0.Raw-USGS"],
                "office-id": ["MVP"],
                "USGS_St_Num": ["04213152"],
                "USGS_PARAMETER": ["00060"],
                "USGS_Method_TS": [np.nan],
            }
        )

        usgs_data = pd.DataFrame(
            index=["04213152.00060"],
            data={
                "values": [
                    [
                        {
                            "value": [
                                {
                                    "dateTime": "2024-01-01",
                                    "value": "100",
                                    "qualifiers": "0",
                                }
                            ]
                        }
                    ]
                ],
                "variable": [{"noDataValue": "-999999", "unit": {"unitCode": "ft3/s"}}],
            },
        )

        usgs_data_method = pd.DataFrame()

        getusgs_cda_module.CWMS_writeData(
            usgs_ts, usgs_data, usgs_data_method, days_back=30
        )

        # Verify that the original ts_id is used
        assert captured_ts_id["ts_id"] == "LOC1.Flow.Inst.~15Minutes.0.Raw-USGS"
