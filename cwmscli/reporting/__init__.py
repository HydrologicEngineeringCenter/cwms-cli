from __future__ import annotations

import math
import os
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import click
import cwms
import pandas as pd
import yaml

from cwmscli.utils.deps import requires


@dataclass
class ProjectSpec:
    location_id: str
    href: Optional[str] = None
    office: Optional[str] = None


@dataclass
class ReportSpec:
    district: str
    name: str
    logo_left: Optional[str] = None
    logo_right: Optional[str] = None


@dataclass
class HeaderCellSpec:
    text: str
    colspan: int = 1
    rowspan: int = 1
    align: Optional[str] = None  # "left"|"center"|"right"
    classes: Optional[str] = None


@dataclass
class TableHeaderSpec:
    project: HeaderCellSpec = field(
        default_factory=lambda: HeaderCellSpec(text="Project", rowspan=1)
    )
    rows: List[List[HeaderCellSpec]] = field(default_factory=list)


@dataclass
class ColumnSpec:
    title: str
    key: str
    tsid: Optional[str] = None
    level: Optional[str] = None
    unit: Optional[str] = None
    precision: Optional[int] = None
    office: Optional[str] = None
    location_id: Optional[str] = None
    href: Optional[str] = None
    missing: Optional[str] = None
    undefined: Optional[str] = None
    target_time: Optional[str] = None


@dataclass
class Config:
    office: str
    cda_api_root: Optional[str] = None
    report: ReportSpec | Dict[str, Any] | None = None
    projects: List[ProjectSpec] = field(default_factory=list)
    columns: List[ColumnSpec] = field(default_factory=list)
    header: Optional[TableHeaderSpec] = None
    begin: Optional[str] = None
    end: Optional[str] = None

    target_time: Optional[str] = None
    time_epsilon_minutes: int = 5

    default_unit: str = "EN"
    missing: str = "----"
    undefined: str = "--NA--"
    time_zone: Optional[str] = None

    @staticmethod
    def from_yaml(path: str) -> "Config":
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        office = (
            raw.get("office")
            or os.getenv("OFFICE")
            or os.getenv("CWMS_OFFICE")
            or "SWT"
        )

        report_block = raw.get("report") or {}
        report = ReportSpec(
            district=report_block.get("district", office),
            name=report_block.get("name", "Daily Report"),
            logo_left=report_block.get("logo_left"),
            logo_right=report_block.get("logo_right"),
        )

        cols: List[ColumnSpec] = []
        for i, c in enumerate(raw.get("columns", [])):
            cols.append(
                ColumnSpec(
                    title=c.get("title") or c.get("name") or f"Col{i+1}",
                    key=c.get("key") or c.get("title") or f"c{i+1}",
                    tsid=c.get("tsid"),
                    level=c.get("level"),
                    unit=c.get("unit"),
                    precision=c.get("precision"),
                    office=c.get("office"),
                    location_id=c.get("location_id"),
                    href=c.get("href"),
                    missing=c.get("missing"),
                    undefined=c.get("undefined"),
                    target_time=c.get("target_time"),
                )
            )

        projects_raw = raw.get("projects", [])
        projects: List[ProjectSpec] = []
        for p in projects_raw:
            if isinstance(p, str):
                projects.append(ProjectSpec(location_id=p))
            elif isinstance(p, dict):
                projects.append(
                    ProjectSpec(
                        location_id=p.get("location_id")
                        or p.get("name")
                        or p.get("id"),
                        href=p.get("href"),
                        office=p.get("office"),
                    )
                )
            else:
                raise click.BadParameter(f"Invalid project entry: {p!r}")
        # Validate the columns and header spec
        header = _parse_header_spec(raw.get("header"))
        if header and header.rows:
            # compute leaf-count in the final header row
            leaf_count = sum(max(1, c.colspan) for c in header.rows[-1])
            if leaf_count != len(cols):
                click.echo(
                    f"[reporting] Warning: header leaf-count ({leaf_count}) != number of data columns ({len(cols)}).",
                    err=True,
                )
        return Config(
            office=office,
            cda_api_root=raw.get("cda_api_root") or os.getenv("CDA_API_ROOT"),
            report=report,
            projects=projects,
            columns=cols,
            begin=raw.get("begin"),
            end=raw.get("end"),
            target_time=raw.get("target_time"),
            time_epsilon_minutes=int(raw.get("time_epsilon_minutes") or 5),
            default_unit=raw.get("default_unit") or "EN",
            missing=raw.get("missing") or "----",
            undefined=raw.get("undefined") or "--NA--",
            time_zone=raw.get("time_zone"),
            header=header,
        )


