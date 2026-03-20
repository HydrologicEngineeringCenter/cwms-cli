import math
import traceback
from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional

import click

from cwmscli.reporting.config import Config
from cwmscli.reporting.models import ProjectSpec
from cwmscli.reporting.utils.date import parse_when


def _expand_template(s: Optional[str], **kwargs) -> Optional[str]:
    if not s:
        return None
    try:
        return s.format(**kwargs)
    except Exception:
        return s


def _fetch_multi_df(
    tsids: List[str],
    office: str,
    unit: str,
    begin: Optional[datetime],
    end: Optional[datetime],
):
    import cwms
    import pandas as pd

    df = cwms.get_multi_timeseries_df(
        ts_ids=tsids,
        office_id=office,
        unit=unit,
        begin=begin,
        end=end,
        melted=True,
    )
    if "date-time" in df.columns:
        df["date-time"] = pd.to_datetime(df["date-time"], utc=True, errors="coerce")
    return df


def _fetch_levels_dict(
    level_ids: List[str],
    begin: Optional[datetime],
    end: Optional[datetime],
    office: str,
    unit: str,
) -> Dict[str, float | None]:
    import cwms

    out: Dict[str, float | None] = {}
    for lvl in level_ids:
        try:
            val = cwms.get_level_as_timeseries(
                begin=begin,
                end=end,
                location_level_id=lvl,
                office_id=office,
                unit=unit,
            )
            js = getattr(val, "json", None) or {}
            if callable(js):
                js = val.json()
            values = (js or {}).get("values", [])
            out[lvl] = values[-1][1] if values else None
        except Exception as err:
            print(
                f"[reporting] Warning: could not fetch level '{lvl}': {err}",
                traceback.format_exc(),
            )
            out[lvl] = None
    return out


def _format_value(
    x: Any,
    precision: Optional[int],
    missing: str,
    undefined: str,
) -> str:
    if x is None:
        return missing
    try:
        xf = float(x)
        if math.isnan(xf) or math.isinf(xf):
            return undefined
        if precision is None:
            return f"{xf}"
        return f"{xf:.{precision}f}"
    except Exception:
        return f"{x}"


def _safe_sum(values: List[float | None]) -> float | None:
    nums = [float(v) for v in values if v is not None]
    if not nums:
        return None
    return sum(nums)


def _safe_mean(values: List[float | None]) -> float | None:
    nums = [float(v) for v in values if v is not None]
    if not nums:
        return None
    return sum(nums) / len(nums)


def _as_location_metadata(location_id: str, office: str) -> Dict[str, Any]:
    import cwms

    try:
        loc = cwms.get_location(office_id=office, location_id=location_id)
        loc_json = getattr(loc, "json", None) or loc
        if isinstance(loc_json, dict):
            return {**loc_json}
    except Exception:
        pass
    return {"name": location_id, "public-name": location_id}


def _resolve_anchor(
    anchor: str,
    anchors: Dict[str, datetime],
) -> datetime:
    if anchor not in anchors:
        raise click.BadParameter(f"Unknown monthly dataset anchor '{anchor}'.")
    return anchors[anchor]


def _extract_series_points(
    tsid: str,
    office: str,
    unit: str,
    begin: datetime,
    end: datetime,
    tz_name: str,
    hour: Optional[int] = None,
) -> List[Dict[str, Any]]:
    from zoneinfo import ZoneInfo

    import pandas as pd

    df = _fetch_multi_df([tsid], office, unit, begin, end)
    if df is None or df.empty:
        return []

    name_col = (
        "ts_id" if "ts_id" in df.columns else ("name" if "name" in df.columns else None)
    )
    time_col = (
        "date-time"
        if "date-time" in df.columns
        else ("date_time" if "date_time" in df.columns else None)
    )
    if not time_col:
        return []

    if name_col:
        df = df[df[name_col].astype(str) == tsid]
    df = df.dropna(subset=[time_col])
    if df.empty:
        return []

    df[time_col] = pd.to_datetime(df[time_col], utc=True, errors="coerce")
    df = df.dropna(subset=[time_col]).sort_values(time_col)
    tzinfo = ZoneInfo(tz_name)
    df["_local_time"] = df[time_col].dt.tz_convert(tzinfo)
    if hour is not None:
        df = df[df["_local_time"].dt.hour == hour]

    out: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        dt_value = row["_local_time"]
        out.append(
            {
                "datetime": (
                    dt_value.to_pydatetime()
                    if hasattr(dt_value, "to_pydatetime")
                    else dt_value
                ),
                "value": row.get("value"),
            }
        )
    return out


