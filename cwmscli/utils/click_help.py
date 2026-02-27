from __future__ import annotations

import sys

import click

from cwmscli.utils import colors
from cwmscli.utils.version import get_cwms_cli_version

DOCS_BASE_URL = "https://cwms-cli.readthedocs.io/en/latest"


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


def _docs_url_for_context(ctx: click.Context) -> str | None:
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
        "version": "version",
    }
    # Link to dedicated pages that are created in \docs
    if command in page_map:
        return f"{DOCS_BASE_URL}/cli/{page_map[command]}.html"

    # Fallback to the root CLI page with command anchor.
    return f"{DOCS_BASE_URL}/cli.html#cwms-cli-{command}"


def _render_docs_line(ctx: click.Context) -> str | None:
    docs_url = _docs_url_for_context(ctx)
    if docs_url is None:
        return None
    return f"Docs: {colors.c(docs_url, 'blue', bright=True)}"


def _inject_version_line(help_text: str, ctx: click.Context) -> str:
    lines = help_text.splitlines()
    if not lines:
        return help_text

    plain_version_line = f"Version: {get_cwms_cli_version()}"
    if any(line.strip() == plain_version_line for line in lines):
        return help_text

    version_line = _render_version_line(ctx)
    docs_line = _render_docs_line(ctx)
    if lines[0].startswith("Usage:"):
        lines.insert(1, version_line)
        if docs_line is not None:
            lines.insert(2, docs_line)
    else:
        lines.insert(0, version_line)
        if docs_line is not None:
            lines.insert(1, docs_line)
    return "\n".join(lines)


def _wrap_get_help(command: click.Command) -> None:
    original_get_help = command.get_help

    def get_help_with_version(ctx: click.Context) -> str:
        return _inject_version_line(original_get_help(ctx), ctx)

    command.get_help = get_help_with_version  # type: ignore[method-assign]


def add_version_to_help_tree(command: click.Command) -> None:
    """Patch a command tree so every help output shows the CLI version."""
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
