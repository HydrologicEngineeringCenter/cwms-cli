import logging as py_logging
import time
from pathlib import Path
from typing import Optional, Union

import click
from click.core import ParameterSource

from cwmscli.utils import colors
from cwmscli.utils.click_help import DOCS_BASE_URL
from cwmscli.utils.logging import apply_logging_policies, current_environment


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
    level = apply_logging_policies(
        level,
        quiet=quiet,
        environment=current_environment(),
        explicit_log_level=ctx.get_parameter_source(param.name)
        == ParameterSource.COMMANDLINE,
    )
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
office_option_notrequired = click.option(
    "-o",
    "--office",
    default=None,
    required=False,
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
    help="API key for CDA. Optional when a saved cwms-cli login token is available. Can also be provided by CDA_API_KEY.",
)
api_key_loc_option = click.option(
    "-kl",
    "--api-key-loc",
    default=None,
    type=str,
    help="File storing an API key. Optional when a saved cwms-cli login token is available.",
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
    # Run before other commands (to cover any logging statements)
    is_eager=True,
    help="Set logging verbosity (overrides default INFO).",
)


def get_api_key(api_key: str, api_key_loc: str) -> str:
    if api_key_loc is not None:
        with open(api_key_loc, "r") as f:
            return f.readline().strip()
    elif api_key is not None:
        return api_key
    else:
        raise Exception(
            "must add a value to either --api-key(-k) or --api-key-loc(-kl)"
        )


def get_saved_login_token(
    token_file: Optional[Union[str, Path]] = None,
    provider: str = "federation-eams",
) -> Optional[str]:
    from cwmscli.utils.auth import AuthError, default_token_file, load_saved_login

    candidate = Path(token_file) if token_file else default_token_file(provider)
    try:
        saved = load_saved_login(candidate)
    except AuthError as error:
        if candidate.exists():
            py_logging.warning("Ignoring saved login at %s: %s", candidate, error)
        return None

    token = saved.get("token", {})
    access_token = token.get("access_token")
    if not access_token:
        py_logging.warning(
            "Ignoring saved login at %s: no access token found", candidate
        )
        return None
    expires_at = token.get("expires_at")
    if expires_at is not None:
        try:
            if float(expires_at) <= time.time():
                py_logging.info(
                    "Ignoring expired saved login token at %s; falling back to API key if available",
                    candidate,
                )
                return None
        except (TypeError, ValueError, OSError):
            py_logging.warning(
                "Ignoring saved login at %s: invalid token expiration value %r",
                candidate,
                expires_at,
            )
            return None
    return access_token


def init_cwms_session(
    cwms_module,
    *,
    api_root: str,
    api_key: Optional[str] = None,
    api_key_loc: Optional[str] = None,
    anonymous: bool = False,
    token_file: Optional[Union[str, Path]] = None,
    provider: str = "federation-eams",
):
    init_fn = getattr(cwms_module, "init_session", None)
    if init_fn is None:
        init_fn = cwms_module.api.init_session

    if anonymous:
        return init_fn(api_root=api_root, api_key=None)

    token = get_saved_login_token(token_file=token_file, provider=provider)
    if token:
        return init_fn(api_root=api_root, token=token)

    resolved_api_key = None
    if api_key_loc is not None or api_key is not None:
        resolved_api_key = get_api_key(api_key, api_key_loc)

    return init_fn(api_root=api_root, api_key=resolved_api_key)


def log_scoped_read_hint(
    *,
    credential_kind: Optional[str],
    anonymous: bool,
    office: str,
    action: str,
    resource: str = "content",
) -> None:
    if anonymous or not credential_kind:
        return
    credential_text = (
        "a saved login token was sent"
        if credential_kind == "token"
        else "an API key was sent"
    )
    py_logging.warning(
        colors.c(
            f"Access scope hint: {credential_text} for this {action} request in office {office}. "
            f"If you need to view {resource} outside that credential's access scope, retry with "
            f"--anonymous or remove the configured credential. Docs: {DOCS_BASE_URL}/cli/blob.html#blob-auth-scope",
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
