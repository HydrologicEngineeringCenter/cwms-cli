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


def _format_numeric(
    value: Any,
    width: int,
    precision: int = 0,
    missing: str = "--",
) -> str:
    if value is None:
        return str(missing).rjust(width)
    try:
        return f"{float(value):>{width}.{precision}f}"
    except Exception:
        return str(value).rjust(width)


def _format_intish(value: Any, width: int, missing: str = "--") -> str:
    if value is None:
        return str(missing).rjust(width)
    try:
        return f"{round(float(value)):>{width}.0f}"
    except Exception:
        return str(value).rjust(width)


def _resolve_value(
    path: str,
    context: Dict[str, Any],
    row: Optional[Dict[str, Any]] = None,
) -> Any:
    if path in {"", "."}:
        return row if row is not None else context

    def _walk(value: Any, parts: list[str]) -> Any:
        cur = value
        for part in parts:
            if cur is None:
                return None
            if isinstance(cur, dict):
                cur = cur.get(part)
            else:
                cur = getattr(cur, part, None)
        return cur

    parts = path.split(".")
    if row is not None:
        row_value = _walk(row, parts)
        if row_value is not None:
            return row_value
    return _walk(context, parts)


def _render_part(
    part: Dict[str, Any],
    context: Dict[str, Any],
    row: Optional[Dict[str, Any]] = None,
) -> str:
    if "text" in part:
        value = str(part.get("text", ""))
    else:
        value = _resolve_value(str(part.get("path", "")), context, row=row)
        width = int(part.get("width") or 0)
        align = str(part.get("align") or "right")
        missing = str(part.get("missing", "--"))
        as_type = str(part.get("format") or "string")
        precision = int(part.get("precision") or 0)

        if as_type == "int":
            value = _format_intish(value, width or 1, missing=missing)
            return value
        if as_type == "float":
            value = _format_numeric(
                value, width or 1, precision=precision, missing=missing
            )
            return value
        value = "" if value is None else str(value)
        if width:
            return _align_text(value, width, align)
    return value


def _condition_matches(condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
    path = str(condition.get("path") or "").strip()
    if not path:
        return True
    value = _resolve_value(path, context)
    if "equals" in condition:
        return value == condition.get("equals")
    if "not_equals" in condition:
        return value != condition.get("not_equals")
    if "in" in condition:
        return value in (condition.get("in") or [])
    if "not_in" in condition:
        return value not in (condition.get("not_in") or [])
    return bool(value)


def _section_enabled(section: Dict[str, Any], context: Dict[str, Any]) -> bool:
    when = section.get("when")
    if when is None:
        return True
    if isinstance(when, str):
        return bool(_resolve_value(when, context))
    if isinstance(when, dict):
        return _condition_matches(when, context)
    return bool(when)


def _render_text_layout(
    config: Config,
    context: Dict[str, Any],
) -> RenderResult:
    sections = list(config.template.options.get("sections") or [])
    if not sections:
        raise click.ClickException(
            "template.sections is required for template.kind=text_layout"
        )

    lines: list[str] = []
    for section in sections:
        section = dict(section or {})
        if not _section_enabled(section, context):
            continue
        stype = str(section.get("type") or "")
        if stype == "blank":
            count = int(section.get("count") or 1)
            lines.extend("" for _ in range(count))
            continue
        if stype == "literal":
            lines.append(str(section.get("text", "")))
            continue
        if stype == "centered":
            width = int(section.get("width") or 65)
            for item in section.get("values") or []:
                if isinstance(item, dict):
                    text = _render_part(item, context)
                else:
                    text = str(item)
                lines.append(text.center(width).rstrip())
            continue
        if stype == "fields":
            parts = [dict(p or {}) for p in (section.get("parts") or [])]
            lines.append(
                "".join(_render_part(part, context) for part in parts).rstrip()
            )
            continue
        if stype == "repeat":
            source = _resolve_value(str(section.get("source", "")), context)
            if not isinstance(source, list):
                continue
            parts = [dict(p or {}) for p in (section.get("parts") or [])]
            blank_every = int(section.get("blank_every") or 0)
            for idx, item in enumerate(source, start=1):
                lines.append(
                    "".join(
                        _render_part(part, context, row=item) for part in parts
                    ).rstrip()
                )
                if blank_every and idx % blank_every == 0 and idx != len(source):
                    lines.append("")
            continue

    footer_lines = list(config.report.footer_lines or [])
    if footer_lines:
        lines.extend(str(line) for line in footer_lines)
    return RenderResult(
        content="\n".join(lines).rstrip() + "\n", default_extension=".txt"
    )


def _render_monthly_project_text(
    config: Config,
    context: Dict[str, Any],
    *,
    template_dir: Optional[str],
    template_name: Optional[str],
) -> RenderResult:
    del template_dir, template_name
    return _render_text_layout(config, context)


def _render_text(
    config: Config,
    context: Dict[str, Any],
    *,
    template_dir: Optional[str],
    template_name: Optional[str],
) -> RenderResult:
    del template_dir, template_name

    if config.template.kind == "text_layout":
        return _render_monthly_project_text(
            config,
            context,
            template_dir=None,
            template_name=None,
        )

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