def _parse_header_spec(raw: Optional[Dict[str, Any]]) -> Optional["TableHeaderSpec"]:
    if not raw:
        return None

    def to_cell(d: Dict[str, Any]) -> HeaderCellSpec:
        return HeaderCellSpec(
            text=str(d.get("text", "")),
            colspan=int(d.get("colspan", 1) or 1),
            rowspan=int(d.get("rowspan", 1) or 1),
            align=d.get("align"),
            classes=d.get("classes"),
        )

    proj_raw = raw.get("project", {}) or {}
    project = to_cell(
        {
            "text": proj_raw.get("text", "Project"),
            "rowspan": proj_raw.get("rowspan", 1),
            "align": proj_raw.get("align"),
            "classes": proj_raw.get("classes"),
        }
    )
    rows_raw = raw.get("rows", []) or []
    rows = []
    for r in rows_raw:
        row_cells = [to_cell(c) for c in (r or [])]
        rows.append(row_cells)
    return TableHeaderSpec(project=project, rows=rows)


def _parse_target_like(
    s: Optional[str], default_tz: Optional[str]
) -> Optional[datetime]:
    """
    Accepts:
      - ISO (with/without tz): '2025-09-17T08:00:00-05:00', '2025-09-17T13:00Z'
      - 'HHMM YYYY-MM-DD [TZ]', 'HHMM MM/DD/YYYY [TZ]', 'HH:MM MM/DD/YYYY [TZ]'
      - '0800 09/17/2025 America/Chicago'
      - 'today 08:00 [TZ]' or 'yesterday 08:00 [TZ]' (optional)
    Returns timezone-aware UTC datetime.
    """
    if not s:
        return None
    s = " ".join(str(s).split())

    lower = s.lower()
    if lower.startswith(("today", "yesterday")):
        parts = s.split()
        base = (
            datetime.now(ZoneInfo(default_tz))
            if default_tz
            else datetime.now(timezone.utc)
        )
        if parts[0].lower() == "yesterday":
            base = base - timedelta(days=1)

        hhmm = parts[1] if len(parts) > 1 else "00:00"
        tz = parts[2] if len(parts) > 2 else default_tz
        if ":" in hhmm:
            hh, mm = hhmm.split(":")
        else:
            hh, mm = hhmm[:2], hhmm[2:]
        naive = base.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
        aware = (
            naive
            if naive.tzinfo
            else (
                naive.replace(tzinfo=ZoneInfo(tz))
                if tz
                else naive.replace(tzinfo=timezone.utc)
            )
        )
        return aware.astimezone(timezone.utc)

    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo(default_tz) if default_tz else timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    try:
        parts = s.split()
        tz = None
        if len(parts) == 3:
            time_s, date_s, tz = parts
        elif len(parts) == 2:
            time_s, date_s = parts
        else:
            raise ValueError()

        if ":" in time_s:
            hh, mm = time_s.split(":")
        else:
            hh, mm = time_s[:2], time_s[2:]

        if "/" in date_s:
            mon, day, yr = date_s.split("/")
            yr = int(yr)
            mon = int(mon)
            day = int(day)
        elif "-" in date_s:
            yr, mon, day = date_s.split("-")
            yr = int(yr)
            mon = int(mon)
            day = int(day)
        else:
            raise ValueError()

        tzinfo = (
            ZoneInfo(tz)
            if tz
            else (ZoneInfo(default_tz) if default_tz else timezone.utc)
        )
        local = datetime(yr, mon, day, int(hh), int(mm), tzinfo=tzinfo)
        return local.astimezone(timezone.utc)
    except Exception:
        raise click.BadParameter(f"Invalid target_time: {s}")


