"""Installed compatibility entry points for the legacy command names."""

import os
import sys

from colorama import just_fix_windows_console

from cwmscli.dss.cli import export_cmd, import_cmd
from cwmscli.utils import colors


def dss2cwms_main() -> None:
    _enable_terminal_colors()
    import_cmd.main(args=_normalize_legacy_args(sys.argv[1:]), prog_name="dss2cwms")


def cwms2dss_main() -> None:
    _enable_terminal_colors()
    export_cmd.main(args=_normalize_legacy_args(sys.argv[1:]), prog_name="cwms2dss")


def _enable_terminal_colors() -> None:
    just_fix_windows_console()
    colors.set_enabled(sys.stdout.isatty() and "NO_COLOR" not in os.environ)


def _normalize_legacy_args(args: list[str]) -> list[str]:
    """Translate legacy ``-option=value`` forms into Click-compatible tokens."""
    normalized = []
    prefixes = ("-dss", "-db", "-id", "-f2", "-tz", "-o", "-f", "-p", "-v", "-l")
    index = 0
    while index < len(args):
        argument = args[index]
        for prefix in prefixes:
            marker = f"{prefix}="
            if argument.lower().startswith(marker):
                value = argument[len(marker) :]
                # PowerShell can split an unquoted ``-dss=file.dss`` into
                # ``-dss=file`` and ``.dss`` before invoking the entry point.
                if index + 1 < len(args) and args[index + 1].startswith("."):
                    value += args[index + 1]
                    index += 1
                normalized.extend((prefix, value))
                break
        else:
            normalized.append(argument)
        index += 1
    return normalized
