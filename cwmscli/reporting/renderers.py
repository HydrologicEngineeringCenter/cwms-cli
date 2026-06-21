from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import click

from cwmscli.reporting.config import Config
from cwmscli.utils.deps import requires


@dataclass
class RenderResult:
    content: str
    default_extension: str


BUILTIN_TEMPLATES = {
    "WM-Daily": {
        "description": "Generic Water Management daily table report.",
        "template": "report.html.j2",
    },
}


def list_builtin_templates() -> Dict[str, Dict[str, str]]:
    return dict(BUILTIN_TEMPLATES)


def _builtin_template_dir() -> str:
    return os.path.join(os.path.dirname(__file__), "templates", "jinja")


def _resolve_template(
    config: Config,
    *,
    template_name: Optional[str] = None,
    template_file: Optional[str] = None,
) -> tuple[str, str]:
    if template_file:
        path = Path(template_file)
        return str(path.parent), path.name

    if config.template.source not in {"builtin", "package"}:
        if config.template.path:
            path = Path(config.template.path)
            return str(path.parent), path.name
        raise click.BadParameter(
            "Only builtin templates and local template files are supported in this MVP."
        )

    selected = template_name or config.template.name or "WM-Daily"
    builtins = list_builtin_templates()
    match = next((name for name in builtins if name.lower() == selected.lower()), None)
    if not match:
        available = ", ".join(sorted(builtins))
        raise click.BadParameter(
            f"Unknown built-in report template '{selected}'. Available: {available}"
        )
    return _builtin_template_dir(), builtins[match]["template"]


def render_html(
    config: Config,
    context: Dict[str, Any],
    *,
    template_name: Optional[str] = None,
    template_file: Optional[str] = None,
) -> RenderResult:
    @requires(
        {
            "module": "jinja2",
            "package": "Jinja2",
            "version": "3.1.0",
            "desc": "HTML report templating",
        }
    )
    def _render() -> str:
        import jinja2

        template_dir, selected_template = _resolve_template(
            config,
            template_name=template_name,
            template_file=template_file,
        )
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dir),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        return env.get_template(selected_template).render(**context)

    return RenderResult(content=_render(), default_extension=".html")


def _align_text(value: str, width: int, align: str) -> str:
    if align == "right":
        return value.rjust(width)
    if align == "center":
        return value.center(width)
    return value.ljust(width)


def render_text(config: Config, context: Dict[str, Any]) -> RenderResult:
    columns = context["columns"]
    rows = context["rows"]
    data = context["data"]
    spacing = "  "
    project_label = "Project"
    project_width = max(
        len(project_label),
        max(len(str(data[row]["location"].get("public-name") or row)) for row in rows),
    )

    resolved_columns = []
    for column in columns:
        cell_values = [
            str(data[row].get(column["key"], {}).get("text", "")) for row in rows
        ]
        width = max(
            int(column.get("width") or 0),
            len(str(column["title"])),
            max((len(value) for value in cell_values), default=0),
        )
        resolved_columns.append(
            {
                "key": column["key"],
                "title": str(column["title"]),
                "width": width,
                "align": str(column.get("align") or "right"),
            }
        )

    table_width = project_width + sum(
        len(spacing) + column["width"] for column in resolved_columns
    )
    title_lines = list(config.report.title_lines or [])
    if not title_lines:
        title_lines = [config.report.district, config.report.name]

    lines = [
        _align_text(str(line), table_width, "center").rstrip() for line in title_lines
    ]
    lines.append("")
    lines.append(
        spacing.join(
            [_align_text(project_label, project_width, "left")]
            + [
                _align_text(column["title"], column["width"], "center")
                for column in resolved_columns
            ]
        ).rstrip()
    )
    lines.append("-" * table_width)

    for row in rows:
        cells = [
            _align_text(
                str(data[row]["location"].get("public-name") or row),
                project_width,
                "left",
            )
        ]
        for column in resolved_columns:
            cells.append(
                _align_text(
                    str(data[row].get(column["key"], {}).get("text", "")),
                    column["width"],
                    column["align"],
                )
            )
        lines.append(spacing.join(cells).rstrip())

    footer_lines = list(config.report.footer_lines or [])
    if footer_lines:
        lines.append("")
        lines.extend(str(line) for line in footer_lines)

    return RenderResult(
        content="\n".join(lines).rstrip() + "\n", default_extension=".txt"
    )
