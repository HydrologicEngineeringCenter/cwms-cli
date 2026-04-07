from __future__ import annotations

import sys
from typing import Optional

import click

from cwmscli.utils import colors
from cwmscli.utils.version import (
    get_cwms_cli_version,
    get_latest_cwms_cli_version,
    is_newer_version_available,
)


def version_output_allows_color(
    no_color: bool,
    log_file: Optional[str],
) -> bool:
    return sys.stdout.isatty() and (not no_color) and (not log_file)


def show_version_and_exit(
    ctx: click.Context, _param: click.Parameter, value: bool
) -> None:
    if not value or ctx.resilient_parsing:
        return

    current_version = get_cwms_cli_version()
    colors.set_enabled(
        version_output_allows_color(
            no_color=bool(ctx.params.get("no_color")),
            log_file=ctx.params.get("log_file"),
        )
    )

    click.echo(f"cwms-cli version {colors.c(current_version, 'cyan', bright=True)}")

    latest_version = get_latest_cwms_cli_version()
    if latest_version and is_newer_version_available(current_version, latest_version):
        click.echo(
            colors.warn("Newer version available: ")
            + colors.c(latest_version, "yellow", bright=True)
        )
        click.echo(f"Run: {colors.c('cwms-cli update', 'cyan', bright=True)}")

    ctx.exit()
