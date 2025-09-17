from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

import click
import cwms
import pandas as pd
import yaml

from cwmscli.utils.deps import requires


# ---------- Models ----------
@dataclass
class ProjectSpec:
    location_id: str
    href: Optional[str] = None
    office: Optional[str] = None


@dataclass
class ColumnSpec:
    title: str
    tsid: str
    unit: Optional[str] = None
    precision: Optional[int] = None
    key: str = field(default="")
    office: Optional[str] = None
    location_id: Optional[str] = None


@dataclass
class ReportSpec:
    district: str
    name: str
    logo_left: Optional[str] = None
    logo_right: Optional[str] = None


@dataclass
class Config:
    office: str
    cda_api_root: Optional[str] = None
    report: ReportSpec | Dict[str, Any] | None = None
    projects: List[ProjectSpec] = field(default_factory=list)
    columns: List[ColumnSpec] = field(default_factory=list)
    begin: Optional[str] = None  # ISO or relative like "24h"
    end: Optional[str] = None  # ISO
    default_unit: str = "EN"

    @staticmethod
    def from_yaml(path: str) -> "Config":
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        # env fallbacks
        office = (
            raw.get("office")
            or os.getenv("OFFICE")
            or os.getenv("CWMS_OFFICE")
            or "SWT"
        )
        cda_api_root = raw.get("cda_api_root") or os.getenv("CDA_API_ROOT")
        report_block = raw.get("report") or {}
        # normalize report to ReportSpec
        report = ReportSpec(
            district=report_block.get("district", office),
            name=report_block.get("name", "Daily Report"),
            logo_left=report_block.get("logo_left"),
            logo_right=report_block.get("logo_right"),
        )
        # columns
        cols = []
        for i, c in enumerate(raw.get("columns", [])):
            cols.append(
                ColumnSpec(
                    title=c.get("title") or c.get("name") or f"Col{i+1}",
                    tsid=c["tsid"],
                    unit=c.get("unit"),
                    precision=c.get("precision"),
                    key=c.get("key") or c.get("title") or f"c{i+1}",
                    office=c.get("office"),
                    location_id=c.get("location_id"),
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

        return Config(
            office=office,
            cda_api_root=cda_api_root,
            report=report,
            projects=projects,
            columns=cols,
            begin=raw.get("begin"),
            end=raw.get("end"),
            default_unit=raw.get("default_unit") or "EN",
        )


# ---------- Helpers ----------
def _parse_time_or_relative(s: Optional[str]) -> Optional[datetime]:
    """
    Accepts ISO strings (with or without tz) or relative like "24h", "3d", "90m".
    Returns timezone-aware UTC datetimes (or None).
    """
    if not s:
        return None
    s = str(s).strip()
    # relative
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
    # ISO parse
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        raise click.BadParameter(f"Invalid datetime: {s}")
    # ensure tz-aware -> UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _ensure_tz(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
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
    # expected columns: 'date-time', 'name', 'value' (possibly 'quality-code')
    # make sure types are reasonable
    if "date-time" in df.columns:
        df["date-time"] = pd.to_datetime(df["date-time"], utc=True, errors="coerce")
    return df


def _last_values_by_name(df: pd.DataFrame) -> Dict[str, float | None]:
    """
    For a melted dataframe with 'name' and 'date-time' and 'value',
    return the last (by time) non-null value for each name.
    """
    if df.empty:
        return {}
    work = df.dropna(subset=["value"])
    if work.empty:
        return {}
    # sort then groupby tail(1)
    print(work.columns, flush=True)
    work = work.sort_values(["ts_id", "date-time"])
    last = work.groupby("ts_id").tail(1)
    return dict(zip(last["ts_id"], last["value"]))


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
    # Use the built-in package templates if no user dir is given
    if not template_dir:
        pkg_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "templates", "jinja")
        )
        print(pkg_dir, flush=True)
        if os.path.isdir(pkg_dir):
            loaders.append(jinja2.FileSystemLoader(pkg_dir))
    # User-specified template dir (highest priority)
    if template_dir and os.path.isdir(template_dir):
        loaders.append(jinja2.FileSystemLoader(template_dir))

    # Fallback minimal inline template if not found
    env = jinja2.Environment(
        loader=jinja2.ChoiceLoader(loaders) if loaders else None,
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    try:
        if not template_name:
            template_name = "report.html.j2"
        tmpl = env.get_template(template_name)
        return tmpl.render(**context)
    except Exception as e:
        # ultra-simple built-in fallback table
        # (lets the command succeed even if no templates are set up yet)
        cols = context["columns"]
        rows = context["rows"]
        data = context["data"]
        title = f'{context.get("report",{}).get("district","") or context.get("office","") } {context.get("report",{}).get("name","Report")}'
        head = (
            "<tr><th>Project</th>"
            + "".join(f"<th>{c['title']}</th>" for c in cols)
            + "</tr>"
        )
        body = []
        for proj in rows:
            tds = [f"<td>{proj}</td>"]
            for c in cols:
                tds.append(f"<td>{data.get(proj,{}).get(c['key'],'-')}</td>")
            body.append("<tr>" + "".join(tds) + "</tr>")
        html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>table{{border-collapse:collapse}}td,th{{border:1px solid #444;padding:4px}}</style>
</head><body>
<h2>{title}</h2>
<table>{head}{''.join(body)}</table>
</body></html>"""
        click.echo(
            f"[reporting] Using built-in fallback template because '{template_name}' was not found.\nError: ({e})",
            err=True,
        )
        return html


# ---------- Main routine ----------
def build_report_table(
    config: Config, begin: Optional[datetime], end: Optional[datetime]
) -> Dict[str, Any]:
    # rows remain as simple strings for template compatibility
    rows: List[str] = [p.location_id for p in config.projects]
    if not rows:
        raise click.UsageError("No 'projects' configured in YAML.")

    # quick lookup
    proj_by_id: Dict[str, ProjectSpec] = {p.location_id: p for p in config.projects}

    # columns with fallback office/unit
    col_defs: List[Dict[str, Any]] = []
    for c in config.columns:
        col_defs.append(
            {
                "title": c.title,
                "key": c.key or c.title,
                "precision": c.precision,
                "unit": c.unit or config.default_unit,
                "tsid_template": c.tsid,
                "office": c.office or config.office,  # <- fallback here
            }
        )

    # group tsids by (office, unit)
    group_tsids: Dict[tuple, List[str]] = {}  # (office, unit) -> tsids
    backref: Dict[tuple, List[tuple]] = (
        {}
    )  # (office, unit, tsid) -> [(project_id, column_key)]

    for proj_id in rows:
        for c in col_defs:
            tsid = _expand_tsid(c["tsid_template"], proj_id)
            k = (c["office"], c["unit"])
            group_tsids.setdefault(k, [])
            if tsid not in group_tsids[k]:
                group_tsids[k].append(tsid)
            backref.setdefault((c["office"], c["unit"], tsid), []).append(
                (proj_id, c["key"])
            )

    # fetch & last values
    last_value_by_key: Dict[tuple, float | None] = {}
    for (office, unit), tsids in group_tsids.items():
        if not tsids:
            continue
        df = _fetch_multi_df(tsids, office, unit, begin, end)
        last_vals = _last_values_by_name(df)
        for ts in tsids:
            last_value_by_key[(office, unit, ts)] = last_vals.get(ts)

    # prefetch project locations once and graft href
    proj_locations: Dict[str, Dict[str, Any]] = {}
    for proj_id in rows:
        proj = proj_by_id[proj_id]
        proj_office = proj.office or config.office
        try:
            loc = cwms.get_location(office_id=proj_office, location_id=proj_id)
            loc_json = (
                getattr(loc, "json", None) or loc
            )  # cwms-python returns object w/ .json
            if isinstance(loc_json, dict):
                loc_json = {**loc_json}
                if proj.href:
                    loc_json["href"] = proj.href
            else:
                loc_json = {"name": proj_id, "href": proj.href}
        except Exception:
            loc_json = {"name": proj_id, "href": proj.href}
        proj_locations[proj_id] = loc_json

    # build the table payload
    table: Dict[str, Dict[str, Any]] = {proj_id: {} for proj_id in rows}

    for (office, unit, tsid), pairs in backref.items():
        raw_val = last_value_by_key.get((office, unit, tsid))
        for proj_id, col_key in pairs:
            col = next((c for c in col_defs if c["key"] == col_key), None)
            precision = col.get("precision") if col else None
            table[proj_id][col_key] = _format_number(raw_val, precision)

    # attach location block (with href) per project row
    for proj_id in rows:
        table[proj_id]["location"] = proj_locations.get(proj_id, {"name": proj_id})

    return {
        "columns": col_defs,
        "rows": rows,  # still a list of project IDs for your template loop
        "data": table,  # data[proj]["location"]["href"] now exists (if provided)
    }


# ---------- Click entry ----------
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
    # Load config
    cfg = Config.from_yaml(config_path)

    # Resolve time window
    cfg_begin = (
        _parse_time_or_relative(begin) if begin else _parse_time_or_relative(cfg.begin)
    )
    cfg_end = _parse_time_or_relative(end) if end else _parse_time_or_relative(cfg.end)
    if cfg_end is None:
        cfg_end = datetime.now(timezone.utc)
    if cfg_begin is None:
        # CWMS default is end-24h, but we make it explicit here
        cfg_begin = cfg_end - timedelta(hours=24)

    # Configure cwms client API root if provided
    cwms.init_session(api_root=cfg.cda_api_root)

    # Build table data
    print(cfg)
    table_ctx = build_report_table(cfg, cfg_begin, cfg_end)

    # Render
    base_date = cfg_end.astimezone(timezone.utc)
    context = {
        "office": cfg.office,
        "report": dataclasses_asdict(cfg.report),
        "base_date": base_date,
        **table_ctx,
    }
    print("TEMPLATE DIR", template_dir)
    html = _render_template(template_dir, template_name, context)

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
