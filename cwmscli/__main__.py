import logging
import os
import sys
from typing import Optional

import click
from click.core import ParameterSource

from cwmscli.commands import commands_cwms
from cwmscli.load import __main__ as load
from cwmscli.usgs import usgs_group
from cwmscli.utils.click_help import add_version_to_help_tree
from cwmscli.utils.friendly_errors import to_user_facing_error
from cwmscli.utils.logging import (
    LoggingConfig,
    apply_logging_policies,
    current_environment,
    setup_logging,
)
from cwmscli.utils.ssl_errors import is_cert_verify_error, ssl_help_text
from cwmscli.utils.version_cli import show_version_and_exit


@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
@click.option(
    "--version",
    "-V",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=show_version_and_exit,
    help="Show the cwms-cli version and exit.",
)
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
@click.option(
    "-q",
    "--quiet",
    is_flag=True,
    default=False,
    help="Suppress routine output; warnings and errors still print.",
)
@click.pass_context
def cli(
    ctx: click.Context,
    log_file: Optional[str],
    no_color: bool,
    log_level: str,
    quiet: bool,
) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    level = apply_logging_policies(
        level,
        quiet=quiet,
        environment=current_environment(),
        explicit_log_level=ctx.get_parameter_source("log_level")
        == ParameterSource.COMMANDLINE,
    )

    # Disable colors if stdout isn't a TTY (piped/redirected)
    tty = sys.stdout.isatty()
    color = (not no_color) and tty
    setup_logging(LoggingConfig(level=level, log_file=log_file, color=color))


cli.add_command(usgs_group, name="usgs")
cli.add_command(commands_cwms.shefcritimport)
cli.add_command(commands_cwms.csv2cwms_cmd)
cli.add_command(commands_cwms.login_cmd)
cli.add_command(commands_cwms.update_cli_cmd)
cli.add_command(commands_cwms.blob_group)
cli.add_command(commands_cwms.users_group)
cli.add_command(load.load_group)
add_version_to_help_tree(cli)


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
        if len(sys.argv) == 1:
            cli.main(args=["--help"], prog_name="cwms-cli", standalone_mode=False)
            raise SystemExit(0)
        cli(standalone_mode=False)
    except SystemExit:
        raise
    except click.ClickException as e:
        e.show()
        raise SystemExit(e.exit_code)
    except Exception as e:
        if is_cert_verify_error(e) and not debug:
            # Keep this short, no stack trace.
            logging.error(
                "SSL certificate verification failed while connecting to the server."
            )
            click.echo(ssl_help_text(), err=True)
            raise SystemExit(2)

        if not debug:
            friendly_error = to_user_facing_error(e)
            if friendly_error is not None:
                logging.debug("Suppressed traceback for CLI exception", exc_info=e)
                friendly_error.show()
                raise SystemExit(friendly_error.exit_code)

        # If debug is enabled (or it's not a cert verify error), keep the normal failure behavior.
        raise


if __name__ == "__main__":
    main()
