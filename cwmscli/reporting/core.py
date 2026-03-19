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


def _as_project_location(project_id: str, office: str) -> Dict[str, Any]:
    import cwms

    try:
        loc = cwms.get_location(office_id=office, location_id=project_id)
        loc_json = getattr(loc, "json", None) or loc
        if isinstance(loc_json, dict):
            return {**loc_json}
    except Exception:
        pass
    return {"name": project_id, "public-name": project_id}


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


def build_monthly_project_report(config: Config) -> Dict[str, Any]:
    dataset = config.dataset.options or {}
    project = str(dataset.get("project") or "").strip()
    if not project:
        raise click.BadParameter(
            "dataset.project is required for monthly_project reports."
        )

    month_expr = str(dataset.get("month") or "").strip()
    if not month_expr:
        raise click.BadParameter(
            "dataset.month is required for monthly_project reports."
        )

    office = str(dataset.get("office") or config.office)
    tz_name = str(dataset.get("timezone") or config.time_zone or "America/Chicago")
    report_hour = int(dataset.get("report_hour", 8))
    rainfall_hour = int(dataset.get("rainfall_hour", 7))
    level_hour = int(dataset.get("level_hour", 1))
    water_supply_projects = {
        str(x).upper() for x in (dataset.get("water_supply_projects") or [])
    }

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
        tsid = _expand_template(spec.get("tsid"), project=project)
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
        level_id = _expand_template(spec.get("level"), project=project)
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

    location = _as_project_location(project, office)
    lake_name = str(
        location.get("public-name")
        or location.get("name")
        or dataset.get("project_name")
        or project
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

    prior_month_date = date(year, month, 1) - timedelta(days=1)
    prior_month = {
        "midnight_elev": by_day.get("midnight_elev", {}).get(prior_month_date),
        "storage_total": by_day.get("storage_total", {}).get(prior_month_date),
    }

    summary = {
        "total_power_release": _safe_sum([row["release_power"] for row in daily_rows]),
        "total_total_release": _safe_sum([row["release_total"] for row in daily_rows]),
        "total_evaporation": _safe_sum([row["evaporation"] for row in daily_rows]),
        "total_inflow": _safe_sum([row["inflow"] for row in daily_rows]),
        "total_rain_dam": _safe_sum([row["rain_dam"] for row in daily_rows]),
        "total_rain_basin": _safe_sum([row["rain_basin"] for row in daily_rows]),
        "average_elevation": _safe_mean([row["midnight_elev"] for row in daily_rows]),
        "average_power_release": _safe_mean(
            [row["release_power"] for row in daily_rows]
        ),
        "average_total_release": _safe_mean(
            [row["release_total"] for row in daily_rows]
        ),
        "average_inflow": _safe_mean([row["inflow"] for row in daily_rows]),
    }
    summary["inflow_volume"] = (
        summary["total_inflow"] * 1.9835
        if summary["total_inflow"] is not None
        else None
    )

    extrema_cfg = dict(dataset.get("extrema") or {})
    max_elev = scalar_values.get("max_elev", {})
    min_elev = scalar_values.get("min_elev", {})
    max_stor = scalar_values.get("max_storage", {})
    min_stor = scalar_values.get("min_storage", {})

    elev_source_key = extrema_cfg.get("elevation_source")
    if elev_source_key and elev_source_key in resolved_series:
        points = resolved_series[elev_source_key]["points"]
        valid_points = [p for p in points if p.get("value") is not None]
        if valid_points:
            max_point = max(valid_points, key=lambda p: float(p["value"]))
            min_point = min(valid_points, key=lambda p: float(p["value"]))
            max_elev = max_point
            min_elev = min_point

    storage_source_key = extrema_cfg.get("storage_source")
    if storage_source_key and storage_source_key in resolved_series:
        points = resolved_series[storage_source_key]["points"]
        valid_points = [p for p in points if p.get("value") is not None]
        if valid_points:
            max_point = max(valid_points, key=lambda p: float(p["value"]))
            min_point = min(valid_points, key=lambda p: float(p["value"]))
            max_stor = max_point
            min_stor = min_point

    water_supply = None
    if project.upper() in water_supply_projects and "water_supply" in by_day:
        water_supply_total = _safe_sum(list(by_day["water_supply"].values()))
        water_supply = {
            "volume": (
                water_supply_total * 1.9835 if water_supply_total is not None else None
            )
        }

    return {
        "dataset_kind": "monthly_project",
        "base_end": month_end_report.astimezone(timezone.utc),
        "project": project,
        "office": office,
        "location": location,
        "lake_name": lake_name,
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
        "water_supply": water_supply,
        "series": resolved_series,
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
