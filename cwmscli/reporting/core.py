# =========================
# Core
# =========================


import math
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

import click
import cwms
import pandas as pd

from cwmscli.reporting.config import Config
from cwmscli.reporting.models import ProjectSpec


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
) -> pd.DataFrame:
    """
    Wrapper around cwms.get_multi_timeseries_df, always returns a melted frame:
      columns: ['date-time','name','value','quality-code'] (depending on cwms-python version)
    """
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
    begin: datetime,
    end: datetime,
    office: str,
    unit: str,
) -> Dict[str, float | None]:
    """
    Return {level_id: value or None}.
    """
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


def build_report_table(
    config: Config, begin: datetime, end: datetime
) -> Dict[str, Any]:
    rows: List[str] = [p.location_id for p in config.projects]
    if not rows:
        raise click.UsageError("No 'projects' configured in YAML.")

    proj_by_id: Dict[str, ProjectSpec] = {p.location_id: p for p in config.projects}

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
            }
        )

    base_end = end or datetime.now(timezone.utc)

    # Group ts requests by (office, unit, begin, end)
    ts_groups: Dict[tuple, List[str]] = {}
    backref_ts: Dict[tuple, List[tuple]] = {}

    # Group level requests by (office, unit)
    lvl_groups: Dict[tuple, List[str]] = {}
    backref_lvl: Dict[tuple, List[tuple]] = {}

    for proj_id in rows:
        for c in col_defs:
            office = c["office"]
            unit = c["unit"]
            key = c["key"]

            if c["tsid_template"]:
                tsid = _expand_template(c["tsid_template"], project=proj_id)
                gk = (office, unit, begin, end)
                ts_groups.setdefault(gk, [])
                if tsid not in ts_groups[gk]:
                    ts_groups[gk].append(tsid)
                backref_ts.setdefault((office, unit, begin, end, tsid), []).append(
                    (proj_id, key)
                )

            elif c["level_template"]:
                lvl = _expand_template(c["level_template"], project=proj_id)
                gk = (office, unit)
                lvl_groups.setdefault(gk, [])
                if lvl not in lvl_groups[gk]:
                    lvl_groups[gk].append(lvl)
                backref_lvl.setdefault((office, unit, lvl), []).append((proj_id, key))

    # Fetch latest TS values within window
    last_ts_value: Dict[tuple, float | None] = {}
    for (office, unit, b, e), tsids in ts_groups.items():
        if not tsids:
            continue
        df = _fetch_multi_df(tsids, office, unit, b, e)

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
                last_ts_value[(office, unit, b, e, str(row[name_col]))] = row.get(
                    "value", None
                )
        else:
            for ts in tsids:
                last_ts_value[(office, unit, b, e, ts)] = None

    # Fetch latest Level values
    last_lvl_value: Dict[tuple, float | None] = {}
    for (office, unit), lvls in lvl_groups.items():
        if not lvls:
            continue
        vals = _fetch_levels_dict(
            lvls,
            begin=begin,
            end=end,
            office=office,
            unit=unit,
        )
        for lvl in lvls:
            last_lvl_value[(office, unit, lvl)] = vals.get(lvl)

    # Project location info
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

    # Build table payload
    table: Dict[str, Dict[str, Any]] = {proj_id: {} for proj_id in rows}

    for (office, unit, b, e, tsid), pairs in backref_ts.items():
        raw = last_ts_value.get((office, unit, b, e, tsid))
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
            table[proj_id][col_key] = (
                {"text": val_text, "href": href} if href else {"text": val_text}
            )

    for (office, unit, lvl), pairs in backref_lvl.items():
        raw = last_lvl_value.get((office, unit, lvl))
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
            table[proj_id][col_key] = (
                {"text": val_text, "href": href} if href else {"text": val_text}
            )

    for proj_id in rows:
        table[proj_id]["location"] = proj_locations.get(proj_id, {"name": proj_id})

    return {
        "columns": col_defs,
        "rows": rows,
        "data": table,
        "base_end": base_end,
    }
