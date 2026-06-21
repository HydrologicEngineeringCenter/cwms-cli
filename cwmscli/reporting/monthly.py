import calendar
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

import click

from cwmscli.reporting.config import Config
from cwmscli.reporting.sources import fetch_timeseries_df

DEFAULT_MONTHLY_SERIES = {
    "elevation": {
        "tsid": "{project}.Elev.Inst.1Hour.0.Ccp-Rev",
        "unit": "ft",
    },
    "storage": {
        "tsid": "{project}.Stor.Inst.1Hour.0.Ccp-Rev",
        "unit": "ac-ft",
    },
    "power_release": {
        "tsid": "{project}.Flow-Power.Ave.~1Day.1Day.Rev-Regi-Flowgroup",
        "unit": "cfs",
    },
    "total_release": {
        "tsid": "{project}.Flow-Res Out.Ave.~1Day.1Day.Rev-Regi-Flowgroup",
        "unit": "cfs",
    },
    "evaporation": {
        "tsid": "{project}.Evap.Total.~1Day.1Day.Ccp-Rev",
        "unit": "in",
    },
    "inflow": {
        "tsid": "{project}.Flow-Res In.Ave.~1Day.1Day.Regi-Rev-Adjusted",
        "unit": "cfs",
    },
    "rainfall_dam": {
        "tsid": "{project}.Precip-Inc.Total.~1Day.1Day.Ccp-Rev",
        "unit": "in",
    },
    "rainfall_basin": {
        "tsid": "{project}.Precip-Mean Areal.Total.~1Day.1Day.Metvue-Computed",
        "unit": "in",
    },
}


