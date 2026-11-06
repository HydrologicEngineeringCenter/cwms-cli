import numpy as np
import pandas as pd
import pytest

from cwmscli.usgs.getusgs_cda import (
    CWMS_writeData,
    resample_to_tsid_interval,
)


def _build_new_api_usgs_ts(
    ts_id: str,
    usgs_station_number: str = "00000001",
    usgs_parameter: str = "00060",
    office_id: str = "SPK",
    time_series_id=None,
) -> pd.DataFrame:
    """
    Build CWMS USGS acquisition configuration compatible with the new API.

    A null USGS_Time_Series_ID means the writer selects data using:

        monitoring_location_id + parameter_code

    A UUID value means the writer selects data using time_series_id.
    """

    return pd.DataFrame(
        {
            "timeseries-id": [ts_id],
            "USGS_St_Num": [usgs_station_number],
            "USGS_PARAMETER": [usgs_parameter],
            "USGS_Time_Series_ID": [time_series_id],
            "office-id": [office_id],
        }
    )


def _build_new_api_usgs_data(
    station_number: str,
    parameter_code: str,
    datetimes,
    values,
    time_series_id: str = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    unit_of_measure: str = "ft^3/s",
) -> pd.DataFrame:
    """
    Build long-format continuous data compatible with the new USGS API.
    """

    return pd.DataFrame(
        {
            "time_series_id": [time_series_id] * len(datetimes),
            "monitoring_location_id": [
                f"USGS-{station_number}"
            ]
            * len(datetimes),
            "parameter_code": [parameter_code] * len(datetimes),
            "statistic_id": ["00011"] * len(datetimes),
            "time": pd.to_datetime(datetimes, utc=True),
            "value": values,
            "unit_of_measure": [unit_of_measure] * len(datetimes),
        }
    )


@pytest.mark.parametrize(
    "incoming_freq,target_interval,incoming_count,expected_count",
    [
        ("15min", "15Minutes", 3, 3),
        ("5min", "15Minutes", 9, 3),
    ],
)
def test_cwms_write_data_resample_behavior(
    monkeypatch,
    incoming_freq,
    target_interval,
    incoming_count,
    expected_count,
):
    """
    Verify that new-USGS long-format observations are resampled to the CWMS
    TSID interval before being passed to timeseries_df_to_json().
    """

    start = pd.Timestamp("2026-09-18T00:00:00Z")

    datetimes = pd.date_range(
        start=start,
        periods=incoming_count,
        freq=incoming_freq,
    )

    values = list(range(1, incoming_count + 1))

    station_number = "00000001"
    parameter_code = "00060"

    ts_id = f"LOC.PRM.X.{target_interval}.0.0"

    usgs_ts = _build_new_api_usgs_ts(
        ts_id=ts_id,
        usgs_station_number=station_number,
        usgs_parameter=parameter_code,
        time_series_id=pd.NA,
    )

    usgs_data = _build_new_api_usgs_data(
        station_number=station_number,
        parameter_code=parameter_code,
        datetimes=datetimes,
        values=values,
    )

    captured = {
        "data_frames": [],
        "store_payloads": [],
    }

    def fake_timeseries_df_to_json(data, ts_id, units, office_id):
        captured["data_frames"].append(data.copy())

        return {
            "ts-id": ts_id,
            "units": units,
            "office-id": office_id,
        }

    def fake_store_timeseries(data, **kwargs):
        captured["store_payloads"].append(data)

    import cwmscli.usgs.getusgs_cda as module

    monkeypatch.setattr(
        module.cwms,
        "timeseries_df_to_json",
        fake_timeseries_df_to_json,
    )

    monkeypatch.setattr(
        module.cwms,
        "store_timeseries",
        fake_store_timeseries,
    )

    CWMS_writeData(
        usgs_ts=usgs_ts,
        usgs_data=usgs_data,
        days_back=1,
    )

    assert len(captured["data_frames"]) == 1
    assert len(captured["store_payloads"]) == 1

    df_passed = captured["data_frames"][0]

    assert len(df_passed) == expected_count

    passed_times = pd.to_datetime(
        df_passed["date-time"],
        utc=True,
    ).tolist()

    passed_values = df_passed["value"].astype(int).tolist()

    if incoming_freq == "15min":
        assert passed_times == list(datetimes)
        assert passed_values == values

    else:
        expected_times = pd.date_range(
            start=datetimes[0],
            periods=expected_count,
            freq="15min",
        ).tolist()

        assert passed_times == expected_times

        step = int(
            pd.to_timedelta("15min")
            / pd.to_timedelta(incoming_freq)
        )

        assert passed_values == values[::step]


