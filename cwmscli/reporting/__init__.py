from __future__ import annotations

import os
import traceback
from datetime import timezone
from typing import Any, Dict, List, Optional

import click

from cwmscli.reporting.config import Config
from cwmscli.reporting.core import build_report_table
from cwmscli.reporting.utils.date import parse_when
from cwmscli.utils.deps import requires


def _render_template(
    template_dir: Optional[str],
    template_name: str | None,
    context: Dict[str, Any],
) -> str:
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
def reporting_cli(config_path, template_dir, template_name, out_path):
    import cwms

    cfg = Config.from_yaml(config_path)

    tz = cfg.time_zone or "UTC"

    # Global window: optional
    begin_dt: Optional[datetime] = parse_when(cfg.begin, tz) if cfg.begin else None
    end_dt: Optional[datetime] = parse_when(cfg.end, tz) if cfg.end else None

    # If both provided, sanity check ordering
    if begin_dt and end_dt and end_dt < begin_dt:
        raise click.ClickException(
            f"'end' ({end_dt.isoformat()}) must be after 'begin' ({begin_dt.isoformat()})"
        )

    cwms.init_session(api_root=cfg.cda_api_root)
    table_ctx = build_report_table(cfg, begin_dt, end_dt)

    base_date = table_ctx.get(
        "base_end", end_dt or datetime.now(timezone.utc)
    ).astimezone(timezone.utc)
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
