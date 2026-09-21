import numpy as np
import pandas as pd
import pytest

from cwmscli.usgs.getusgs_cda import CWMS_writeData, resample_to_tsid_interval


def _make_usgs_row(values_list, unit_code="cfs"):
    return {
        "values": [
            {"value": values_list},
        ],
        "variable": {"noDataValue": -999999, "unit": {"unitCode": unit_code}},
    }


def _build_usgs_data(index_key, datetimes, values):
    # build the nested structure expected by CWMS_writeData
    value_records = [
        {"dateTime": dt.isoformat(), "value": str(val), "qualifiers": []}
        for dt, val in zip(datetimes, values)
    ]
    usgs_row = _make_usgs_row(value_records)
    df = pd.DataFrame([usgs_row], index=[index_key])
    return df


def _build_usgs_ts_row(ts_id, usgs_st_num, usgs_param, office="SPK"):
    return {
        "timeseries-id": ts_id,
        "USGS_St_Num": usgs_st_num,
        "USGS_PARAMETER": usgs_param,
        "USGS_Method_TS": np.nan,
        "office-id": office,
    }


@pytest.mark.parametrize(
    "incoming_freq,target_interval,incoming_count,expected_count",
    [
        ("15min", "15Minutes", 3, 3),  # incoming 15 -> target 15 -> no resample
        ("5min", "15Minutes", 9, 3),  # incoming 5 -> target 15 -> resample down
    ],
)
def test_resample_behavior(
    monkeypatch, incoming_freq, target_interval, incoming_count, expected_count
):
    # Build times covering a short window
    start = pd.Timestamp("2026-09-18T00:00:00")
    datetimes = pd.date_range(start=start, periods=incoming_count, freq=incoming_freq)
    values = list(range(1, incoming_count + 1))

    usgs_st = "00000001"
    usgs_param = "00060"
    index_key = f"{usgs_st}.{usgs_param}"

    usgs_data = _build_usgs_data(index_key, datetimes, values)

    # Build USGS_ts DataFrame with a TSID that encodes the target interval in the 4th segment
    # e.g. anything.15Minutes.0.0
    ts_id = f"LOC.PRM.X.{target_interval}.0.0"
    usgs_ts = pd.DataFrame([_build_usgs_ts_row(ts_id, usgs_st, usgs_param)])

    captured = {"data_frames": []}

    def fake_timeseries_df_to_json(data, ts_id, units, office_id):
        # capture the DataFrame passed for inspection
        captured["data_frames"].append(data.copy())
        return {"dummy": True}

    def fake_store_timeseries(data, **kwargs):
        # no-op store, capture called payload as well
        captured.setdefault("stores", []).append(data)

    # Patch the cwms functions used by CWMS_writeData
    import cwmscli.usgs.getusgs_cda as module

    monkeypatch.setattr(
        module.cwms, "timeseries_df_to_json", fake_timeseries_df_to_json
    )
    monkeypatch.setattr(module.cwms, "store_timeseries", fake_store_timeseries)

    # Call the writer
    CWMS_writeData(usgs_ts, usgs_data, pd.DataFrame(), days_back=1)

    # Ensure timeseries_df_to_json was called once and inspect the DataFrame
    assert len(captured["data_frames"]) == 1
    df_passed = captured["data_frames"][0]
    # data passed should have expected_count rows after any resample
    assert len(df_passed) == expected_count

    # Check the timestamps and values content
    passed_times = pd.to_datetime(df_passed["date-time"]).tolist()
    passed_values = df_passed["value"].astype(int).tolist()

    if incoming_freq == "15min":
        # should be identical to incoming times/values
        assert passed_times == list(datetimes)
        assert passed_values == values
    else:
        # for 5min -> 15min resample, first value in each 15-min bin should be kept
        target_times = pd.date_range(
            start=datetimes[0], periods=expected_count, freq="15min"
        ).tolist()
        assert passed_times == target_times
        # pick every (target interval / incoming interval)th value from original list
        step = int(pd.to_timedelta("15min") / pd.to_timedelta(incoming_freq))
        expected_values = values[::step]
        assert passed_values == expected_values


def test_resample_helper_direct():
    start = pd.Timestamp("2026-09-18T00:00:00")
    datetimes = pd.date_range(start=start, periods=9, freq="5min")
    values = list(range(1, 10))

    value_records = [
        {"dateTime": dt.isoformat(), "value": str(val), "qualifiers": []}
        for dt, val in zip(datetimes, values)
    ]
    values_df = pd.DataFrame(value_records)
    values_df = values_df.rename(columns={"dateTime": "date-time"})

    ts_id = "LOC.PRM.X.15Minutes.0.0"
    res = resample_to_tsid_interval(values_df, ts_id)

    # expect 3 rows at 15min frequency
    assert len(res) == 3
    assert (
        pd.to_datetime(res["date-time"]).tolist()
        == pd.date_range(start=datetimes[0], periods=3, freq="15min").tolist()
    )


