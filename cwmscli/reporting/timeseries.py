import calendar
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

import click

from cwmscli.reporting.config import Config
from cwmscli.reporting.sources import fetch_timeseries_df
from cwmscli.reporting.utils.date import parse_when


def _expand(value: Optional[str], **kwargs) -> Optional[str]:
    if not value:
        return None
    try:
        return value.format(**kwargs)
    except Exception:
        return value


def _parse_month(value: str, tz_name: str) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m", "%b %Y", "%B %Y"):
        try:
            parsed = datetime.strptime(text, fmt)
            return datetime(parsed.year, parsed.month, 1, tzinfo=ZoneInfo(tz_name))
        except ValueError:
            pass
    raise click.BadParameter("dataset.month must be YYYY-MM, Mon YYYY, or Month YYYY.")


def _coerce_when(value: Any, tz_name: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = parse_when(str(value), tz_name)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(tz_name))
    return parsed


def _utc_timestamp(value: Any, tz_name: str):
    import pandas as pd

    return pd.Timestamp(_coerce_when(value, tz_name)).tz_convert("UTC")


def _frame_between(df, begin: Optional[Any], end: Optional[Any], tz_name: str):
    if df.empty:
        return df
    out = df
    if begin is not None:
        out = out[out["date-time"] >= _utc_timestamp(begin, tz_name)]
    if end is not None:
        out = out[out["date-time"] <= _utc_timestamp(end, tz_name)]
    return out


def _value_at(df, when: Any, tz_name: str) -> Optional[float]:
    if df.empty:
        return None
    timestamp = _utc_timestamp(when, tz_name)
    matches = df[df["date-time"].eq(timestamp)]
    if matches.empty:
        return None
    value = matches.iloc[-1]["value"]
    return None if value is None else float(value)


def _format_float(value: Optional[float], precision: int, missing: str = "--") -> str:
    if value is None:
        return missing
    return f"{float(value):.{precision}f}"


def _format_int(value: Optional[float], missing: str = "--") -> str:
    if value is None:
        return missing
    return f"{int(round(float(value)))}"


def _month_context(month_start: Optional[datetime]) -> Optional[Dict[str, Any]]:
    if month_start is None:
        return None
    days = calendar.monthrange(month_start.year, month_start.month)[1]
    month_end = month_start + timedelta(days=days)
    return {
        "start": month_start,
        "end": month_end,
        "days": days,
        "label": month_start.strftime("%B %Y").upper(),
        "abbr": month_start.strftime("%b").upper(),
        "year_two": str(month_start.year)[-2:],
    }


def _series_items(raw: Any) -> Dict[str, Dict[str, Any]]:
    if isinstance(raw, dict):
        return {str(key): dict(value or {}) for key, value in raw.items()}
    if isinstance(raw, list):
        items = {}
        for index, value in enumerate(raw):
            if not isinstance(value, dict):
                raise click.BadParameter(f"Invalid series entry: {value!r}")
            key = value.get("key") or value.get("name") or f"series_{index + 1}"
            items[str(key)] = dict(value)
        return items
    if raw:
        raise click.BadParameter("dataset.series must be a mapping or list.")
    return {}


def build_time_series_context(
    config: Config, begin: Optional[datetime], end: Optional[datetime]
) -> Dict[str, Any]:
    if config.dataset.kind != "time_series":
        raise click.BadParameter(
            "time series context requires dataset.kind='time_series'."
        )

    options = dict(config.dataset.options or {})
    tz_name = config.time_zone or "UTC"
    project = str(options.get("project") or "").strip()
    timeout_seconds = float(options.get("request_timeout_seconds") or 12)
    month = _month_context(_parse_month(str(options.get("month") or ""), tz_name))
    if month and begin is None:
        begin = month["start"] - timedelta(days=1)
    if month and end is None:
        end = month["end"] + timedelta(days=1)

    series_specs = _series_items(options.get("series") or {})
    if not series_specs:
        raise click.UsageError("No 'dataset.series' configured in YAML.")

    frames = {}
    requested_series = {}
    for key, spec in series_specs.items():
        tsid = _expand(str(spec.get("tsid") or ""), project=project)
        if not tsid:
            raise click.BadParameter(f"Series '{key}' must define 'tsid'.")
        unit = str(spec.get("unit") or config.default_unit)
        series_begin = (
            parse_when(str(spec["begin"]), tz_name)
            if spec.get("begin") is not None
            else begin
        )
        series_end = (
            parse_when(str(spec["end"]), tz_name)
            if spec.get("end") is not None
            else end
        )
        frames[key] = fetch_timeseries_df(
            [tsid],
            str(spec.get("office") or config.office),
            unit,
            series_begin,
            series_end,
            timeout_seconds,
        )
        requested_series[key] = {
            **spec,
            "tsid": tsid,
            "unit": unit,
            "begin": series_begin,
            "end": series_end,
        }

    def frame(key: str):
        return frames.get(key)

    def values_between(key: str, range_begin=None, range_end=None):
        df = frames.get(key)
        if df is None:
            return []
        out = _frame_between(df, range_begin, range_end, tz_name)
        return out.to_dict("records")

    def value_at(key: str, when, default=None):
        df = frames.get(key)
        if df is None:
            return default
        value = _value_at(df, when, tz_name)
        return default if value is None else value

    def sum_values(key: str, range_begin=None, range_end=None):
        df = frames.get(key)
        if df is None:
            return 0
        out = _frame_between(df, range_begin, range_end, tz_name)
        return float(out["value"].dropna().sum()) if not out.empty else 0

    def min_row(key: str, range_begin=None, range_end=None, tie: str = "first"):
        df = frames.get(key)
        if df is None:
            return None
        out = _frame_between(df, range_begin, range_end, tz_name)
        if out.empty:
            return None
        value = out["value"].min()
        matches = out[out["value"].eq(value)]
        row = matches.iloc[-1] if tie == "last" else matches.iloc[0]
        return row.to_dict()

    def max_row(key: str, range_begin=None, range_end=None, tie: str = "first"):
        df = frames.get(key)
        if df is None:
            return None
        out = _frame_between(df, range_begin, range_end, tz_name)
        if out.empty:
            return None
        value = out["value"].max()
        matches = out[out["value"].eq(value)]
        row = matches.iloc[-1] if tie == "last" else matches.iloc[0]
        return row.to_dict()

    def add_days(value, days: int):
        return _coerce_when(value, tz_name) + timedelta(days=int(days))

    def at_time(value, hour: int = 0, minute: int = 0):
        return _coerce_when(value, tz_name).replace(hour=int(hour), minute=int(minute))

    def local_day(value) -> int:
        return _coerce_when(value, tz_name).astimezone(ZoneInfo(tz_name)).day

    return {
        "kind": "time_series",
        "project": project,
        "options": options,
        "month": month,
        "series": requested_series,
        "series_frames": frames,
        "frame": frame,
        "values_between": values_between,
        "value_at": value_at,
        "sum_values": sum_values,
        "min_row": min_row,
        "max_row": max_row,
        "add_days": add_days,
        "at_time": at_time,
        "local_day": local_day,
        "fmt_float": _format_float,
        "fmt_int": _format_int,
        "center": lambda text, width=74: str(text).center(int(width)).rstrip(),
        "center_legacy_title": lambda text: str(text)
        .center(72 if len(str(text)) % 2 == 0 else 73)
        .rstrip(),
        "is_even": lambda value: int(value) % 2 == 0,
        "round_int": lambda value: (
            int(round(float(value))) if value is not None else None
        ),
        "base_end": end or (month["end"] if month else None),
        "rows": [],
        "columns": [],
        "data": {},
    }