def _series_value_by_day(
    points: List[Dict[str, Any]],
    tz_name: str,
    day_offset: int = 0,
) -> Dict[date, float | None]:
    from zoneinfo import ZoneInfo

    tzinfo = ZoneInfo(tz_name)
    out: Dict[date, float | None] = {}
    for point in points:
        dt_value = point["datetime"]
        if dt_value.tzinfo is None:
            dt_local = dt_value.replace(tzinfo=timezone.utc).astimezone(tzinfo)
        else:
            dt_local = dt_value.astimezone(tzinfo)
        out[dt_local.date() + timedelta(days=day_offset)] = point["value"]
    return out


def _series_value_by_month(
    points: List[Dict[str, Any]],
    tz_name: str,
) -> Dict[tuple[int, int], float | None]:
    from zoneinfo import ZoneInfo

    tzinfo = ZoneInfo(tz_name)
    out: Dict[tuple[int, int], float | None] = {}
    for point in points:
        dt_value = point["datetime"]
        if dt_value.tzinfo is None:
            dt_local = dt_value.replace(tzinfo=timezone.utc).astimezone(tzinfo)
        else:
            dt_local = dt_value.astimezone(tzinfo)
        out[(dt_local.year, dt_local.month)] = point["value"]
    return out


def _series_monthly_stats(
    points: List[Dict[str, Any]],
    tz_name: str,
) -> Dict[tuple[int, int], Dict[str, float | None]]:
    from zoneinfo import ZoneInfo

    tzinfo = ZoneInfo(tz_name)
    buckets: Dict[tuple[int, int], List[float]] = {}
    last_values: Dict[tuple[int, int], float | None] = {}
    for point in points:
        raw_value = point.get("value")
        if raw_value is None:
            continue
        value = float(raw_value)
        if math.isnan(value) or math.isinf(value):
            continue
        dt_value = point["datetime"]
        if dt_value.tzinfo is None:
            dt_local = dt_value.replace(tzinfo=timezone.utc).astimezone(tzinfo)
        else:
            dt_local = dt_value.astimezone(tzinfo)
        year_month = (dt_local.year, dt_local.month)
        buckets.setdefault(year_month, []).append(value)
        last_values[year_month] = value

    out: Dict[tuple[int, int], Dict[str, float | None]] = {}
    for year_month, values in buckets.items():
        if not values:
            out[year_month] = {"avg": None, "min": None, "max": None, "last": None}
            continue
        out[year_month] = {
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "last": last_values.get(year_month),
        }
    return out


def _context_get(path: str, values: Dict[str, Any]) -> Any:
    cur: Any = values
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
    return cur


def _context_has_path(path: str, values: Dict[str, Any]) -> bool:
    cur: Any = values
    for part in path.split("."):
        if cur is None:
            return False
        if isinstance(cur, dict):
            if part not in cur:
                return False
            cur = cur.get(part)
        else:
            if not hasattr(cur, part):
                return False
            cur = getattr(cur, part)
    return True


def _location_features(dataset: Dict[str, Any], location_id: str) -> Dict[str, Any]:
    features = dict(
        dataset.get("location_features") or dataset.get("project_features") or {}
    )
    feature_sets = dict(dataset.get("feature_sets") or {})
    for key, members in feature_sets.items():
        project_ids = {str(x).upper() for x in (members or [])}
        features[str(key)] = location_id.upper() in project_ids
    water_supply_projects = {
        str(x).upper() for x in (dataset.get("water_supply_projects") or [])
    }
    if "water_supply" not in features:
        features["water_supply"] = location_id.upper() in water_supply_projects
    for item in dataset.get("features") or []:
        features[str(item).lower()] = True
    return features


