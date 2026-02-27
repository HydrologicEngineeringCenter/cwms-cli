import logging
import os
import sys
from typing import Optional

import click

from cwmscli.commands import commands_cwms
from cwmscli.load import __main__ as load
from cwmscli.usgs import usgs_group
from cwmscli.utils.logging import LoggingConfig, setup_logging
from cwmscli.utils.ssl_errors import is_cert_verify_error, ssl_help_text


@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
@click.option(
    "--log-file",
    type=click.Path(dir_okay=False, writable=True, resolve_path=True),
    default=None,
    help="Write logs to a file. If set, disables color completely.",
)
@click.option(
    "--no-color",
    is_flag=True,
    default=False,
    help="Disable colored output in the terminal.",
)
@click.option(
    "--log-level",
    type=click.Choice(
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False
    ),
    default="INFO",
)
def cli(log_file: Optional[str], no_color: bool, log_level: str) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Disable colors if stdout isn't a TTY (piped/redirected)
    tty = sys.stdout.isatty()
    color = (not no_color) and tty
    setup_logging(LoggingConfig(level=level, log_file=log_file, color=color))


cli.add_command(usgs_group, name="usgs")
cli.add_command(commands_cwms.shefcritimport)
cli.add_command(commands_cwms.csv2cwms_cmd)
cli.add_command(commands_cwms.blob_group)
cli.add_command(load.load_group)


def main() -> None:
    """
    Entrypoint wrapper so we can print friendly guidance without a traceback
    for known TLS/cert issues.
    """
    debug = os.getenv("CWMS_CLI_DEBUG", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    try:
        cli(standalone_mode=False)
    except SystemExit:
        raise
    except Exception as e:
        if is_cert_verify_error(e) and not debug:
            # Keep this short, no stack trace.
            logging.error(
                "SSL certificate verification failed while connecting to the server."
            )
            click.echo(ssl_help_text(), err=True)
            raise SystemExit(2)

        # If debug is enabled (or it's not a cert verify error), keep the normal failure behavior.
        raise


if __name__ == "__main__":
    main()
