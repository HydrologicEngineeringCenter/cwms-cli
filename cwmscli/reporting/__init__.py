from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import click

from cwmscli.reporting.config import Config
from cwmscli.reporting.core import build_monthly_project_report, build_report_table
from cwmscli.reporting.engines import render_report
from cwmscli.reporting.utils.date import parse_when
from cwmscli.utils.deps import requires


@click.group(
    name="report",
    help="Generate CWMS reports from a declarative YAML definition.",
)
def report_cli() -> None:
    pass


def _normalize_month_expr(month_expr: Optional[str]) -> Optional[str]:
    if month_expr is None:
        return None
    value = str(month_expr).strip()
    if not value:
        return None
    if len(value) == 7 and value[4] == "-":
        year_s, month_s = value.split("-", 1)
        return f"{int(year_s):04d}-{int(month_s):02d}"
    if len(value) == 7 and value[2] == "/":
        month_s, year_s = value.split("/", 1)
        return f"{int(year_s):04d}-{int(month_s):02d}"
    raise click.BadParameter("Month must be in YYYY-MM or MM/YYYY format.")


def _build_context(
    config_path: str,
    *,
    location: Optional[str] = None,
    month: Optional[str] = None,
):
    cfg = Config.from_yaml(config_path)
    dataset_options = dict(cfg.dataset.options or {})
    if location:
        location_id = str(location).strip().upper()
        dataset_options["location"] = location_id
        dataset_options["project"] = location_id
    normalized_month = _normalize_month_expr(month)
    if normalized_month:
        dataset_options["month"] = normalized_month
    cfg.dataset.options = dataset_options

    if cfg.dataset.kind in {"monthly_project", "monthly_location"}:
        import cwms

        cwms.init_session(api_root=cfg.cda_api_root)
        report_ctx = build_monthly_project_report(cfg)
        base_date = report_ctx.get("base_end", datetime.now(timezone.utc)).astimezone(
            timezone.utc
        )
        return cfg, {
            "office": cfg.office,
            "report": dataclasses_asdict(cfg.report),
            "engine": dataclasses_asdict(cfg.engine),
            "dataset": dataclasses_asdict(cfg.dataset),
            "template": dataclasses_asdict(cfg.template),
            "base_date": base_date,
            "generated_at": datetime.now(timezone.utc),
            **report_ctx,
        }

    tz = cfg.time_zone or "UTC"
    begin_dt: Optional[datetime] = parse_when(cfg.begin, tz) if cfg.begin else None
    end_dt: Optional[datetime] = parse_when(cfg.end, tz) if cfg.end else None

    if begin_dt and end_dt and end_dt < begin_dt:
        raise click.ClickException(
            f"'end' ({end_dt.isoformat()}) must be after 'begin' ({begin_dt.isoformat()})"
        )

    import cwms

    cwms.init_session(api_root=cfg.cda_api_root)
    table_ctx = build_report_table(cfg, begin_dt, end_dt)
    base_date = table_ctx.get(
        "base_end", end_dt or datetime.now(timezone.utc)
    ).astimezone(timezone.utc)
    return cfg, {
        "office": cfg.office,
        "report": dataclasses_asdict(cfg.report),
        "engine": dataclasses_asdict(cfg.engine),
        "dataset": dataclasses_asdict(cfg.dataset),
        "template": dataclasses_asdict(cfg.template),
        "base_date": base_date,
        "generated_at": datetime.now(timezone.utc),
        "header": dataclasses_asdict(cfg.header),
        **table_ctx,
    }


def _default_output_path(out_path: Optional[str], default_extension: str) -> str:
    if out_path:
        return out_path
    return f"report{default_extension}"


REPORTING_REQUIREMENTS = (
    {
        "module": "yaml",
        "package": "PyYAML",
        "version": "6.0",
        "desc": "YAML parsing for report configuration",
    },
    {
        "module": "cwms",
        "package": "cwms-python",
        "version": "0.8.0",
        "desc": "CWMS REST API client for report data retrieval",
    },
    {
        "module": "pandas",
        "package": "pandas",
        "version": "2.0.0",
        "desc": "Timeseries table shaping for reports",
    },
)


@report_cli.command(name="generate")
@click.option(
    "--config",
    "-c",
    "config_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to report YAML definition.",
)
@click.option(
    "--location",
    "--project",
    "location_id",
    default=None,
    help="Override the report location id, for example KEYS or OOLO.",
)
@click.option(
    "--month",
    "month_expr",
    default=None,
    help="Override the report month. Accepts YYYY-MM or MM/YYYY.",
)
@click.option(
    "--engine",
    "engine_name",
    default=None,
    help="Override the engine declared in the config. Built-ins: text, jinja2.",
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
    "--out",
    "-o",
    "out_path",
    default=None,
    type=click.Path(dir_okay=False),
    help="Output path. Defaults to report.txt or report.html based on the selected engine.",
)
@requires(*REPORTING_REQUIREMENTS)
def generate_report_cli(
    config_path,
    location_id,
    month_expr,
    engine_name,
    template_dir,
    template_name,
    out_path,
):
    cfg, context = _build_context(
        config_path,
        location=location_id,
        month=month_expr,
    )
    result = render_report(
        cfg,
        context,
        engine_name=engine_name,
        template_dir=template_dir,
        template_name=template_name,
    )
    final_out_path = _default_output_path(out_path, result.default_extension)
    with open(final_out_path, "w", encoding="utf-8") as f:
        f.write(result.content)
    click.echo(f"Wrote {final_out_path}")


def dataclasses_asdict(obj):
    # Custom dataclass to dict, recursive
    # Guarantees we end up with a structure made of only "safe" Python types:
    # dicts, lists, tuples, numbers, strings, None.
    # Helper for Jinja2 or JSON data structures
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
