from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import click

from cwmscli.reporting.config import Config
from cwmscli.reporting.context import build_report_table
from cwmscli.reporting.renderers import (
    list_builtin_templates,
    render_html,
    render_template_text,
    render_text,
)
from cwmscli.reporting.timeseries import build_time_series_context
from cwmscli.reporting.utils.date import parse_when
from cwmscli.utils import colors
from cwmscli.utils.deps import requires

LOGGER = logging.getLogger(__name__)


@click.group(
    name="report",
    help="Generate CWMS reports from declarative YAML definitions.",
)
def report_cli() -> None:
    pass


def _status(label: str, detail: str, color: str = "cyan") -> None:
    LOGGER.info("%s %s", colors.c(label, color, bright=True), detail)


def _build_context(config_path: str):
    _status("[report]", f"Loading config: {config_path}", "cyan")
    config = Config.from_yaml(config_path)
    _status(
        "[report]",
        f"Office={config.office}; dataset={config.dataset.kind}; "
        f"projects={len(config.projects)}; columns={len(config.columns)}",
        "green",
    )
    tz = config.time_zone or "UTC"
    begin_dt: Optional[datetime] = (
        parse_when(config.begin, tz) if config.begin else None
    )
    end_dt: Optional[datetime] = parse_when(config.end, tz) if config.end else None
    if begin_dt and end_dt and end_dt < begin_dt:
        raise click.ClickException(
            f"'end' ({end_dt.isoformat()}) must be after 'begin' ({begin_dt.isoformat()})"
        )
    if begin_dt or end_dt:
        _status(
            "[report]",
            f"Time window begin={begin_dt.isoformat() if begin_dt else '<none>'}; "
            f"end={end_dt.isoformat() if end_dt else '<none>'}",
            "cyan",
        )

    import cwms

    _status(
        "[report]",
        f"Initializing CWMS session: {config.cda_api_root or '<cwms-python default>'}",
        "cyan",
    )
    cwms.init_session(api_root=config.cda_api_root)
    _status("[report]", "Fetching CWMS data and shaping report context", "cyan")
    if config.dataset.kind == "time_series":
        table_context = build_time_series_context(config, begin_dt, end_dt)
    else:
        table_context = build_report_table(config, begin_dt, end_dt)
    _status(
        "[report]",
        f"Fetched report rows={len(table_context.get('rows', []))}; "
        f"columns={len(table_context.get('columns', []))}",
        "green",
    )
    base_date = table_context.get(
        "base_end", end_dt or datetime.now(timezone.utc)
    ).astimezone(timezone.utc)
    return config, {
        "office": config.office,
        "report": dataclasses_asdict(config.report),
        "dataset": dataclasses_asdict(config.dataset),
        "template": dataclasses_asdict(config.template),
        "base_date": base_date,
        "generated_at": datetime.now(timezone.utc),
        "header": dataclasses_asdict(config.header),
        **table_context,
    }


def _default_output_path(out_path: Optional[str], default_extension: str) -> str:
    return out_path or f"report{default_extension}"


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
        "version": "1.0.7",
        "desc": "CWMS REST API client for report data retrieval",
    },
    {
        "module": "pandas",
        "package": "pandas",
        "version": "2.0.0",
        "desc": "Timeseries table shaping for reports",
    },
)

PANDAS_REQUIREMENT = {
    "module": "pandas",
    "package": "pandas",
    "version": "2.0.0",
    "desc": "Tabular display for report templates",
}


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
    "--template",
    "template_name",
    default=None,
    help="Built-in template name. Default: template.name from config or WM-Daily.",
)
@click.option(
    "--template-file",
    "template_file",
    type=click.Path(exists=True, dir_okay=False),
    help="Local Jinja template file. Overrides built-in template selection.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["html", "text"], case_sensitive=False),
    default="html",
    show_default=True,
    help="Rendered report format.",
)
@click.option(
    "--out",
    "-o",
    "out_path",
    default=None,
    type=click.Path(dir_okay=False),
    help="Output path. Defaults to report.html or report.txt.",
)
@requires(*REPORTING_REQUIREMENTS)
def generate_report_cli(
    config_path,
    template_name,
    template_file,
    output_format,
    out_path,
):
    config, context = _build_context(config_path)
    if output_format.lower() == "text":
        configured_template_file = (
            config.template.path
            or config.template.source
            not in {
                "builtin",
                "package",
            }
        )
        if (
            template_file
            or configured_template_file
            or (template_name or config.template.name) != "WM-Daily"
        ):
            template_detail = (
                f"user template file {template_file}"
                if template_file
                else f"built-in template {template_name or config.template.name}"
            )
            _status("[report]", f"Rendering text with {template_detail}", "cyan")
            result = render_template_text(
                config,
                context,
                template_name=template_name,
                template_file=template_file,
            )
        else:
            _status("[report]", "Rendering text output", "cyan")
            result = render_text(config, context)
    else:
        template_detail = (
            f"user template file {template_file}"
            if template_file
            else f"built-in template {template_name or config.template.name or 'WM-Daily'}"
        )
        _status("[report]", f"Rendering HTML with {template_detail}", "cyan")
        result = render_html(
            config,
            context,
            template_name=template_name,
            template_file=template_file,
        )

    final_out_path = _default_output_path(out_path, result.default_extension)
    with open(final_out_path, "w", encoding="utf-8", newline="") as file:
        file.write(result.content)
    _status("[report]", f"Wrote {final_out_path}", "green")


@report_cli.group(name="templates")
def templates_cli() -> None:
    """Inspect built-in report templates."""


@templates_cli.command(name="list")
@click.option(
    "--template-file",
    "template_files",
    multiple=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Local user-defined template file to include in the list.",
)
@requires(PANDAS_REQUIREMENT)
def list_templates_cli(template_files) -> None:
    import pandas as pd

    rows = []
    for name, info in sorted(list_builtin_templates().items()):
        rows.append(
            {
                "Template": name,
                "Source": "builtin",
                "Description": info["description"],
            }
        )

    for template_file in template_files:
        rows.append(
            {
                "Template": template_file,
                "Source": "user-defined",
                "Description": "Local template file",
            }
        )

    table = pd.DataFrame(rows, columns=["Template", "Source", "Description"])
    click.echo(_format_templates_table(table))


def _format_templates_table(table) -> str:
    columns = list(table.columns)
    widths = {
        column: max(len(str(column)), *(len(str(value)) for value in table[column]))
        for column in columns
    }

    def render_cell(column, value):
        text = str(value)
        if column == "Source":
            if text == "builtin":
                rendered = colors.c(text, "green", bright=True)
            elif text == "user-defined":
                rendered = colors.c(text, "cyan", bright=True)
            else:
                rendered = text
        else:
            rendered = text
        return rendered + (" " * (widths[column] - len(text)))

    lines = [" ".join(str(column).ljust(widths[column]) for column in columns)]
    for _, row in table.iterrows():
        lines.append(" ".join(render_cell(column, row[column]) for column in columns))
    return "\n".join(lines)


def dataclasses_asdict(obj):
    if obj is None:
        return None
    if hasattr(obj, "__dataclass_fields__"):
        return {
            field: dataclasses_asdict(getattr(obj, field))
            for field in obj.__dataclass_fields__
        }
    if isinstance(obj, (list, tuple)):
        return [dataclasses_asdict(value) for value in obj]
    if isinstance(obj, dict):
        return {key: dataclasses_asdict(value) for key, value in obj.items()}
    return obj
