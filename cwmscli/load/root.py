from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import click

from cwmscli import requirements as reqs
from cwmscli.utils.deps import requires

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
        source_cda = _normalize_url(kwargs.get("source_cda"))
        target_cda = _normalize_url(kwargs.get("target_cda"))
        source_office = _norm_office(kwargs.get("source_office"))
        target_office = _norm_office(kwargs.get("target_office"))

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
            click.secho(
                "Warning: source and target use the same CDA root URL but different offices. "
                "This is allowed, but double-check intent.",
                fg="yellow",
            )

        click.secho(
            f"Source: {source_cda} (office={source_office or '-'})\n"
            f"Target: {target_cda} (office={source_office or '-'})",
            fg="green" if not same_root else "yellow",
        )
        return func(*args, **kwargs)

    return wrapper


def shared_source_target_options(f):
    f = click.option(
        "--source-cda",
        envvar="CDA_SOURCE_URL",
        required=True,
        default="https://cwms-data.usace.army.mil/cwms-data/",
        help="Source CWMS Data API root. Default: https://cwms-data.usace.army.mil/cwms-data/",
    )(f)
    f = click.option(
        "--source-office",
        envvar="CDA_SOURCE_OFFICE",
        required=True,
        help="Source office ID (e.g. SWT, SWL).",
    )(f)
    f = click.option(
        "--target-cda",
        envvar="CDA_TARGET_URL",
        required=True,
        default="http://localhost:8081/cwms-data/",
        help="Target CWMS Data API root. Default: http://localhost:8081/cwms-data/",
    )(f)
    f = click.option(
        "--target-api-key",
        envvar="CDA_API_KEY",
        help="Target API key (if required by the target CDA).",
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


@click.group(
    name="load",
    help="Load data from one CWMS Data API instance to another.",
    context_settings=CONTEXT,
)
def load_group():
    pass
