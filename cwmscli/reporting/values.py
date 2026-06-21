import math
from typing import Any, Dict, Optional, Tuple


def coerce_cda_datetimes(values):
    import pandas as pd
    from pandas.api.types import is_datetime64_any_dtype

    if is_datetime64_any_dtype(values):
        return pd.to_datetime(values, utc=True, errors="coerce")

    non_null = values.dropna()
    numeric = pd.to_numeric(non_null, errors="coerce")
    if not non_null.empty and numeric.notna().all():
        return pd.to_datetime(
            pd.to_numeric(values, errors="coerce"),
            unit="ms",
            utc=True,
            errors="coerce",
        )
    return pd.to_datetime(values, utc=True, errors="coerce")


def format_report_value(
    value: Any,
    precision: Optional[int],
    missing: str,
    undefined: str,
) -> str:
    if value is None:
        return missing
    try:
        numeric = float(value)
        if math.isnan(numeric) or math.isinf(numeric):
            return undefined
        if precision is None:
            return f"{numeric}"
        return f"{numeric:.{precision}f}"
    except Exception:
        return f"{value}"


def latest_timeseries_values(df) -> Dict[str, Tuple[Any, Any]]:
    name_col = (
        "ts_id" if "ts_id" in df.columns else ("name" if "name" in df.columns else None)
    )
    time_col = (
        "date-time"
        if "date-time" in df.columns
        else ("date_time" if "date_time" in df.columns else None)
    )
    if not name_col or not time_col or df.empty:
        return {}

    df = df.dropna(subset=[time_col]).copy()
    df[time_col] = coerce_cda_datetimes(df[time_col])
    df = df.sort_values([name_col, time_col])

    latest: Dict[str, Tuple[Any, Any]] = {}
    for _, row in df.groupby(name_col).tail(1).iterrows():
        latest[str(row[name_col])] = (row.get("value"), row[time_col])
    return latest
