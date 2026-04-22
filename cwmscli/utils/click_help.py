from __future__ import annotations

import sys
from typing import Optional

import click

from cwmscli.ownership import get_command_maintainers, get_core_maintainer_emails
from cwmscli.utils import colors
from cwmscli.utils.version import get_cwms_cli_version

DOCS_BASE_URL = "https://cwms-cli.readthedocs.io/en/latest"
SHELL_COMPLETION_DOCS_URL = f"{DOCS_BASE_URL}/cli/shell_completion.html"


def _render_version_line(ctx: click.Context) -> str:
    # Match existing CLI color behavior: disable color for non-TTY, --no-color, or --log-file.
    argv = sys.argv[1:]
    no_color = "--no-color" in argv
    has_log_file = ("--log-file" in argv) or any(
        arg.startswith("--log-file=") for arg in argv
    )
    allow_color = sys.stdout.isatty() and (not no_color) and (not has_log_file)
    colors.set_enabled(allow_color)
    return f"Version: {colors.c(get_cwms_cli_version(), 'cyan', bright=True)}"


def _docs_url_for_context(ctx: click.Context) -> Optional[str]:
    # Show docs links only on command root pages:
    # - cwms-cli --help (depth 1)
    # - cwms-cli <top-level-command> --help (depth 2)
    depth = 0
    cur = ctx
    while cur is not None:
        depth += 1
        cur = cur.parent

    if depth == 1:
        return f"{DOCS_BASE_URL}/cli.html"
    if depth != 2:
        return None

    command = (ctx.info_name or getattr(ctx.command, "name", None) or "").strip()
    page_map = {
        "blob": "blob",
        "update": "update",
        "users": "users",
        "version": "version",
    }
    # Link to dedicated pages that are created in \docs
    if command in page_map:
        return f"{DOCS_BASE_URL}/cli/{page_map[command]}.html"

    # Fallback to the root CLI page with command anchor.
    return f"{DOCS_BASE_URL}/cli.html#cwms-cli-{command}"


def _render_docs_line(ctx: click.Context) -> Optional[str]:
    docs_url = _docs_url_for_context(ctx)
    if docs_url is None:
        return None
    return f"Docs: {colors.c(docs_url, 'blue', bright=True)}"


def _render_shell_completion_line(ctx: click.Context) -> Optional[str]:
    if ctx.parent is not None:
        return None
    return (
        f"Shell completion: {colors.c(SHELL_COMPLETION_DOCS_URL, 'blue', bright=True)}"
    )


def _command_path(ctx: click.Context) -> str:
    names: list[str] = []
    cur: Optional[click.Context] = ctx
    while cur is not None:
        name = (cur.info_name or getattr(cur.command, "name", None) or "").strip()
        if name:
            if cur.parent is None:
                name = "cwms-cli"
            names.append(name)
        cur = cur.parent
    names.reverse()
    return " ".join(names)


def _render_maintainers_line(ctx: click.Context) -> str:
    command_path = _command_path(ctx)
    core_emails = get_core_maintainer_emails()
    rendered = []
    for person in get_command_maintainers(command_path):
        name = person["name"]
        if person["email"] in core_emails:
            name = colors.c(name, "blue", bright=True)
        rendered.append(name)
    return f"Maintainers: {', '.join(rendered)}"


def _inject_help_header(help_text: str, ctx: click.Context) -> str:
    lines = help_text.splitlines()
    if not lines:
        return help_text

    plain_version_line = f"Version: {get_cwms_cli_version()}"
    if any(line.strip() == plain_version_line for line in lines):
        return help_text

    version_line = _render_version_line(ctx)
    docs_line = _render_docs_line(ctx)
    shell_completion_line = _render_shell_completion_line(ctx)
    maintainers_line = _render_maintainers_line(ctx)
    if lines[0].startswith("Usage:"):
        lines.insert(1, version_line)
        if docs_line is not None:
            lines.insert(2, docs_line)
            lines.insert(3, maintainers_line)
        else:
            lines.insert(2, maintainers_line)
        if shell_completion_line is not None:
            insert_at = 3 if docs_line is not None else 2
            if docs_line is not None:
                insert_at += 1
            lines.insert(insert_at, shell_completion_line)
    else:
        lines.insert(0, version_line)
        if docs_line is not None:
            lines.insert(1, docs_line)
            lines.insert(2, maintainers_line)
        else:
            lines.insert(1, maintainers_line)
        if shell_completion_line is not None:
            insert_at = 2 if docs_line is not None else 1
            if docs_line is not None:
                insert_at += 1
            lines.insert(insert_at, shell_completion_line)
    return "\n".join(lines)


def _wrap_get_help(command: click.Command) -> None:
    original_get_help = command.get_help

    def get_help_with_header(ctx: click.Context) -> str:
        return _inject_help_header(original_get_help(ctx), ctx)

    command.get_help = get_help_with_header  # type: ignore[method-assign]


def add_version_to_help_tree(command: click.Command) -> None:
    """Patch a command tree so every help output shows the CLI version and docs link."""
    stack = [command]
    seen: set[int] = set()

    while stack:
        cmd = stack.pop()
        obj_id = id(cmd)
        if obj_id in seen:
            continue
        seen.add(obj_id)

        _wrap_get_help(cmd)

        if isinstance(cmd, click.Group):
            stack.extend(cmd.commands.values())
