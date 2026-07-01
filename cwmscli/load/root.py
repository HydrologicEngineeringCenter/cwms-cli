from __future__ import annotations

import functools
import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import click

from cwmscli import requirements as reqs
from cwmscli.utils.deps import requires
from cwmscli.utils.env_store import load_env

logger = logging.getLogger(__name__)

CONTEXT = dict(
    help_option_names=["-h", "--help"],
    max_content_width=160,
)


@dataclass
class CdaEndpoints:
    source_cda: str
    source_office: str
    target_cda: str
    target_office: str
    target_api_key: Optional[str] = None


def _normalize_url(u: str) -> str:
    if not u:
        return ""
    p = urlparse(u)
    path = (p.path or "").rstrip("/")
    return f"{p.scheme.lower()}://{p.netloc.lower()}{path}"


def _norm_office(o: Optional[str]) -> str:
    return (o or "").strip().upper()


def validate_cda_targets(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        source_env = kwargs.pop("source_env", None)
        target_env = kwargs.pop("target_env", None)

        if source_env is not None:
            if _param_was_explicit("source_cda"):
                raise click.ClickException(
                    "--source-env and --source-cda are mutually exclusive."
                )
            env_data = load_env(source_env)
            if env_data is None:
                raise click.ClickException(
                    f"Environment '{source_env}' not found. "
                    "Run 'cwms-cli env show' to list available environments."
                )
            if "CDA_API_ROOT" not in env_data:
                raise click.ClickException(
                    f"Environment '{source_env}' has no CDA_API_ROOT configured. "
                    f"Run 'cwms-cli env setup {source_env} --api-root <url>' to fix."
                )
            kwargs["source_cda"] = env_data["CDA_API_ROOT"]
            if not _param_was_explicit("source_office") and env_data.get("OFFICE"):
                kwargs["source_office"] = env_data["OFFICE"]

        if target_env is not None:
            if _param_was_explicit("target_cda"):
                raise click.ClickException(
                    "--target-env and --target-cda are mutually exclusive."
                )
            env_data = load_env(target_env)
            if env_data is None:
                raise click.ClickException(
                    f"Environment '{target_env}' not found. "
                    "Run 'cwms-cli env show' to list available environments."
                )
            if "CDA_API_ROOT" not in env_data:
                raise click.ClickException(
                    f"Environment '{target_env}' has no CDA_API_ROOT configured. "
                    f"Run 'cwms-cli env setup {target_env} --api-root <url>' to fix."
                )
            kwargs["target_cda"] = env_data["CDA_API_ROOT"]
            if not _param_was_explicit("target_api_key") and env_data.get(
                "CDA_API_KEY"
            ):
                kwargs["target_api_key"] = env_data["CDA_API_KEY"]

        source_csv = kwargs.get("source_csv")
        target_csv = kwargs.get("target_csv")

        if source_csv and target_csv:
            raise click.ClickException(
                "--source-csv and --target-csv are both set, but no CDA is involved. "
                "Use a plain file copy instead."
            )

        if source_csv:
            if kwargs.get("source_cda") and (
                _param_was_explicit("source_cda") or source_env is not None
            ):
                raise click.ClickException(
                    "--source-csv and --source-cda/--source-env are mutually exclusive."
                )
            kwargs["source_cda"] = None

        if target_csv:
            if kwargs.get("target_cda") and (
                _param_was_explicit("target_cda") or target_env is not None
            ):
                raise click.ClickException(
                    "--target-csv and --target-cda/--target-env are mutually exclusive."
                )
            kwargs["target_cda"] = None

        source_cda = _normalize_url(kwargs.get("source_cda"))
        target_cda = _normalize_url(kwargs.get("target_cda"))
        source_office = _norm_office(kwargs.get("source_office"))
        target_office = _norm_office(kwargs.get("target_office"))

        if source_cda and not source_office:
            raise click.ClickException(
                "--source-office is required when reading from a source CDA."
            )

        same_root = source_cda == target_cda and bool(source_cda)
        same_office = source_office == target_office and bool(source_office)

        if same_root and same_office:
            raise click.ClickException(
                "Circular reference detected: source and target CDA endpoints "
                "are identical (URL + office). This would read-from and write-to "
                "the same system.\n\nChange the source or target CDA URL or office. "
                "Type cwms-cli load --help for arg options."
            )
        elif same_root and not same_office:
            logger.warning(
                "Warning: source and target use the same CDA root URL but different offices. "
                "This is allowed, but double-check intent.",
            )

        src_label = source_csv or source_cda or "-"
        tgt_label = target_csv or target_cda or "-"
        logger.info(
            f"Source: {src_label} (office={source_office or '-'})\n"
            f"Target: {tgt_label} (office={target_office or source_office or '-'})",
        )
        return func(*args, **kwargs)

    return wrapper


def _param_was_explicit(name: str) -> bool:
    ctx = click.get_current_context(silent=True)
    if ctx is None:
        return False
    src = ctx.get_parameter_source(name)
    return src is not None and src.name != "DEFAULT"


def shared_source_target_options(f):
    f = click.option(
        "--source-cda",
        envvar="CDA_SOURCE_URL",
        default="https://cwms-data.usace.army.mil/cwms-data/",
        help="Source CWMS Data API root. Default: https://cwms-data.usace.army.mil/cwms-data/",
    )(f)
    f = click.option(
        "--source-office",
        envvar="CDA_SOURCE_OFFICE",
        help="Source office ID (e.g. SWT, SWL). Required when reading from a CDA.",
    )(f)
    f = click.option(
        "--target-cda",
        envvar="CDA_TARGET_URL",
        default="http://localhost:8081/cwms-data/",
        help="Target CWMS Data API root. Default: http://localhost:8081/cwms-data/",
    )(f)
    f = click.option(
        "--target-api-key",
        envvar="CDA_API_KEY",
        help="Target API key used when no saved cwms-cli login token is available.",
    )(f)
    f = click.option(
        "--source-env",
        default=None,
        help=(
            "Named CDA environment for the source "
            "(resolves api-root and office from ~/.config/cwms-cli/envs/). "
            "Mutually exclusive with --source-cda."
        ),
    )(f)
    f = click.option(
        "--target-env",
        default=None,
        help=(
            "Named CDA environment for the target "
            "(resolves api-root and api-key from ~/.config/cwms-cli/envs/). "
            "Mutually exclusive with --target-cda."
        ),
    )(f)
    f = click.option(
        "--dry-run/--no-dry-run",
        is_flag=True,
        default=False,
        show_default=True,
        help="Show what would be written without storing to target.",
    )(f)
    f = click.option(
        "-v",
        "--verbose",
        count=True,
        help="Increase verbosity (repeat for more detail).",
    )(f)
    return f


def csv_source_target_options(*, allow_source_csv: bool, allow_target_csv: bool):
    """Add --source-csv and/or --target-csv to a command, depending on flags."""

    def decorator(f):
        if allow_target_csv:
            f = click.option(
                "--target-csv",
                "target_csv",
                type=click.Path(dir_okay=False, writable=True),
                default=None,
                help=(
                    "Write fetched locations to this CSV file instead of POSTing "
                    "to a target CDA. Mutually exclusive with --target-cda."
                ),
            )(f)
        if allow_source_csv:
            f = click.option(
                "--source-csv",
                "source_csv",
                type=click.Path(exists=True, dir_okay=False, readable=True),
                default=None,
                help=(
                    "Read locations from this CSV file instead of fetching from "
                    "a source CDA. Mutually exclusive with --source-cda."
                ),
            )(f)
        return f

    return decorator


@click.group(
    name="load",
    help="Load data from one CWMS Data API instance to another.",
    context_settings=CONTEXT,
)
def load_group():
    pass