def _parse_month(value: str, tz: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise click.BadParameter("monthly_lake dataset requires dataset.month.")
    for fmt in ("%Y-%m", "%b %Y", "%B %Y"):
        try:
            parsed = datetime.strptime(text, fmt)
            return datetime(parsed.year, parsed.month, 1, tzinfo=ZoneInfo(tz))
        except ValueError:
            pass
    raise click.BadParameter("dataset.month must be YYYY-MM, Mon YYYY, or Month YYYY.")


def _series_options(config: Config, key: str) -> Dict[str, str]:
    configured = dict((config.dataset.options.get("series") or {}).get(key) or {})
    defaults = DEFAULT_MONTHLY_SERIES[key]
    return {
        "tsid": configured.get("tsid") or defaults["tsid"],
        "unit": configured.get("unit") or defaults["unit"],
    }


def _expand(value: str, project: str) -> str:
    return value.format(project=project)


def _value_at(df, timestamp: datetime) -> Optional[float]:
    if df.empty:
        return None
    matches = df[df["date-time"].eq(timestamp)]
    if matches.empty:
        return None
    value = matches.iloc[-1]["value"]
    return None if value is None else float(value)


def _round_int(value: Optional[float]) -> Optional[int]:
    if value is None:
        return None
    return int(round(value))


def _format_float(value: Optional[float], precision: int) -> str:
    if value is None:
        return "--"
    return f"{value:.{precision}f}"


def _format_int(value: Optional[float]) -> str:
    if value is None:
        return "--"
    return f"{int(round(value))}"


def _center(text: str, width: int = 74) -> str:
    return str(text).center(width).rstrip()


def _month_end(month_start: datetime) -> datetime:
    days = calendar.monthrange(month_start.year, month_start.month)[1]
    return month_start + timedelta(days=days)


def _local_day(timestamp: datetime, tz_name: str) -> int:
    return timestamp.astimezone(ZoneInfo(tz_name)).day


def build_monthly_lake_report(config: Config) -> Dict[str, Any]:
    options = config.dataset.options
    tz_name = config.time_zone or "America/Chicago"
    month_start = _parse_month(str(options.get("month") or ""), tz_name)
    month_end = _month_end(month_start)
    num_days = (month_end - month_start).days
    project = str(options.get("project") or options.get("location") or "").strip()
    if not project:
        if config.projects:
            project = config.projects[0].location_id
        else:
            raise click.BadParameter("monthly_lake dataset requires dataset.project.")
    title = str(options.get("title") or f"{project} Lake")
    timeout_seconds = float(options.get("request_timeout_seconds") or 12)

    begin = month_start - timedelta(days=1)
    end = month_end + timedelta(days=1)
    dataframes = {}
    for key in DEFAULT_MONTHLY_SERIES:
        series = _series_options(config, key)
        tsid = _expand(series["tsid"], project=project)
        dataframes[key] = fetch_timeseries_df(
            [tsid],
            config.office,
            series["unit"],
            begin,
            end,
            timeout_seconds,
        )

    elevation = dataframes["elevation"]
    storage = dataframes["storage"]

    prior_timestamp = month_start
    prior_elev = _value_at(elevation, prior_timestamp)
    prior_storage = _value_at(storage, prior_timestamp)

    rows = []
    for day in range(1, num_days + 1):
        day_start = month_start + timedelta(days=day - 1)
        day_end = day_start + timedelta(days=1)
        row = {
            "day": day,
            "elev_0800": _value_at(elevation, day_start.replace(hour=8)),
            "elev_2400": _value_at(elevation, day_end),
            "storage": _value_at(storage, day_end),
            "power_release": _value_at(dataframes["power_release"], day_end),
            "total_release": _value_at(dataframes["total_release"], day_end),
            "evaporation": _value_at(
                dataframes["evaporation"], day_start.replace(hour=7)
            ),
            "inflow": _value_at(dataframes["inflow"], day_end),
            "rainfall_dam": _value_at(
                dataframes["rainfall_dam"], day_start.replace(hour=7)
            ),
            "rainfall_basin": _value_at(
                dataframes["rainfall_basin"], day_start.replace(hour=7)
            ),
        }
        row["line"] = _format_monthly_row(row)
        rows.append(row)

    power_values = [_round_int(row["power_release"]) for row in rows]
    release_values = [_round_int(row["total_release"]) for row in rows]
    inflow_values = [_round_int(row["inflow"]) for row in rows]
    evap_values = [row["evaporation"] for row in rows if row["evaporation"] is not None]
    dam_rain_values = [
        row["rainfall_dam"] for row in rows if row["rainfall_dam"] is not None
    ]
    basin_rain_values = [
        row["rainfall_basin"] for row in rows if row["rainfall_basin"] is not None
    ]
    elev_2400_values = [
        row["elev_2400"] for row in rows if row["elev_2400"] is not None
    ]

    month_elev = elevation[
        (elevation["date-time"] >= month_start) & (elevation["date-time"] <= month_end)
    ]
    max_row = month_elev.loc[month_elev["value"].idxmax()]
    min_row = month_elev.loc[month_elev["value"].idxmin()]
    max_time = max_row["date-time"].to_pydatetime()
    min_time = min_row["date-time"].to_pydatetime()

    power_total = round(
        sum(row["power_release"] for row in rows if row["power_release"] is not None)
    )
    release_total = round(
        sum(row["total_release"] for row in rows if row["total_release"] is not None)
    )
    inflow_total = sum(value for value in inflow_values if value is not None)

    summary = {
        "power_total": power_total,
        "release_total": release_total,
        "evap_total": sum(evap_values),
        "inflow_total": inflow_total,
        "dam_rain_total": sum(dam_rain_values),
        "basin_rain_total": sum(basin_rain_values),
        "elev_average": (
            sum(elev_2400_values) / len(elev_2400_values) if elev_2400_values else None
        ),
        "power_average": (power_total / len(power_values) if power_values else None),
        "release_average": (
            release_total / len(release_values) if release_values else None
        ),
        "inflow_average": (
            inflow_total / len(inflow_values) if inflow_values else None
        ),
        "max_elev": float(max_row["value"]),
        "max_storage": _value_at(storage, max_time),
        "max_day": _local_day(max_time, tz_name),
        "min_elev": float(min_row["value"]),
        "min_storage": _value_at(storage, min_time),
        "min_day": _local_day(min_time, tz_name),
        "inflow_volume": inflow_total
        * float(options.get("cfs_day_to_acre_feet") or 1.9835),
        "top_conservation": float(options.get("top_conservation_display") or 0),
        "top_flood": float(options.get("top_flood_display") or 0),
    }

    monthly = {
        "kind": "monthly_lake",
        "project": project,
        "title": title,
        "month_label": month_start.strftime("%B %Y").upper(),
        "filename": f"{project}{month_start.strftime('%b').upper()}{str(month_start.year)[-2:]}.txt",
        "prior": {
            "elevation": prior_elev,
            "storage": prior_storage,
            "line": (
                f"PRIOR MONTH  {_format_float(prior_elev, 2):>6}"
                f"   {_format_int(prior_storage):>6}"
            ),
        },
        "rows": rows,
        "summary": summary,
        "base_end": month_end,
    }
    monthly["text"] = _render_monthly_text(monthly)
    return {**monthly, "monthly": monthly}


def _format_monthly_row(row: Dict[str, Any]) -> str:
    return (
        f"{row['day']:2d}   "
        f"{_format_float(row['elev_0800'], 2):>6}  "
        f"{_format_float(row['elev_2400'], 2):>6}   "
        f"{_format_int(row['storage']):>6}  "
        f"{_format_int(row['power_release']):>5}    "
        f"{_format_int(row['total_release']):>5}   "
        f"{_format_float(row['evaporation'], 3):>5}   "
        f"{_format_int(row['inflow']):>5}   "
        f"{_format_float(row['rainfall_dam'], 2):>4}  "
        f"{_format_float(row['rainfall_basin'], 2):>4}"
    )


def _render_monthly_text(monthly: Dict[str, Any]) -> str:
    summary = monthly["summary"]
    header_lines = [
        _center(monthly["title"]),
        _center("MONTHLY LAKE REPORT"),
        _center(monthly["month_label"]),
    ]
    lines = [
        "    POOL ELEVATIONS  STORAGE     RELEASES       EVAP  INFLOW   RAINFALL",
        "DAY      FT-NGVD     2400HR         DSF        INCHES   ADJ     INCHES",
        "      0800    2400    AC-FT   POWER    TOTAL  8A TO 8A  DSF    7A TO  7A",
        "                                                               DAM   BSN",
        monthly["prior"]["line"],
    ]
    for row in monthly["rows"]:
        lines.append(row["line"])
        if row["day"] % 5 == 0 and row["day"] <= len(monthly["rows"]) - 6:
            lines.append("")

    lines.extend(
        [
            "",
            (
                "TOTAL                         "
                f"{summary['power_total']:5d}    {summary['release_total']:5d}"
                f"   {summary['evap_total']:5.3f}   {summary['inflow_total']:5d}"
                f"   {summary['dam_rain_total']:4.2f}  {summary['basin_rain_total']:4.2f}"
            ),
            (
                f"AVERAGE   {summary['elev_average']:6.2f}               "
                f"{summary['power_average']:4.0f}     {summary['release_average']:4.0f}"
                f"            {summary['inflow_average']:4.0f} NORMAL= 4.19"
            ),
            "",
            (
                f"MAXIMUM   {summary['max_elev']:6.2f}      "
                f"{round(summary['max_storage']):6d}   DATE={summary['max_day']:2d}"
                f"    TOP CONSERVATION POOL      {summary['top_conservation']:4.2f}"
            ),
            (
                f"MINIMUM   {summary['min_elev']:6.2f}      "
                f"{round(summary['min_storage']):6d}   DATE={summary['min_day']:2d}"
                f"    TOP FLOOD POOL             {summary['top_flood']:4.2f}"
            ),
            "",
            f"                      INFLOW VOLUME=   {round(summary['inflow_volume']):6d} AC-FT",
            "",
            "",
            "",
            "REPORT IS SUBJECT TO CHANGE AND/OR REVISION",
        ]
    )
    header = "\r\n".join(header_lines[:2]) + f"\r\n{header_lines[2]}\n\n\r\n\r\n"
    return header + "\r\n".join(lines)