def test_cwms_write_data_selects_explicit_timeseries_id(
    monkeypatch,
):
    """
    Verify that a non-null CWMS alias selects only the matching new-USGS
    time_series_id from a larger response DataFrame.
    """

    station_number = "00000001"
    parameter_code = "00060"

    requested_time_series_id = (
        "f38a57ccac5a426e8388b8507fa9bbce"
    )

    ts_id = "LOC.PRM.X.15Minutes.0.0"

    usgs_ts = _build_new_api_usgs_ts(
        ts_id=ts_id,
        usgs_station_number=station_number,
        usgs_parameter=parameter_code,
        time_series_id=requested_time_series_id,
    )

    datetimes = pd.date_range(
        start=pd.Timestamp("2026-09-18T00:00:00Z"),
        periods=2,
        freq="15min",
    )

    requested_data = _build_new_api_usgs_data(
        station_number=station_number,
        parameter_code=parameter_code,
        datetimes=datetimes,
        values=[10.0, 20.0],
        time_series_id=requested_time_series_id,
    )

    unrelated_data = _build_new_api_usgs_data(
        station_number=station_number,
        parameter_code=parameter_code,
        datetimes=datetimes,
        values=[999.0, 999.0],
        time_series_id="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    )

    usgs_data = pd.concat(
        [
            requested_data,
            unrelated_data,
        ],
        ignore_index=True,
    )

    captured = {}

    def fake_timeseries_df_to_json(data, ts_id, units, office_id):
        captured["data"] = data.copy()
        captured["ts_id"] = ts_id
        captured["units"] = units
        captured["office_id"] = office_id

        return {"stored": True}

    import cwmscli.usgs.getusgs_cda as module

    monkeypatch.setattr(
        module.cwms,
        "timeseries_df_to_json",
        fake_timeseries_df_to_json,
    )

    monkeypatch.setattr(
        module.cwms,
        "store_timeseries",
        lambda data, **kwargs: None,
    )

    CWMS_writeData(
        usgs_ts=usgs_ts,
        usgs_data=usgs_data,
        days_back=1,
    )

    assert captured["ts_id"] == ts_id
    assert captured["units"] == "ft3/s"
    assert captured["office_id"] == "SPK"

    assert captured["data"]["value"].tolist() == [
        10.0,
        20.0,
    ]


def test_cwms_write_data_does_not_write_null_alias_with_multiple_ids(
    monkeypatch,
):
    """
    A null alias is valid only when station + parameter returns one USGS
    time_series_id. Multiple IDs must not be written automatically.
    """

    station_number = "00000001"
    parameter_code = "00060"

    ts_id = "LOC.PRM.X.15Minutes.0.0"

    usgs_ts = _build_new_api_usgs_ts(
        ts_id=ts_id,
        usgs_station_number=station_number,
        usgs_parameter=parameter_code,
        time_series_id=pd.NA,
    )

    datetimes = pd.date_range(
        start=pd.Timestamp("2026-09-18T00:00:00Z"),
        periods=2,
        freq="15min",
    )

    first_series = _build_new_api_usgs_data(
        station_number=station_number,
        parameter_code=parameter_code,
        datetimes=datetimes,
        values=[100.0, 110.0],
        time_series_id="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )

    second_series = _build_new_api_usgs_data(
        station_number=station_number,
        parameter_code=parameter_code,
        datetimes=datetimes,
        values=[0.0, 0.0],
        time_series_id="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    )

    usgs_data = pd.concat(
        [
            first_series,
            second_series,
        ],
        ignore_index=True,
    )

    captured = {
        "timeseries_json_calls": 0,
        "store_calls": 0,
    }

    def fake_timeseries_df_to_json(*args, **kwargs):
        captured["timeseries_json_calls"] += 1
        return {"stored": True}

    def fake_store_timeseries(*args, **kwargs):
        captured["store_calls"] += 1

    import cwmscli.usgs.getusgs_cda as module

    monkeypatch.setattr(
        module.cwms,
        "timeseries_df_to_json",
        fake_timeseries_df_to_json,
    )

    monkeypatch.setattr(
        module.cwms,
        "store_timeseries",
        fake_store_timeseries,
    )

    CWMS_writeData(
        usgs_ts=usgs_ts,
        usgs_data=usgs_data,
        days_back=1,
    )

    assert captured["timeseries_json_calls"] == 0
    assert captured["store_calls"] == 0


def test_cwms_write_data_applies_backfill_version(
    monkeypatch,
):
    station_number = "00000001"
    parameter_code = "00060"

    original_ts_id = "LOC.PRM.X.15Minutes.0.Raw-USGS"

    usgs_ts = _build_new_api_usgs_ts(
        ts_id=original_ts_id,
        usgs_station_number=station_number,
        usgs_parameter=parameter_code,
        time_series_id=pd.NA,
    )

    datetimes = pd.date_range(
        start=pd.Timestamp("2026-09-18T00:00:00Z"),
        periods=2,
        freq="15min",
    )

    usgs_data = _build_new_api_usgs_data(
        station_number=station_number,
        parameter_code=parameter_code,
        datetimes=datetimes,
        values=[100.0, 110.0],
    )

    captured = {}

    def fake_timeseries_df_to_json(data, ts_id, units, office_id):
        captured["ts_id"] = ts_id
        return {"stored": True}

    import cwmscli.usgs.getusgs_cda as module

    monkeypatch.setattr(
        module.cwms,
        "timeseries_df_to_json",
        fake_timeseries_df_to_json,
    )

    monkeypatch.setattr(
        module.cwms,
        "store_timeseries",
        lambda data, **kwargs: None,
    )

    CWMS_writeData(
        usgs_ts=usgs_ts,
        usgs_data=usgs_data,
        days_back=1,
        backfill_version="Rev-USGS",
    )

    assert captured["ts_id"] == (
        "LOC.PRM.X.15Minutes.0.Rev-USGS"
    )


def test_resample_helper_direct():
    start = pd.Timestamp("2026-09-18T00:00:00")

    datetimes = pd.date_range(
        start=start,
        periods=9,
        freq="5min",
    )

    values_df = pd.DataFrame(
        {
            "date-time": datetimes,
            "value": list(range(1, 10)),
            "quality-code": [0] * 9,
        }
    )

    ts_id = "LOC.PRM.X.15Minutes.0.0"

    result = resample_to_tsid_interval(
        values_df,
        ts_id,
    )

    assert len(result) == 3

    assert pd.to_datetime(result["date-time"]).tolist() == (
        pd.date_range(
            start=datetimes[0],
            periods=3,
            freq="15min",
        ).tolist()
    )

    assert result["value"].tolist() == [
        1,
        4,
        7,
    ]


@pytest.mark.parametrize(
    "interval_segment",
    [
        "~15Minutes",
        "0",
    ],
)
def test_resample_helper_irregular_interval_does_not_resample(
    interval_segment,
):
    start = pd.Timestamp("2026-09-18T00:00:00")

    datetimes = pd.date_range(
        start=start,
        periods=3,
        freq="5min",
    )

    values_df = pd.DataFrame(
        {
            "date-time": datetimes,
            "value": [1, 2, 3],
            "quality-code": [0, 0, 0],
        }
    )

    ts_id = f"LOC.PRM.X.{interval_segment}.0.0"

    result = resample_to_tsid_interval(
        values_df,
        ts_id,
    )

    assert len(result) == len(values_df)

    assert pd.to_datetime(result["date-time"]).tolist() == (
        list(datetimes)
    )

    assert result["value"].tolist() == [
        1,
        2,
        3,
    ]


def test_resample_helper_preserves_first_non_null_value():
    start = pd.Timestamp("2026-09-18T00:00:00")

    datetimes = pd.date_range(
        start=start,
        periods=6,
        freq="5min",
    )

    values_df = pd.DataFrame(
        {
            "date-time": datetimes,
            "value": [
                1.0,
                np.nan,
                3.0,
                4.0,
                np.nan,
                6.0,
            ],
            "quality-code": [0] * 6,
        }
    )

    result = resample_to_tsid_interval(
        values_df,
        "LOC.PRM.X.15Minutes.0.0",
    )

    assert len(result) == 2

    assert pd.to_datetime(result["date-time"]).tolist() == (
        pd.date_range(
            start=datetimes[0],
            periods=2,
            freq="15min",
        ).tolist()
    )

    assert result["value"].tolist() == [
        1.0,
        4.0,
    ]


def test_resample_helper_hours():
    start = pd.Timestamp("2026-09-18T00:00:00")

    datetimes = pd.date_range(
        start=start,
        periods=4,
        freq="30min",
    )

    values_df = pd.DataFrame(
        {
            "date-time": datetimes,
            "value": [10, 11, 20, 21],
            "quality-code": [0, 0, 0, 0],
        }
    )

    result = resample_to_tsid_interval(
        values_df,
        "LOC.PRM.X.1Hours.0.0",
    )

    assert len(result) == 2

    assert pd.to_datetime(result["date-time"]).tolist() == (
        pd.date_range(
            start=datetimes[0],
            periods=2,
            freq="1h",
        ).tolist()
    )

    assert result["value"].tolist() == [
        10,
        20,
    ]


def test_fifteen_minute_input_and_target_is_unchanged():
    start = pd.Timestamp("2026-09-18T00:00:00")

    datetimes = pd.date_range(
        start=start,
        periods=4,
        freq="15min",
    )

    values_df = pd.DataFrame(
        {
            "date-time": datetimes,
            "value": [5, 6, 7, 8],
            "quality-code": [0, 0, 0, 0],
        }
    )

    result = resample_to_tsid_interval(
        values_df,
        "LOC.PRM.X.15Minutes.0.0",
    )

    assert len(result) == len(values_df)

    assert pd.to_datetime(result["date-time"]).tolist() == (
        list(datetimes)
    )

    assert result["value"].tolist() == [
        5,
        6,
        7,
        8,
    ]


def test_missing_datetime_rows_are_dropped_before_resample():
    start = pd.Timestamp("2026-09-18T00:00:00")

    datetimes = pd.date_range(
        start=start,
        periods=6,
        freq="5min",
    )

    values_df = pd.DataFrame(
        {
            "date-time": [
                datetimes[0],
                datetimes[1],
                None,
                datetimes[3],
                datetimes[4],
                datetimes[5],
            ],
            "value": [1, 2, 3, 4, 5, 6],
            "quality-code": [0] * 6,
        }
    )

    result = resample_to_tsid_interval(
        values_df,
        "LOC.PRM.X.15Minutes.0.0",
    )

    assert len(result) == 2


def test_duplicate_timestamps_keep_first_value():
    start = pd.Timestamp("2026-09-18T00:00:00")

    values_df = pd.DataFrame(
        {
            "date-time": [
                start,
                start,
                start + pd.Timedelta("15min"),
            ],
            "value": [
                9,
                99,
                10,
            ],
            "quality-code": [0, 0, 0],
        }
    )

    result = resample_to_tsid_interval(
        values_df,
        "LOC.PRM.X.15Minutes.0.0",
    )

    assert len(result) == 2

    assert result["value"].astype(int).tolist() == [
        9,
        10,
    ]