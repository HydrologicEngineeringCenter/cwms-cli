from cwmscli.utils.intervals import (
    FIXED_INTERVALS_BY_SECONDS,
    REGULAR_INTERVAL_PARAMETERS,
)


def test_fixed_intervals_by_seconds_uses_regular_cwms_names():
    assert FIXED_INTERVALS_BY_SECONDS[60] == "1Minute"
    assert FIXED_INTERVALS_BY_SECONDS[3600] == "1Hour"
    assert FIXED_INTERVALS_BY_SECONDS[604800] == "1Week"
    assert set(FIXED_INTERVALS_BY_SECONDS.values()) <= set(REGULAR_INTERVAL_PARAMETERS)


def test_fixed_intervals_exclude_calendar_lengths():
    assert "1Month" not in FIXED_INTERVALS_BY_SECONDS.values()
    assert "1Year" not in FIXED_INTERVALS_BY_SECONDS.values()
    assert "1Decade" not in FIXED_INTERVALS_BY_SECONDS.values()
