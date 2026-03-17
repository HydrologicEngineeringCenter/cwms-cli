from datetime import datetime, timedelta

import pytest

from cwmscli.utils.intervals import ALL_INTERVAL_PARAMETERS

from ..utils.dateutils import (
    determine_interval,
    interval_parameter_to_seconds,
    parse_date,
    round_datetime_to_interval,
    safe_zoneinfo,
)


def test_parse_date_valid_formats():
    tz = safe_zoneinfo("UTC")
    expected = datetime(2025, 3, 25, 14, 30, tzinfo=tz)
    assert parse_date("03/25/2025 14:30:00") == expected
    assert parse_date("03/25/2025 14:30") == expected
    assert parse_date("03/25/2025 14") == datetime(2025, 3, 25, 14, tzinfo=tz)


def test_parse_date_invalid_format():
    with pytest.raises(ValueError):
        parse_date("25-03-2025")


def test_parse_date_uses_single_user_format():
    tz = safe_zoneinfo("UTC")
    expected = datetime(2025, 3, 25, 14, 30, tzinfo=tz)
    assert (
        parse_date(
            "2025/03/25 14:30", date_format="%Y/%m/%d %H:%M", tz_str="UTC"
        )
        == expected
    )


def test_parse_date_uses_ordered_format_list():
    tz = safe_zoneinfo("UTC")
    expected = datetime(2025, 3, 25, 14, 30, tzinfo=tz)
    assert (
        parse_date(
            "2025-03-25 14:30",
            date_format=["%m/%d/%Y %H:%M", "%Y-%m-%d %H:%M"],
            tz_str="UTC",
        )
        == expected
    )


def test_interval_parameter_to_seconds():
    assert interval_parameter_to_seconds("15Minutes") == 900
    assert interval_parameter_to_seconds("1Hour") == 3600
    assert interval_parameter_to_seconds("1Day") == 86400


def test_interval_parameter_list_includes_schema_values():
    assert "1Week" in ALL_INTERVAL_PARAMETERS
    assert "~15Minutes" in ALL_INTERVAL_PARAMETERS
    assert "1Decade" in ALL_INTERVAL_PARAMETERS


def test_interval_parameter_to_seconds_rejects_irregular_interval():
    with pytest.raises(ValueError):
        interval_parameter_to_seconds("~15Minutes")


def test_round_datetime_to_interval_hour():
    tz = safe_zoneinfo("UTC")
    dt = datetime(2025, 3, 25, 14, 31, tzinfo=tz)
    assert round_datetime_to_interval(dt, "1Hour") == datetime(
        2025, 3, 25, 15, 0, tzinfo=tz
    )


def test_round_datetime_to_interval_minutes():
    tz = safe_zoneinfo("UTC")
    dt = datetime(2025, 3, 25, 14, 8, tzinfo=tz)
    assert round_datetime_to_interval(dt, "15Minutes") == datetime(
        2025, 3, 25, 14, 15, tzinfo=tz
    )


def test_round_datetime_to_interval_5_minutes():
    tz = safe_zoneinfo("UTC")
    dt = datetime(2025, 3, 25, 14, 3, 31, tzinfo=tz)
    assert round_datetime_to_interval(dt, "5Minutes") == datetime(
        2025, 3, 25, 14, 5, tzinfo=tz
    )


def test_round_datetime_to_interval_30_minutes():
    tz = safe_zoneinfo("UTC")
    dt = datetime(2025, 3, 25, 14, 16, tzinfo=tz)
    assert round_datetime_to_interval(dt, "30Minutes") == datetime(
        2025, 3, 25, 14, 30, tzinfo=tz
    )


def test_determine_interval_regular_spacing():
    now = datetime(2025, 3, 25, 14, 30, tzinfo=safe_zoneinfo("UTC"))
    interval = 900  # 15 minutes
    csv_data = {
        int((now + timedelta(seconds=i * interval)).timestamp()): [] for i in range(5)
    }
    assert determine_interval(csv_data) == 900


def test_determine_interval_mixed_spacing():
    now = datetime(2025, 3, 25, 14, 30, tzinfo=safe_zoneinfo("UTC"))
    timestamps = [
        now,
        now + timedelta(minutes=15),
        now + timedelta(minutes=30),
        now + timedelta(minutes=60),  # outlier
        now + timedelta(minutes=45),
    ]
    csv_data = {int(dt.timestamp()): [] for dt in timestamps}
    assert determine_interval(csv_data) == 900


def test_determine_interval_duplicate_timestamps():
    now = datetime(2025, 3, 25, 14, 30, tzinfo=safe_zoneinfo("UTC"))
    timestamps = [
        now,
        now + timedelta(minutes=15),
        now + timedelta(minutes=15),  # duplicate
        now + timedelta(minutes=30),
    ]
    csv_data = {int(dt.timestamp()): [] for dt in timestamps}
    assert determine_interval(csv_data) == 900


def test_determine_interval_missing_values():
    now = datetime(2025, 3, 25, 14, 30, tzinfo=safe_zoneinfo("UTC"))
    csv_data = {
        int((now + timedelta(minutes=15 * i)).timestamp()): []
        for i in [0, 1, 3, 4]  # skip index 2 (30-minute gap)
    }
    assert determine_interval(csv_data) == 900


def test_determine_interval_insufficient_data():
    now = datetime(2025, 3, 25, 14, 30, tzinfo=safe_zoneinfo("UTC"))
    csv_data = {int(now.timestamp()): []}  # only one row
    with pytest.raises(ValueError):
        determine_interval(csv_data)