def _parse_time_or_relative(s: Optional[str]) -> Optional[datetime]:
    """
    Accepts ISO strings (with or without tz) or relative like "24h", "3d", "90m".
    Returns timezone-aware UTC datetimes (or None).
    """
    if not s:
        return None
    s = str(s).strip()

    if s.endswith(("h", "m", "d")) and s[:-1].isdigit():
        amount = int(s[:-1])
        unit = s[-1]
        now = datetime.now(timezone.utc)
        if unit == "h":
            return now - timedelta(hours=amount)
        if unit == "m":
            return now - timedelta(minutes=amount)
        if unit == "d":
            return now - timedelta(days=amount)

    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        raise click.BadParameter(f"Invalid datetime: {s}")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_number(x: Any, precision: Optional[int]) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "-"
    try:
        if precision is None:
            return f"{x}"
        fmt = f"{{:.{precision}f}}"
        return fmt.format(float(x))
    except Exception:
        return f"{x}"


def _expand_tsid(tsid_template: str, project: str) -> str:
    """
    If tsid_template contains '{project}', substitute it.
    Otherwise return as-is (full TSIDs remain unchanged).
    """
    if "{project}" in tsid_template:
        return tsid_template.format(project=project)
    return tsid_template


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


def _window_for_target(dt: datetime, minutes: int) -> tuple[datetime, datetime]:
    eps = max(1, int(minutes))
    return (dt - timedelta(minutes=eps), dt + timedelta(minutes=eps))


def _expand_template(s: Optional[str], **kwargs) -> Optional[str]:
    if not s:
        return None
    try:
        return s.format(**kwargs)
    except Exception:
        return s


def _fetch_levels_dict(
    level_ids: List[str],
    begin: str,
    end: str,
    office: str,
    unit: str,
) -> Dict[str, float | None]:
    """
    Return {level_id: value or None}.
    We assume cwms-python supports a get_level-like call; fall back to levels endpoint if needed.
    """
    out: Dict[str, float | None] = {}
    for lvl in level_ids:
        try:

            val = cwms.get_level_as_timeseries(
                begin=datetime.fromisoformat(begin),
                end=datetime.fromisoformat(end),
                location_level_id=lvl,
                office_id=office,
                unit=unit,
            )
            out[lvl] = val.json.get("values")[-1][1] if val.json.get("values") else None
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


def _render_template(
    template_dir: Optional[str],
    template_name: str | None,
    context: Dict[str, Any],
) -> str:
    """
    Try user-specified template directory first; if not provided or missing,
    fall back to package templates (if you ship any). For now, we only support
    user-supplied templates or very simple built-in fallback.
    """
    import jinja2

    loaders: List[jinja2.BaseLoader] = []

    if not template_dir:
        pkg_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "templates", "jinja")
        )
        if os.path.isdir(pkg_dir):
            loaders.append(jinja2.FileSystemLoader(pkg_dir))

    if template_dir and os.path.isdir(template_dir):
        loaders.append(jinja2.FileSystemLoader(template_dir))

    env = jinja2.Environment(
        loader=jinja2.ChoiceLoader(loaders) if loaders else None,
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    try:
        tmpl = env.get_template(template_name or "report.html.j2")
        return tmpl.render(**context)
    except Exception as e:
        click.echo(
            f"[reporting] Using built-in fallback template because '{template_name}' was not found.\nError: ({e})",
            err=True,
        )
        click.echo(traceback.format_exc())


def build_report_table(
    config: Config, begin: Optional[datetime], end: Optional[datetime]
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
                "target_time": c.target_time or config.target_time,
            }
        )

    base_end = end or datetime.now(timezone.utc)

    ts_groups: Dict[tuple, List[str]] = {}
    backref_ts: Dict[tuple, List[tuple]] = {}

    lvl_groups: Dict[tuple, List[str]] = {}
    backref_lvl: Dict[tuple, List[tuple]] = {}

    col_time_windows: Dict[str, tuple[datetime, datetime] | None] = {}
    for c in col_defs:
        tt = c.get("target_time")
        if tt:
            dt = _parse_target_like(tt, config.time_zone)
            col_time_windows[c["key"]] = _window_for_target(
                dt, config.time_epsilon_minutes
            )
        else:
            col_time_windows[c["key"]] = None

    for proj_id in rows:
        for c in col_defs:
            office = c["office"]
            unit = c["unit"]
            key = c["key"]

            if c["tsid_template"]:
                tsid = _expand_template(c["tsid_template"], project=proj_id)
                win = col_time_windows[key]
                b, e = win if win else (begin, end)

                if b is None or e is None:
                    e = e or base_end
                    b = b or (e - timedelta(hours=24))
                gk = (office, unit, b, e)
                ts_groups.setdefault(gk, [])
                if tsid not in ts_groups[gk]:
                    ts_groups[gk].append(tsid)
                backref_ts.setdefault((office, unit, b, e, tsid), []).append(
                    (proj_id, key)
                )

            elif c["level_template"]:
                lvl = _expand_template(c["level_template"], project=proj_id)
                gk = (office, unit)
                lvl_groups.setdefault(gk, [])
                if lvl not in lvl_groups[gk]:
                    lvl_groups[gk].append(lvl)
                backref_lvl.setdefault((office, unit, lvl), []).append((proj_id, key))

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

    last_lvl_value: Dict[tuple, float | None] = {}
    for (office, unit), lvls in lvl_groups.items():
        if not lvls:
            continue
        vals = _fetch_levels_dict(
            lvls,
            begin=config.begin,
            end=config.end,
            office=office,
            unit=unit,
        )
        for lvl in lvls:
            last_lvl_value[(office, unit, lvl)] = vals.get(lvl)

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