@pytest.mark.parametrize("segment", ["~15Minutes", "0"])
def test_resample_helper_irregular_no_resample(segment):
    # when TSID encodes irregular interval, helper should return original values
    start = pd.Timestamp("2026-09-18T00:00:00")
    datetimes = pd.date_range(start=start, periods=3, freq="5min")
    values = [1, 2, 3]

    value_records = [
        {"dateTime": dt.isoformat(), "value": val, "qualifiers": []}
        for dt, val in zip(datetimes, values)
    ]
    values_df = pd.DataFrame(value_records).rename(columns={"dateTime": "date-time"})

    ts_id = f"LOC.PRM.X.{segment}.0.0"
    res = resample_to_tsid_interval(values_df, ts_id)
    assert len(res) == len(values_df)
    assert pd.to_datetime(res["date-time"]).tolist() == list(datetimes)


def test_resample_helper_preserves_nans():
    start = pd.Timestamp("2026-09-18T00:00:00")
    datetimes = pd.date_range(start=start, periods=6, freq="5min")
    values = [1, np.nan, 3, 4, np.nan, 6]

    value_records = [
        {"dateTime": dt.isoformat(), "value": val, "qualifiers": []}
        for dt, val in zip(datetimes, values)
    ]
    values_df = pd.DataFrame(value_records).rename(columns={"dateTime": "date-time"})

    ts_id = "LOC.PRM.X.15Minutes.0.0"
    res = resample_to_tsid_interval(values_df, ts_id)

    # 6 rows at 5min -> 2 rows at 15min; first values in each 15-min bin are 1 and 4
    assert len(res) == 2
    assert (
        pd.to_datetime(res["date-time"]).tolist()
        == pd.date_range(start=datetimes[0], periods=2, freq="15min").tolist()
    )
    assert res["value"].tolist() == [1.0, 4.0]


def test_resample_helper_hours():
    # incoming 30min, target 1Hours
    start = pd.Timestamp("2026-09-18T00:00:00")
    datetimes = pd.date_range(start=start, periods=4, freq="30min")
    values = [10, 11, 20, 21]

    value_records = [
        {"dateTime": dt.isoformat(), "value": val, "qualifiers": []}
        for dt, val in zip(datetimes, values)
    ]
    values_df = pd.DataFrame(value_records).rename(columns={"dateTime": "date-time"})

    ts_id = "LOC.PRM.X.1Hours.0.0"
    res = resample_to_tsid_interval(values_df, ts_id)

    # expect 2 rows at hourly intervals: 00:00 and 01:00, values are 10 and 20
    assert len(res) == 2
    assert (
        pd.to_datetime(res["date-time"]).tolist()
        == pd.date_range(start=datetimes[0], periods=2, freq="1h").tolist()
    )
    assert res["value"].tolist() == [10, 20]


def test_15min_incoming_and_target_noop():
    # incoming 15min data and TSID target 15Minutes should not resample
    start = pd.Timestamp("2026-09-18T00:00:00")
    datetimes = pd.date_range(start=start, periods=4, freq="15min")
    values = [5, 6, 7, 8]

    value_records = [
        {"dateTime": dt.isoformat(), "value": val, "qualifiers": []}
        for dt, val in zip(datetimes, values)
    ]
    values_df = pd.DataFrame(value_records).rename(columns={"dateTime": "date-time"})

    ts_id = "LOC.PRM.X.15Minutes.0.0"
    res = resample_to_tsid_interval(values_df, ts_id)

    assert len(res) == len(values_df)
    assert pd.to_datetime(res["date-time"]).tolist() == list(datetimes)
    assert res["value"].astype(int).tolist() == values


def test_missing_datetime_rows_are_dropped():
    start = pd.Timestamp("2026-09-18T00:00:00")
    # create 5min data with one row missing dateTime
    datetimes = pd.date_range(start, periods=6, freq="5min")
    values = [1, 2, 3, 4, 5, 6]
    records = []
    for i, (dt, v) in enumerate(zip(datetimes, values)):
        if i == 2:
            # third row missing timestamp
            records.append({"dateTime": "", "value": str(v), "qualifiers": []})
        else:
            records.append(
                {"dateTime": dt.isoformat(), "value": str(v), "qualifiers": []}
            )

    df_in = pd.DataFrame(records).rename(columns={"dateTime": "date-time"})
    ts_id = "LOC.PRM.X.15Minutes.0.0"
    res = resample_to_tsid_interval(df_in, ts_id)

    # original had 6 rows, one dropped => 5 rows at 5min; resampled to 15min -> 2 rows
    assert len(res) == 2


def test_duplicate_timestamps_keep_first():
    start = pd.Timestamp("2026-09-18T00:00:00")
    datetimes = [start, start, start + pd.Timedelta("15min")]  # duplicate first two
    values = [9, 99, 10]
    records = [
        {"dateTime": dt.isoformat(), "value": str(v), "qualifiers": []}
        for dt, v in zip(datetimes, values)
    ]
    df_in = pd.DataFrame(records).rename(columns={"dateTime": "date-time"})
    ts_id = "LOC.PRM.X.15Minutes.0.0"
    res = resample_to_tsid_interval(df_in, ts_id)

    # duplicates at the same timestamp should keep the first (9) and then 15min value 10
    assert len(res) == 2
    assert res["value"].astype(int).tolist() == [9, 10]
