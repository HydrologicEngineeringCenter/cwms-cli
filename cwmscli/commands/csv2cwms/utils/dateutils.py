import logging
import math
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import List, Sequence

from cwmscli.utils.intervals import ALL_INTERVAL_PARAMETERS

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
INTERVAL_PARAMETER_RE = re.compile(
    r"^(?:"
    + "|".join(sorted((re.escape(value) for value in ALL_INTERVAL_PARAMETERS), key=len, reverse=True))
    + r")$",
    re.IGNORECASE,
)
INTERVAL_PARAMETER_COMPONENT_RE = re.compile(
    r"^(?P<count>\d+)(?P<unit>minute|minutes|hour|hours|day|days|week|weeks|month|months|year|years|decade|decades)$",
    re.IGNORECASE,
)
UNIT_SECONDS = {
    "minute": 60,
    "hour": 3600,
    "day": 86400,
}


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


def parse_interval_parameter(interval_parameter: str) -> tuple[int, str]:
    normalized = interval_parameter.strip()
    if not INTERVAL_PARAMETER_RE.match(normalized):
        raise ValueError(
            f"Unsupported interval parameter '{interval_parameter}'. Expected values like 15Minutes, 1Hour, 1Day, or 1Year."
        )

    if normalized in {"0"} or normalized.startswith("~"):
        raise ValueError(
            f"Interval parameter '{interval_parameter}' is irregular and cannot be used for round_to_nearest."
        )

    match = INTERVAL_PARAMETER_COMPONENT_RE.match(normalized)
    if not match:
        raise ValueError(
            f"Interval parameter '{interval_parameter}' is recognized but not parseable for round_to_nearest."
        )

    count = int(match.group("count"))
    unit = match.group("unit").lower()
    if unit.endswith("s"):
        unit = unit[:-1]
    return count, unit


def interval_parameter_to_seconds(interval_parameter: str) -> int:
    count, unit = parse_interval_parameter(interval_parameter)
    if unit == "week":
        return count * 7 * UNIT_SECONDS["day"]
    if unit == "month":
        return count * 30 * UNIT_SECONDS["day"]
    if unit == "year":
        return count * 365 * UNIT_SECONDS["day"]
    if unit == "decade":
        return count * 10 * 365 * UNIT_SECONDS["day"]
    return count * UNIT_SECONDS[unit]


def round_datetime_to_interval(dt: datetime, interval_parameter: str) -> datetime:
    count, unit = parse_interval_parameter(interval_parameter)

    if unit in {"minute", "hour"}:
        anchor = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        interval_seconds = count * UNIT_SECONDS[unit]
        elapsed = (dt - anchor).total_seconds()
        rounded_seconds = math.floor((elapsed + interval_seconds / 2) / interval_seconds) * interval_seconds
        return anchor + timedelta(seconds=rounded_seconds)

    if unit == "day":
        anchor = datetime(1970, 1, 1, tzinfo=dt.tzinfo)
        interval_days = count
        elapsed_days = (dt - anchor).total_seconds() / UNIT_SECONDS["day"]
        rounded_days = math.floor((elapsed_days + interval_days / 2) / interval_days) * interval_days
        return anchor + timedelta(days=rounded_days)

    if unit == "week":
        anchor = datetime(1970, 1, 5, tzinfo=dt.tzinfo)
        interval_days = count * 7
        elapsed_days = (dt - anchor).total_seconds() / UNIT_SECONDS["day"]
        rounded_days = math.floor((elapsed_days + interval_days / 2) / interval_days) * interval_days
        return anchor + timedelta(days=rounded_days)

    if unit == "month":
        total_months = dt.year * 12 + (dt.month - 1)
        rounded_months = math.floor((total_months + count / 2) / count) * count
        rounded_year = rounded_months // 12
        rounded_month = rounded_months % 12 + 1
        return datetime(rounded_year, rounded_month, 1, tzinfo=dt.tzinfo)

    lower_bucket = ((dt.year - 1) // count) * count + 1
    upper_bucket = lower_bucket + count
    lower_dt = datetime(lower_bucket, 1, 1, tzinfo=dt.tzinfo)
    upper_dt = datetime(upper_bucket, 1, 1, tzinfo=dt.tzinfo)
    midpoint = lower_dt + (upper_dt - lower_dt) / 2
    return upper_dt if dt >= midpoint else lower_dt


def _normalize_date_formats(date_format: str | Sequence[str] | None) -> list[str]:
    if not date_format:
        return []
    if isinstance(date_format, str):
        if "," in date_format:
            return [fmt.strip() for fmt in date_format.split(",") if fmt.strip()]
        return [date_format]
    return [fmt for fmt in date_format if fmt]


def parse_date(date, tz_str="UTC", date_format: str | Sequence[str] | None = None) -> datetime:
    """Handle all date types seen in hydropower files
    NOTE: TimeZone naive - assumes all timestamps are in the same timezone
    Args:
        date (str): Date string to parse
    """
    if isinstance(date, int):
        return datetime.fromtimestamp(date, tz=safe_zoneinfo(tz_str))

    date_formats = _normalize_date_formats(date_format)

    # Include the user-specified date format first, if provided
    for idx, fmt in enumerate(date_formats + DATE_STRINGS):
        try:
            if not fmt:
                continue
            dt_naive = datetime.strptime(date, fmt)
            if idx > 0:
                # Only log if using a fallback format
                if not date_formats:
                    logger.warning(
                        f"Using fallback date format '{fmt}' for date '{date}'. No user-specified format was provided."
                    )
                else:
                    logger.warning(
                        f"Using fallback date format '{fmt}' for date '{date}'. The user-specified format is '{date_formats}'."
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
