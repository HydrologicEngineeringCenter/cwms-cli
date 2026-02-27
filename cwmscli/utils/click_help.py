from __future__ import annotations

import click

from cwmscli.utils.version import get_cwms_cli_version


def _inject_version_line(help_text: str) -> str:
    lines = help_text.splitlines()
    if not lines:
        return help_text

    version_line = f"Version: {get_cwms_cli_version()}"
    if any(line.strip() == version_line for line in lines):
        return help_text

    if lines[0].startswith("Usage:"):
        lines.insert(1, version_line)
    else:
        lines.insert(0, version_line)
    return "\n".join(lines)


def _wrap_get_help(command: click.Command) -> None:
    original_get_help = command.get_help

    def get_help_with_version(ctx: click.Context) -> str:
        return _inject_version_line(original_get_help(ctx))

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
