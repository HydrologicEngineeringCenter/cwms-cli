from datetime import datetime, timedelta

import pytest

from ..utils.dateutils import determine_interval, parse_date, safe_zoneinfo


def test_parse_date_valid_formats():
    tz = safe_zoneinfo("UTC")
    expected = datetime(2025, 3, 25, 14, 30, tzinfo=tz)
    assert parse_date("03/25/2025 14:30:00") == expected
    assert parse_date("03/25/2025 14:30") == expected
    assert parse_date("03/25/2025 14") == datetime(2025, 3, 25, 14, tzinfo=tz)


def test_parse_date_invalid_format():
    with pytest.raises(ValueError):
        parse_date("25-03-2025")


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