def _series_numeric_values(source: Any) -> List[float]:
    if not isinstance(source, dict):
        return []
    points = source.get("points")
    if isinstance(points, list):
        out: List[float] = []
        for point in points:
            value = point.get("value") if isinstance(point, dict) else None
            if value is not None:
                out.append(float(value))
        return out
    values = source.get("values")
    if isinstance(values, dict):
        return [float(v) for v in values.values() if v is not None]
    return []


def _row_numeric_values(source: Any) -> List[float]:
    if not isinstance(source, list):
        return []
    out: List[float] = []
    for value in source:
        if value is not None:
            out.append(float(value))
    return out


def _series_extreme_point(source: Any, op: str) -> Dict[str, Any] | None:
    if not isinstance(source, dict):
        return None
    points = source.get("points")
    if not isinstance(points, list):
        return None
    valid_points = [
        p for p in points if isinstance(p, dict) and p.get("value") is not None
    ]
    if not valid_points:
        return None
    key_fn = lambda p: float(p["value"])
    return (
        max(valid_points, key=key_fn) if op == "max" else min(valid_points, key=key_fn)
    )


def _evaluate_derived(
    derived_cfg: Dict[str, Any],
    values: Dict[str, Any],
    tzinfo,
) -> Dict[str, Any]:
    derived: Dict[str, Any] = {}
    pending = dict(derived_cfg)
    while pending:
        progressed = False
        for key in list(pending):
            spec = dict(pending[key] or {})
            op = str(spec.get("op") or "").strip().lower()
            source_path = str(spec.get("source") or "").strip()
            eval_values = {**values, "derived": derived}
            source = _context_get(source_path, eval_values) if source_path else None
            if source_path and not _context_has_path(source_path, eval_values):
                continue

            if op == "sum":
                nums = _series_numeric_values(source)
                if not nums:
                    nums = _row_numeric_values(source)
                derived[key] = sum(nums) if nums else None
            elif op == "mean":
                nums = _series_numeric_values(source)
                if not nums:
                    nums = _row_numeric_values(source)
                derived[key] = (sum(nums) / len(nums)) if nums else None
            elif op == "multiply":
                factor = float(spec.get("factor") or 1)
                if source is None:
                    derived[key] = None
                else:
                    derived[key] = float(source) * factor
            elif op == "extreme":
                mode = str(spec.get("mode") or "max").lower()
                derived[key] = _series_extreme_point(source, mode)
            elif op == "field":
                field_name = str(spec.get("field") or "").strip()
                derived[key] = (
                    source.get(field_name) if isinstance(source, dict) else None
                )
            elif op == "datetime_format":
                fmt = str(spec.get("format") or "%d")
                dt_value = source
                if isinstance(source, dict):
                    dt_value = source.get("datetime")
                if dt_value is None:
                    derived[key] = None
                else:
                    if getattr(dt_value, "tzinfo", None) is None:
                        dt_value = dt_value.replace(tzinfo=timezone.utc).astimezone(
                            tzinfo
                        )
                    else:
                        dt_value = dt_value.astimezone(tzinfo)
                    derived[key] = dt_value.strftime(fmt)
            elif op == "literal":
                derived[key] = spec.get("value")
            else:
                raise click.BadParameter(
                    f"Unsupported dataset.derived operation '{op}'."
                )

            del pending[key]
            progressed = True
        if not progressed:
            unresolved = ", ".join(sorted(pending))
            raise click.BadParameter(
                f"Could not resolve dataset.derived entries: {unresolved}"
            )
    return derived


