import logging as py_logging
from typing import Optional

import click

from cwmscli.utils import colors
from cwmscli.utils.click_help import DOCS_BASE_URL
from cwmscli.utils.logging import apply_quiet_log_level


def to_uppercase(ctx, param, value):
    if value is None:
        return None
    return value.upper()


def _set_log_level(ctx, param, value):
    if value is None:
        return
    level = getattr(py_logging, value.upper(), None)
    if level is None:
        raise click.BadParameter(f"Invalid log level: {value}")
    quiet = bool(ctx.find_root().params.get("quiet", False))
    level = apply_quiet_log_level(level, quiet=quiet)
    py_logging.getLogger().setLevel(level)
    return value


office_option = click.option(
    "-o",
    "--office",
    required=True,
    envvar="OFFICE",
    type=str,
    callback=to_uppercase,
    help="Office to grab data for",
)
api_root_option = click.option(
    "-a",
    "--api-root",
    required=True,
    envvar="CDA_API_ROOT",
    type=str,
    help="Api Root for CDA. Can be user defined or placed in a env variable CDA_API_ROOT",
)
api_coop_root_option = click.option(
    "--coop",
    is_flag=True,
    envvar="CDA_API_COOP_ROOT",
    type=str,
    help="Use CDA_API_COOP_ROOT from env",
)

api_key_option = click.option(
    "-k",
    "--api-key",
    default=None,
    type=str,
    envvar="CDA_API_KEY",
    help="api key for CDA. Can be user defined or place in env variable CDA_API_KEY. one of api-key or api-key-loc are required",
)
api_key_loc_option = click.option(
    "-kl",
    "--api-key-loc",
    default=None,
    type=str,
    help="file storing Api Key. One of api-key or api-key-loc are required",
)
log_level_option = click.option(
    "--log-level",
    type=click.Choice(
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False
    ),
    default="INFO",
    envvar="LOG_LEVEL",
    callback=_set_log_level,
    expose_value=False,  # Callback will set the log level of all methods
    is_eager=True,  # Run before other commands (to cover any logging statements)
    help="Set logging verbosity (overrides default INFO).",
)


def get_api_key(api_key: str, api_key_loc: str) -> str:
    if api_key is not None:
        return api_key
    elif api_key_loc is not None:
        with open(api_key_loc, "r") as f:
            return f.readline().strip()
    else:
        raise Exception(
            "must add a value to either --api-key(-k) or --api-key-loc(-kl)"
        )


def log_scoped_read_hint(
    *,
    api_key: Optional[str],
    anonymous: bool,
    office: str,
    action: str,
    resource: str = "content",
) -> None:
    if anonymous or not api_key:
        return
    py_logging.warning(
        colors.c(
            f"Access scope hint: a key was sent for this {action} request in office {office}. "
            f"If you need to view {resource} outside that key's access scope, retry with "
            f"--anonymous or remove the configured API key. Docs: {DOCS_BASE_URL}/cli/blob.html#blob-auth-scope",
            "yellow",
            bright=True,
        )
    )


def common_api_options(f):
    f = log_level_option(f)
    f = office_option(f)
    f = api_root_option(f)
    f = api_key_option(f)
    return f
