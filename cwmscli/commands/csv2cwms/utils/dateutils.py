import logging
from collections import Counter
from datetime import datetime, timezone
from typing import List

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:
    # Python < 3.9 does not support zoneinfo
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception

logger = logging.getLogger(__name__)

DATE_STRINGS = [
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y %H",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%dT%H",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H",
]


def safe_zoneinfo(key: str):
    """
    Attempts to return ZoneInfo(key); falls back to UTC if unavailable.
    """
    if ZoneInfo is None:
        return timezone.utc  # fallback for very old Python

    try:
        return ZoneInfo(key)
    except ZoneInfoNotFoundError:
        return timezone.utc


def parse_date(date, tz_str="UTC", date_format: str = "") -> datetime:
    """Handle all date types seen in hydropower files
    NOTE: TimeZone naive - assumes all timestamps are in the same timezone
    Args:
        date (str): Date string to parse
    """
    if isinstance(date, int):
        return datetime.fromtimestamp(date, tz=safe_zoneinfo(tz_str))

    if isinstance(date_format, str):
        # Handle comma-separated list of formats
        if date_format.find(",") >= 0:
            date_format = [fmt.strip() for fmt in date_format.split(",") if fmt.strip()]
        date_format = [date_format]

    # Include the user-specified date format first, if provided
    for idx, fmt in enumerate(date_format + DATE_STRINGS):
        try:
            if not fmt:
                continue
            dt_naive = datetime.strptime(date, fmt)
            if idx > 0:
                # Only log if using a fallback format
                if not date_format:
                    logger.warning(
                        f"Using fallback date format '{fmt}' for date '{date}'. No user-specified format was provided."
                    )
                else:
                    logger.warning(
                        f"Using fallback date format '{fmt}' for date '{date}'. The user-specified format is '{date_format}'."
                    )
            return dt_naive.replace(tzinfo=safe_zoneinfo(tz_str))
        except ValueError:
            continue
    raise ValueError(f"Invalid date format: {date}")


def determine_interval(csv_data: List[list], sample_size=10) -> int:
    """
    Determine the most common interval (in seconds) between timestamps in the first few rows of CSV data.
    Args:
        `csv_data` is the raw list-of-lists from your CSV (NOT including header).
        `sample_size` is the number of rows to sample from the CSV data.
    Returns:
        [int] The most common interval between timestamps in seconds

    """

    timestamps = []
    dates = list(csv_data.keys())
    sample_idx = min(sample_size, len(dates) - 1)
    if sample_idx < 0:
        raise ValueError("No data found in CSV file for the given lookback period.")
    for row in dates[0:sample_idx]:
        try:
            timestamps.append(parse_date(row))
        except Exception as err:
            continue

    if len(timestamps) < 2:
        raise ValueError("Not enough valid timestamps to determine interval.")

    diffs = [int((b - a).total_seconds()) for a, b in zip(timestamps, timestamps[1:])]
    most_common = Counter(diffs).most_common(1)[0][0]
    return most_common
