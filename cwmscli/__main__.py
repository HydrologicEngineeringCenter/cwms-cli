from __future__ import annotations

import logging
import os
import sys

import click

from cwmscli.commands import commands_cwms
from cwmscli.load import __main__ as load
from cwmscli.usgs import usgs_group
from cwmscli.utils.ssl_errors import is_cert_verify_error, ssl_help_text


@click.group()
def cli():
    pass


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