def build_monthly_project_report(config: Config) -> Dict[str, Any]:
    dataset = config.dataset.options or {}
    locations = [
        str(x).strip().upper()
        for x in (dataset.get("locations") or dataset.get("projects") or [])
        if str(x).strip()
    ]
    location_id = (
        str(dataset.get("location") or dataset.get("project") or "").strip().upper()
    )
    if not location_id and len(locations) == 1:
        location_id = locations[0]
    if not location_id:
        raise click.BadParameter(
            "dataset.location is required for monthly reports. "
            "If the config declares multiple dataset.locations, pass --location."
        )
    if locations and location_id not in locations:
        raise click.BadParameter(
            f"Location '{location_id}' is not listed in dataset.locations."
        )

    month_expr = str(dataset.get("month") or "").strip()
    if not month_expr:
        raise click.BadParameter(
            "dataset.month is required for monthly_project reports. "
            "Pass it in config or with --month."
        )

    office = str(dataset.get("office") or config.office)
    tz_name = str(dataset.get("timezone") or config.time_zone or "America/Chicago")
    report_hour = int(dataset.get("report_hour", 8))
    rainfall_hour = int(dataset.get("rainfall_hour", 7))
    level_hour = int(dataset.get("level_hour", 1))
    location_features = _location_features(dataset, location_id)

    try:
        year_s, month_s = month_expr.split("-", 1)
        year = int(year_s)
        month = int(month_s)
    except Exception as err:
        raise click.BadParameter("dataset.month must be in YYYY-MM format.") from err

    from zoneinfo import ZoneInfo

    tzinfo = ZoneInfo(tz_name)
    _, last_day = monthrange(year, month)
    month_start_report = datetime(year, month, 1, report_hour, 0, 0, tzinfo=tzinfo)
    month_start_midnight = datetime(year, month, 1, 0, 0, 0, tzinfo=tzinfo)
    month_start_7am = datetime(year, month, 1, rainfall_hour, 0, 0, tzinfo=tzinfo)
    month_start_1am = datetime(year, month, 1, level_hour, 0, 0, tzinfo=tzinfo)
    month_end_report = datetime(year, month, last_day, report_hour, 0, 0, tzinfo=tzinfo)
    month_end_midnight_plus_one = datetime(
        year, month, last_day, 0, 0, 0, tzinfo=tzinfo
    ) + timedelta(days=1)
    month_end_report_plus_one = month_end_report + timedelta(days=1)
    month_start_report_yesterday = month_start_report - timedelta(days=1)
    month_level_end = month_start_1am + timedelta(days=1)

    anchors = {
        "month_start_report": month_start_report,
        "month_start_midnight": month_start_midnight,
        "month_start_rainfall": month_start_7am,
        "month_start_level": month_start_1am,
        "month_end_report": month_end_report,
        "month_end_midnight_plus_one": month_end_midnight_plus_one,
        "month_end_report_plus_one": month_end_report_plus_one,
        "month_start_report_yesterday": month_start_report_yesterday,
        "month_level_end": month_level_end,
    }

    series_cfg = dict(dataset.get("series") or {})
    levels_cfg = dict(dataset.get("levels") or {})

    if not series_cfg:
        raise click.BadParameter(
            "dataset.series is required for monthly_project reports."
        )

    resolved_series: Dict[str, Dict[str, Any]] = {}
    by_day: Dict[str, Dict[date, float | None]] = {}
    scalar_values: Dict[str, Any] = {}

    for key, spec in series_cfg.items():
        spec = dict(spec or {})
        tsid = _expand_template(
            spec.get("tsid"),
            project=location_id,
            location=location_id,
        )
        if not tsid:
            raise click.BadParameter(f"dataset.series.{key}.tsid is required.")
        unit = str(spec.get("unit") or config.default_unit)
        precision = spec.get("precision")
        missing = spec.get("missing") or config.missing
        undefined = spec.get("undefined") or config.undefined
        office_id = str(spec.get("office") or office)
        hour = spec.get("hour")
        day_offset = int(spec.get("day_offset") or 0)
        begin = _resolve_anchor(str(spec.get("begin_anchor")), anchors)
        end = _resolve_anchor(str(spec.get("end_anchor")), anchors)
        points = _extract_series_points(
            tsid=tsid,
            office=office_id,
            unit=unit,
            begin=begin,
            end=end,
            tz_name=tz_name,
            hour=int(hour) if hour is not None else None,
        )
        resolved_series[key] = {
            "tsid": tsid,
            "unit": unit,
            "precision": precision,
            "missing": missing,
            "undefined": undefined,
            "day_offset": day_offset,
            "points": points,
        }
        if spec.get("mode") == "daily":
            by_day[key] = _series_value_by_day(points, tz_name, day_offset=day_offset)
        elif spec.get("mode") == "summary":
            last_point = points[-1] if points else None
            scalar_values[key] = {
                "value": last_point["value"] if last_point else None,
                "datetime": last_point["datetime"] if last_point else None,
            }

    level_values: Dict[str, float | None] = {}
    for key, spec in levels_cfg.items():
        spec = dict(spec or {})
        level_id = _expand_template(
            spec.get("level"),
            project=location_id,
            location=location_id,
        )
        if not level_id:
            raise click.BadParameter(f"dataset.levels.{key}.level is required.")
        unit = str(spec.get("unit") or config.default_unit)
        office_id = str(spec.get("office") or office)
        vals = _fetch_levels_dict(
            [level_id],
            begin=month_start_1am,
            end=month_level_end,
            office=office_id,
            unit=unit,
        )
        level_values[key] = vals.get(level_id)

    location = _as_location_metadata(location_id, office)
    location_name = str(
        location.get("public-name")
        or location.get("name")
        or dataset.get("location_name")
        or dataset.get("project_name")
        or location_id
    )

    daily_dates = [date(year, month, day) for day in range(1, last_day + 1)]
    daily_rows: List[Dict[str, Any]] = []
    for current_day in daily_dates:
        row = {
            "day": current_day.day,
            "morning_elev": by_day.get("morning_elev", {}).get(current_day),
            "midnight_elev": by_day.get("midnight_elev", {}).get(current_day),
            "storage_total": by_day.get("storage_total", {}).get(current_day),
            "release_power": by_day.get("release_power", {}).get(current_day),
            "release_total": by_day.get("release_total", {}).get(current_day),
            "evaporation": by_day.get("evaporation", {}).get(current_day),
            "inflow": by_day.get("inflow", {}).get(current_day),
            "rain_dam": by_day.get("rain_dam", {}).get(current_day),
            "rain_basin": by_day.get("rain_basin", {}).get(current_day),
        }
        daily_rows.append(row)

    for key, values_by_day in by_day.items():
        if key == "day":
            continue
        for row, current_day in zip(daily_rows, daily_dates):
            row.setdefault(key, values_by_day.get(current_day))

    row_series_context: Dict[str, List[float | None]] = {}
    if daily_rows:
        for key in daily_rows[0]:
            if key == "day":
                continue
            row_series_context[key] = [row.get(key) for row in daily_rows]

    prior_month_date = date(year, month, 1) - timedelta(days=1)
    prior_month = {
        "midnight_elev": by_day.get("midnight_elev", {}).get(prior_month_date),
        "storage_total": by_day.get("storage_total", {}).get(prior_month_date),
    }

    daily_series_context = {
        key: {"values": value_map} for key, value_map in by_day.items()
    }
    derived_cfg = dict(dataset.get("derived") or {})
    derived = _evaluate_derived(
        derived_cfg,
        {
            "series": resolved_series,
            "daily": daily_series_context,
            "rows": row_series_context,
            "levels": level_values,
            "summary": scalar_values,
        },
        tzinfo=tzinfo,
    )

    summary = {
        "total_power_release": derived.get("total_power_release"),
        "total_total_release": derived.get("total_total_release"),
        "total_evaporation": derived.get("total_evaporation"),
        "total_inflow": derived.get("total_inflow"),
        "total_rain_dam": derived.get("total_rain_dam"),
        "total_rain_basin": derived.get("total_rain_basin"),
        "average_elevation": derived.get("average_elevation"),
        "average_power_release": derived.get("average_power_release"),
        "average_total_release": derived.get("average_total_release"),
        "average_inflow": derived.get("average_inflow"),
        "inflow_volume": derived.get("inflow_volume"),
    }

    max_elev = derived.get("max_elev_point") or {}
    min_elev = derived.get("min_elev_point") or {}
    max_stor = derived.get("max_storage_point") or {}
    min_stor = derived.get("min_storage_point") or {}

    return {
        "dataset_kind": config.dataset.kind,
        "base_end": month_end_report.astimezone(timezone.utc),
        "location_id": location_id,
        "project": location_id,
        "office": office,
        "location": location,
        "location_features": location_features,
        "project_features": location_features,
        "location_name": location_name,
        "lake_name": location_name,
        "month_label": month_start_report.strftime("%b %Y").upper(),
        "period": {
            "year": year,
            "month": month,
            "last_day": last_day,
            "timezone": tz_name,
        },
        "daily_rows": daily_rows,
        "prior_month": prior_month,
        "summary": summary,
        "extremes": {
            "max_elev": max_elev.get("value"),
            "max_elev_day": (
                max_elev.get("datetime").astimezone(tzinfo).day
                if max_elev.get("datetime") is not None
                else None
            ),
            "min_elev": min_elev.get("value"),
            "min_elev_day": (
                min_elev.get("datetime").astimezone(tzinfo).day
                if min_elev.get("datetime") is not None
                else None
            ),
            "max_storage": max_stor.get("value"),
            "min_storage": min_stor.get("value"),
        },
        "levels": level_values,
        "series": resolved_series,
        "derived": derived,
    }