@click.command(
    name="reporting",
    help="Render a CWMS timeseries report to HTML using a YAML config and Jinja2.",
)
@click.option(
    "--config",
    "-c",
    "config_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to report YAML.",
)
@click.option(
    "--template-dir",
    "-t",
    "template_dir",
    type=click.Path(exists=True, file_okay=False),
    help="Directory containing Jinja templates (e.g., templates/jinja).",
)
@click.option(
    "--template",
    "-n",
    "template_name",
    default=None,
    help="Template filename to render (relative to --template-dir). Default: report.html.j2",
)
@click.option(
    "--begin",
    help='Override begin time (ISO or relative like "24h"). If omitted, uses YAML or defaults.',
)
@click.option("--end", help="Override end time (ISO). If omitted, uses YAML or now.")
@click.option(
    "--out",
    "-o",
    "out_path",
    default="report.html",
    show_default=True,
    type=click.Path(dir_okay=False),
    help="Output HTML path.",
)
@requires(
    {
        "module": "jinja2",
        "package": "Jinja2",
        "version": "3.1.0",
        "desc": "Templating for pre/post-processing",
    },
)
def reporting_cli(config_path, template_dir, template_name, begin, end, out_path):

    cfg = Config.from_yaml(config_path)
    cfg_begin = (
        _parse_time_or_relative(begin) if begin else _parse_time_or_relative(cfg.begin)
    )
    cfg_end = _parse_time_or_relative(end) if end else _parse_time_or_relative(cfg.end)
    if cfg_end is None:
        cfg_end = datetime.now(timezone.utc)
    if cfg_begin is None:
        cfg_begin = cfg_end - timedelta(hours=24)

    cwms.init_session(api_root=cfg.cda_api_root)
    table_ctx = build_report_table(cfg, cfg_begin, cfg_end)

    base_date = table_ctx.get("base_end", cfg_end).astimezone(timezone.utc)
    context = {
        "office": cfg.office,
        "report": dataclasses_asdict(cfg.report),
        "base_date": base_date,
        "header": dataclasses_asdict(cfg.header),
        **table_ctx,
    }
    html = _render_template(template_dir, template_name, context)
    if not html:
        raise click.ClickException("No HTML generated.")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    click.echo(f"Wrote {out_path}")


def dataclasses_asdict(obj):
    if obj is None:
        return None
    if hasattr(obj, "__dataclass_fields__"):
        return {
            fld: dataclasses_asdict(getattr(obj, fld))
            for fld in obj.__dataclass_fields__
        }
    if isinstance(obj, (list, tuple)):
        return [dataclasses_asdict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: dataclasses_asdict(v) for k, v in obj.items()}
    return obj
