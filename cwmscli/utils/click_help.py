from __future__ import annotations

import sys

import click

from cwmscli.utils import colors
from cwmscli.utils.version import get_cwms_cli_version


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


def _inject_version_line(help_text: str, ctx: click.Context) -> str:
    lines = help_text.splitlines()
    if not lines:
        return help_text

    plain_version_line = f"Version: {get_cwms_cli_version()}"
    if any(line.strip() == plain_version_line for line in lines):
        return help_text

    version_line = _render_version_line(ctx)
    if lines[0].startswith("Usage:"):
        lines.insert(1, version_line)
    else:
        lines.insert(0, version_line)
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