def build_yearly_location_report(config: Config) -> Dict[str, Any]:
    dataset = config.dataset.options or {}
    locations = [
        str(x).strip().upper()
        for x in (dataset.get("locations") or dataset.get("projects") or [])
        if str(x).strip()
    ]
    location_id = (
        str(dataset.get("location") or dataset.get("project") or "").strip().upper()
    )
    if not location_id and len(locations) == 1:
        location_id = locations[0]
    if not location_id:
        raise click.BadParameter(
            "dataset.location is required for yearly reports. "
            "If the config declares multiple dataset.locations, pass --location."
        )
    if locations and location_id not in locations:
        raise click.BadParameter(
            f"Location '{location_id}' is not listed in dataset.locations."
        )

    year = int(dataset.get("year") or 0)
    if not year:
        raise click.BadParameter(
            "dataset.year is required for yearly reports. Pass it in config."
        )

    office = str(dataset.get("office") or config.office)
    tz_name = str(dataset.get("timezone") or config.time_zone or "America/Chicago")

    from zoneinfo import ZoneInfo

    tzinfo = ZoneInfo(tz_name)
    year_start = datetime(year, 1, 1, 0, 0, 0, tzinfo=tzinfo)
    year_end = datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=tzinfo)

    monthly_series_cfg = dict(dataset.get("monthly_series") or {})
    hourly_series_cfg = dict(dataset.get("hourly_series") or {})
    if not monthly_series_cfg and not hourly_series_cfg:
        raise click.BadParameter(
            "dataset.monthly_series or dataset.hourly_series is required for yearly reports."
        )

    monthly_values: Dict[str, Dict[tuple[int, int], float | None]] = {}
    hourly_stats: Dict[str, Dict[tuple[int, int], Dict[str, float | None]]] = {}
    series_meta: Dict[str, Dict[str, Any]] = {}

    for key, spec in monthly_series_cfg.items():
        spec = dict(spec or {})
        tsid = _expand_template(
            spec.get("tsid"),
            project=location_id,
            location=location_id,
        )
        if not tsid:
            raise click.BadParameter(f"dataset.monthly_series.{key}.tsid is required.")
        unit = str(spec.get("unit") or config.default_unit)
        office_id = str(spec.get("office") or office)
        points = _extract_series_points(
            tsid=tsid,
            office=office_id,
            unit=unit,
            begin=year_start,
            end=year_end,
            tz_name=tz_name,
        )
        monthly_values[key] = _series_value_by_month(points, tz_name)
        series_meta[key] = {
            "tsid": tsid,
            "unit": unit,
            "precision": spec.get("precision"),
            "kind": "monthly",
        }

    for key, spec in hourly_series_cfg.items():
        spec = dict(spec or {})
        tsid = _expand_template(
            spec.get("tsid"),
            project=location_id,
            location=location_id,
        )
        if not tsid:
            raise click.BadParameter(f"dataset.hourly_series.{key}.tsid is required.")
        unit = str(spec.get("unit") or config.default_unit)
        office_id = str(spec.get("office") or office)
        points = _extract_series_points(
            tsid=tsid,
            office=office_id,
            unit=unit,
            begin=year_start,
            end=year_end,
            tz_name=tz_name,
        )
        hourly_stats[key] = _series_monthly_stats(points, tz_name)
        series_meta[key] = {
            "tsid": tsid,
            "unit": unit,
            "precision": spec.get("precision"),
            "kind": "hourly",
        }

    location = _as_location_metadata(location_id, office)
    location_name = str(
        location.get("public-name")
        or location.get("name")
        or dataset.get("location_name")
        or dataset.get("project_name")
        or location_id
    )

    monthly_rows: List[Dict[str, Any]] = []
    for month in range(1, 13):
        current = datetime(year, month, 1, 0, 0, 0, tzinfo=tzinfo)
        row: Dict[str, Any] = {
            "month": current.strftime("%b").upper(),
            "month_number": month,
        }
        for key, values_by_month in monthly_values.items():
            row[key] = values_by_month.get((year, month))
        for key, stats_by_month in hourly_stats.items():
            stats = stats_by_month.get((year, month), {})
            row[f"{key}_last"] = stats.get("last")
            row[f"{key}_avg"] = stats.get("avg")
            row[f"{key}_min"] = stats.get("min")
            row[f"{key}_max"] = stats.get("max")
        monthly_rows.append(row)

    return {
        "dataset_kind": config.dataset.kind,
        "base_end": year_end.astimezone(timezone.utc),
        "location_id": location_id,
        "project": location_id,
        "office": office,
        "location": location,
        "location_name": location_name,
        "year_label": str(year),
        "period": {
            "year": year,
            "timezone": tz_name,
        },
        "monthly_rows": monthly_rows,
        "series": series_meta,
    }


