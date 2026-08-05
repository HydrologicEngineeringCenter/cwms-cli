from __future__ import annotations

import functools
import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

import click
import requests

from cwmscli import requirements as reqs
from cwmscli.utils.deps import requires

logger = logging.getLogger(__name__)
CDA_PROBE_TIMEOUT_SECONDS = 2.5

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


def _swagger_docs_url(api_root: str) -> str:
    return urljoin(f"{api_root.rstrip('/')}/", "swagger-docs")


def _looks_like_cda_landing_page(response: requests.Response) -> bool:
    # Some local CDA builds serve the UI but not the generated OpenAPI route.
    server = response.headers.get("Server", "").lower()
    if "cwms-data-api" in server:
        return True

    content_type = response.headers.get("Content-Type", "").lower()
    if "html" not in content_type:
        return False
    return "CDA - CWMS Data API" in response.text


def _validate_cda_api_root(api_root: str, *, role: str) -> None:
    parsed = urlparse(api_root)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise click.ClickException(
            f"{role} CDA URL must be an absolute http(s) URL, got {api_root!r}."
        )

    url = _swagger_docs_url(api_root)
    try:
        response = requests.get(
            url,
            headers={"Accept": "application/json"},
            timeout=CDA_PROBE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        document = response.json()
        if isinstance(document, dict) and (
            document.get("openapi") or document.get("swagger")
        ):
            return
    except (requests.RequestException, ValueError) as openapi_error:
        logger.debug(
            "CDA OpenAPI probe for %s at %s did not succeed: %s",
            role,
            url,
            openapi_error,
        )

    try:
        response = requests.get(api_root, timeout=CDA_PROBE_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.Timeout as e:
        raise click.ClickException(
            f"Could not validate {role} CDA at {api_root}: timed out fetching {api_root}."
        ) from e
    except requests.RequestException as e:
        raise click.ClickException(
            f"Could not validate {role} CDA at {api_root}: failed to fetch {api_root}: {e}"
        ) from e

    if not _looks_like_cda_landing_page(response):
        raise click.ClickException(
            f"{role} URL {api_root} did not return a CDA OpenAPI document or CDA landing page."
        )


def validate_cda_targets(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        source_csv = kwargs.get("source_csv")
        target_csv = kwargs.get("target_csv")
        skip_target_cda_check = kwargs.pop("skip_target_cda_check", False)

        if source_csv and target_csv:
            raise click.ClickException(
                "--source-csv and --target-csv are both set, but no CDA is involved. "
                "Use a plain file copy instead."
            )

        if source_csv:
            if kwargs.get("source_cda") and _param_was_explicit("source_cda"):
                raise click.ClickException(
                    "--source-csv and --source-cda are mutually exclusive."
                )
            kwargs["source_cda"] = None

        if target_csv:
            if kwargs.get("target_cda") and _param_was_explicit("target_cda"):
                raise click.ClickException(
                    "--target-csv and --target-cda are mutually exclusive."
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

        # Dry-runs still need a real target; otherwise users can validate a bad load command.
        if target_cda and not skip_target_cda_check:
            _validate_cda_api_root(target_cda, role="Target")

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
        "--skip-target-cda-check",
        envvar="CWMS_CLI_SKIP_TARGET_CDA_CHECK",
        is_flag=True,
        default=False,
        show_default=True,
        help="Skip the preflight check that --target-cda points to a CDA service.",
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
