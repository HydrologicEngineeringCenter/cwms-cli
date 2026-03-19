from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import click

from cwmscli.reporting.config import Config
from cwmscli.utils.deps import requires


@dataclass
class RenderResult:
    content: str
    default_extension: str


def _render_jinja2(
    config: Config,
    context: Dict[str, Any],
    *,
    template_dir: Optional[str],
    template_name: Optional[str],
) -> RenderResult:
    @requires(
        {
            "module": "jinja2",
            "package": "Jinja2",
            "version": "3.1.0",
            "desc": "Templating for report rendering",
        }
    )
    def _render() -> str:
        import jinja2

        loaders = []
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
        template = env.get_template(template_name or "report.html.j2")
        return template.render(**context)

    return RenderResult(content=_render(), default_extension=".html")


def _align_text(value: str, width: int, align: str) -> str:
    if align == "right":
        return value.rjust(width)
    if align == "center":
        return value.center(width)
    return value.ljust(width)


def _render_text(
    config: Config,
    context: Dict[str, Any],
    *,
    template_dir: Optional[str],
    template_name: Optional[str],
) -> RenderResult:
    del template_dir, template_name

    columns = context["columns"]
    rows = context["rows"]
    data = context["data"]
    options = config.engine.options or {}
    spacing = " " * int(options.get("column_spacing", 2))
    project_label = str(options.get("project_label", "Project"))
    project_align = str(options.get("project_align", "left"))
    project_width = max(
        int(options.get("project_width", len(project_label))),
        len(project_label),
        max(len(str(data[row]["location"].get("public-name") or row)) for row in rows),
    )

    resolved_columns = []
    for col in columns:
        cell_values = [
            str(data[row].get(col["key"], {}).get("text", "")) for row in rows
        ]
        width = max(
            int(col.get("width") or 0),
            len(str(col["title"])),
            max((len(v) for v in cell_values), default=0),
        )
        resolved_columns.append(
            {
                "key": col["key"],
                "title": str(col["title"]),
                "width": width,
                "align": str(col.get("align") or "right"),
            }
        )

    table_width = project_width
    if resolved_columns:
        table_width += len(spacing) * len(resolved_columns)
        table_width += sum(col["width"] for col in resolved_columns)

    title_lines = list(config.report.title_lines or [])
    if not title_lines:
        title_lines = [config.report.district, config.report.name]

    lines = [
        _align_text(str(line), table_width, "center").rstrip() for line in title_lines
    ]
    lines.append("")

    header_cells = [_align_text(project_label, project_width, project_align)]
    for col in resolved_columns:
        header_cells.append(_align_text(col["title"], col["width"], "center"))
    lines.append(spacing.join(header_cells).rstrip())
    lines.append("-" * table_width)

    for row in rows:
        row_cells = [
            _align_text(
                str(data[row]["location"].get("public-name") or row),
                project_width,
                project_align,
            )
        ]
        for col in resolved_columns:
            text = str(data[row].get(col["key"], {}).get("text", ""))
            row_cells.append(_align_text(text, col["width"], col["align"]))
        lines.append(spacing.join(row_cells).rstrip())

    footer_lines = list(config.report.footer_lines or [])
    if footer_lines:
        lines.append("")
        lines.extend(str(line) for line in footer_lines)

    return RenderResult(
        content="\n".join(lines).rstrip() + "\n", default_extension=".txt"
    )


ENGINE_REGISTRY: Dict[str, Callable[..., RenderResult]] = {
    "jinja2": _render_jinja2,
    "text": _render_text,
}


def render_report(
    config: Config,
    context: Dict[str, Any],
    *,
    engine_name: Optional[str] = None,
    template_dir: Optional[str] = None,
    template_name: Optional[str] = None,
) -> RenderResult:
    selected_engine = (engine_name or config.engine.name or "text").strip().lower()
    renderer = ENGINE_REGISTRY.get(selected_engine)
    if renderer is None:
        raise click.ClickException(
            f"Unsupported report engine '{selected_engine}'. "
            f"Available engines: {', '.join(sorted(ENGINE_REGISTRY))}"
        )

    final_template_dir = (
        template_dir if template_dir is not None else config.engine.template_dir
    )
    final_template_name = (
        template_name if template_name is not None else config.engine.template
    )
    return renderer(
        config,
        context,
        template_dir=final_template_dir,
        template_name=final_template_name,
    )