def build_report_table(
    config: Config, begin: Optional[datetime], end: Optional[datetime]
) -> Dict[str, Any]:
    import cwms
    import pandas as pd

    rows: List[str] = [p.location_id for p in config.projects]
    if not rows:
        raise click.UsageError("No 'projects' configured in YAML.")

    proj_by_id: Dict[str, ProjectSpec] = {p.location_id: p for p in config.projects}
    tz = config.time_zone or "UTC"

    col_defs: List[Dict[str, Any]] = []
    for c in config.columns:
        if not (c.tsid or c.level):
            raise click.BadParameter(f"Column '{c.title}' must have 'tsid' or 'level'.")
        col_defs.append(
            {
                "title": c.title,
                "key": c.key,
                "precision": c.precision,
                "unit": c.unit or config.default_unit,
                "office": c.office or config.office,
                "tsid_template": c.tsid,
                "level_template": c.level,
                "href_template": c.href,
                "missing": c.missing or config.missing,
                "undefined": c.undefined or config.undefined,
                "begin_expr": c.begin,
                "end_expr": c.end,
            }
        )

    candidate_ends: List[datetime] = []
    if end:
        candidate_ends.append(end)

    def effective_range(
        bexpr: Optional[str], eexpr: Optional[str]
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        b_eff = parse_when(bexpr, tz) if bexpr else begin
        e_eff = parse_when(eexpr, tz) if eexpr else end
        return b_eff, e_eff

    ts_groups: Dict[tuple, List[str]] = {}
    backref_ts: Dict[tuple, List[tuple]] = {}

    lvl_groups: Dict[tuple, List[str]] = {}
    backref_lvl: Dict[tuple, List[tuple]] = {}

    effective_windows: Dict[tuple, tuple[Optional[datetime], Optional[datetime]]] = {}

    for proj_id in rows:
        for c in col_defs:
            office = c["office"]
            unit = c["unit"]
            key = c["key"]

            b_eff, e_eff = effective_range(c.get("begin_expr"), c.get("end_expr"))
            if e_eff:
                candidate_ends.append(e_eff)
            effective_windows[(proj_id, key)] = (b_eff, e_eff)

            if c["tsid_template"]:
                tsid = _expand_template(c["tsid_template"], project=proj_id)
                gk = (office, unit, b_eff, e_eff)
                ts_groups.setdefault(gk, [])
                if tsid not in ts_groups[gk]:
                    ts_groups[gk].append(tsid)
                backref_ts.setdefault((office, unit, b_eff, e_eff, tsid), []).append(
                    (proj_id, key)
                )

            elif c["level_template"]:
                lvl = _expand_template(c["level_template"], project=proj_id)
                gk = (office, unit, b_eff, e_eff)
                lvl_groups.setdefault(gk, [])
                if lvl not in lvl_groups[gk]:
                    lvl_groups[gk].append(lvl)
                backref_lvl.setdefault((office, unit, b_eff, e_eff, lvl), []).append(
                    (proj_id, key)
                )

    base_end = (
        candidate_ends
        and max(dt for dt in candidate_ends if dt is not None)
        or datetime.now(timezone.utc)
    )

    last_ts_value: Dict[tuple, float | None] = {}
    for (office, unit, b_eff, e_eff), tsids in ts_groups.items():
        if not tsids:
            continue
        df = _fetch_multi_df(tsids, office, unit, b_eff, e_eff)

        name_col = (
            "ts_id"
            if "ts_id" in df.columns
            else ("name" if "name" in df.columns else None)
        )
        time_col = (
            "date-time"
            if "date-time" in df.columns
            else ("date_time" if "date_time" in df.columns else None)
        )

        if name_col and time_col:
            df = df.dropna(subset=[time_col])
            df[time_col] = pd.to_datetime(df[time_col], utc=True, errors="coerce")
            df = df.sort_values([name_col, time_col])
            last = df.groupby(name_col).tail(1)
            for _, row in last.iterrows():
                last_ts_value[(office, unit, b_eff, e_eff, str(row[name_col]))] = (
                    row.get("value", None)
                )
        else:
            for ts in tsids:
                last_ts_value[(office, unit, b_eff, e_eff, ts)] = None

    last_lvl_value: Dict[tuple, float | None] = {}
    for (office, unit, b_eff, e_eff), lvls in lvl_groups.items():
        if not lvls:
            continue
        vals = _fetch_levels_dict(
            lvls,
            begin=b_eff,
            end=e_eff,
            office=office,
            unit=unit,
        )
        for lvl in lvls:
            last_lvl_value[(office, unit, b_eff, e_eff, lvl)] = vals.get(lvl)

    table: Dict[str, Dict[str, Any]] = {proj_id: {} for proj_id in rows}

    for (office, unit, b_eff, e_eff, tsid), pairs in backref_ts.items():
        raw = last_ts_value.get((office, unit, b_eff, e_eff, tsid))
        for proj_id, col_key in pairs:
            c = next((x for x in col_defs if x["key"] == col_key), None)
            val_text = _format_value(
                raw,
                precision=c.get("precision") if c else None,
                missing=(c.get("missing") or config.missing),
                undefined=(c.get("undefined") or config.undefined),
            )
            href = _expand_template(
                c.get("href_template"),
                project=proj_id,
                office=office,
                tsid=tsid,
                level=None,
            )
            table[proj_id][col_key] = {
                "text": val_text,
                **({"href": href} if href else {}),
            }

    for (office, unit, b_eff, e_eff, lvl), pairs in backref_lvl.items():
        raw = last_lvl_value.get((office, unit, b_eff, e_eff, lvl))
        for proj_id, col_key in pairs:
            c = next((x for x in col_defs if x["key"] == col_key), None)
            val_text = _format_value(
                raw,
                precision=c.get("precision") if c else None,
                missing=(c.get("missing") or config.missing),
                undefined=(c.get("undefined") or config.undefined),
            )
            href = _expand_template(
                c.get("href_template"),
                project=proj_id,
                office=office,
                tsid=None,
                level=lvl,
            )
            table[proj_id][col_key] = {
                "text": val_text,
                **({"href": href} if href else {}),
            }

    proj_locations: Dict[str, Dict[str, Any]] = {}
    for proj_id in rows:
        proj = proj_by_id[proj_id]
        proj_office = proj.office or config.office
        try:
            loc = cwms.get_location(office_id=proj_office, location_id=proj_id)
            loc_json = getattr(loc, "json", None) or loc
            if isinstance(loc_json, dict):
                loc_json = {**loc_json}
                if proj.href:
                    loc_json["href"] = proj.href
            else:
                loc_json = {"name": proj_id, "href": proj.href}
        except Exception:
            loc_json = {"name": proj_id, "href": proj.href}
        proj_locations[proj_id] = loc_json

    for proj_id in rows:
        table[proj_id]["location"] = proj_locations.get(proj_id, {"name": proj_id})

    return {
        "columns": col_defs,
        "rows": rows,
        "data": table,
        "base_end": base_end,
    }
