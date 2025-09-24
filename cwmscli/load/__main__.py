from __future__ import annotations

import functools
import os
from dataclasses import dataclass
from typing import Iterable, Optional
from urllib.parse import urlparse

import click

from cwmscli import requirements as reqs
from cwmscli.utils.deps import requires

# Expand the help menu for a more verbose help menu
CONTEXT = dict(
    help_option_names=["-h", "--help"],
    max_content_width=160,  # Expand to fit wider terminals
)


@dataclass
class CdaEndpoints:
    source_cda: str
    source_office: str
    target_cda: str
    target_office: str
    target_api_key: Optional[str] = None


# Determine the currently available kwargs for the user's installed hec-python-library
# ! https://github.com/HydrologicEngineeringCenter/hec-python-library/issues/54


def _normalize_url(u: str) -> str:
    if not u:
        return ""
    # Lowercase scheme/host and strip trailing slash
    p = urlparse(u)
    # Normalize to lowercase scheme/url/host and no trailing slash
    path = (p.path or "").rstrip("/")
    base = f"{p.scheme.lower()}://{p.netloc.lower()}{path}"
    return base


def _norm_office(o: Optional[str]) -> str:
    return (o or "").strip().upper()


def validate_cda_targets(func):
    """
    Validates that source and target endpoints (CDA+office) are not identical.
    If the URL roots are the same but offices differ, emit a warning.
    If they are fully identical throw an error
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print("KWARGGSS", kwargs)
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
                "the same system.\n\nChange the source or target CDA URL or office. Type cwms-cli load --help for arg options."
            )
        elif same_root and not same_office:
            click.secho(
                "Warning: source and target use the same CDA root URL but different offices. "
                "This is allowed, but double-check intent.",
                fg="yellow",
            )

        # Log out what the intent will be, in color
        click.secho(
            f"Source: {source_cda} (office={source_office or '-'})\n"
            f"Target: {target_cda} (office={target_office or '-'})",
            fg="green" if not same_root else "yellow",
        )
        return func(*args, **kwargs)

    return wrapper


def shared_source_target_options(f):
    """
    Shared options across all the sub commands. These are required for any given sub command to complete.
    """

    f = click.option(
        "--source-cda",
        envvar="CDA_SOURCE_URL",
        required=True,
        default="https://cwms-data.usace.army.mil/cwms-data",
        help="Source CWMS Data API root. Default: https://cwms-data.usace.army.mil/cwms-data",
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
        default="http://localhost:8081/cwms-data",
        help="Target CWMS Data API root. Default: http://localhost:8081/cwms-data.",
    )(f)
    f = click.option(
        "--target-office",
        envvar="CDA_TARGET_OFFICE",
        required=True,
        help="Target office ID for writes.",
    )(f)
    f = click.option(
        "--target-api-key",
        envvar="CDA_API_KEY",
        help="Target API key (if required by the target CDA).",
    )(f)
    # f = click.option(
    #     "--store-rule",
    #     type=click.Choice(
    #         ["REPLACE_ALL", "CREATE_ONLY", "REPLACE_NEWER", "MERGE"],
    #         case_sensitive=False,
    #     ),
    #     default="REPLACE_ALL",
    #     show_default=True,
    #     help="Store rule to use for writes.",
    # )(f)
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


@load_group.command(
    "locations", help="Copy locations from a source CDA to a target CDA."
)
@shared_source_target_options
@click.option(
    "--like",
    default=None,
    type=str,
    help="LIKE filter for location name (e.g. 'Turbine*').",
)
@click.option(
    "--location-kind-like",
    "location_kind_like",
    # Don't load everything by default
    default=["PROJECT"],
    multiple=True,
    help=(
        "Filter by LOCATION_KIND using LIKE; may be passed multiple times.\n\n"
        "Common kinds: SITE, EMBANKMENT, OVERFLOW, TURBINE, STREAM, PROJECT, "
        "STREAMGAGE, BASIN, OUTLET, LOCK, GATE.\n\n"
        "Examples:\n"
        "  --location-kind-like PROJECT --location-kind-like STREAM\n"
        "  --location-kind-like '(SITE|STREAM)'   # Posix regex"
    ),
)
@click.option(
    "--dry-run/--no-dry-run",
    is_flag=True,
    default=False,
    show_default=True,
    help="Show what would be written without storing to target.",
)
@requires(reqs.cwms)
@validate_cda_targets
def load_locations(
    source_cda: str,
    source_office: str,
    target_cda: str,
    target_office: str,
    target_api_key: Optional[str],
    verbose: int,
    like: Optional[str],
    location_kind_like: Iterable[str],
    dry_run: bool,
):
    """
    Copy locations from a source CDA to a target CDA.

    \b
    Filters:
      • --like "FGIB*"
      • --location-kind-like PROJECT|STREAM|...

    \b
    Examples:
      # Copy Fort Gibson locations from prod -> local
      cwms-cli load locations \
        --source-cda https://cwms-data.usace.army.mil/cwms-data \
        --source-office SWT \
        --target-cda http://localhost:8081/cwms-data \
        --target-office SWT \
        --like "FGIB*"

      # Multiple kinds (OR'd)
      cwms-cli load locations \
        --source-cda ... --source-office SWT \
        --target-cda ... --target-office SWT \
        --location-kind-like PROJECT \
        --location-kind-like STREAM \
        --dry-run -vv
    """

    import cwms

    if verbose:
        click.echo(
            f"[load locations] source={source_cda} ({source_office}) -> target={target_cda} ({target_office})"
        )
        click.echo(
            f"  like={like or '-'}  kinds={list(location_kind_like) or '-'}  dry_run={dry_run}"
        )

    cwms.init_session(api_root=source_cda)

    cat_kwargs = {"office_id": source_office}
    if like:
        cat_kwargs["like"] = like
    if location_kind_like:
        kinds = list(location_kind_like)
    else:
        kinds = [None]

    locations = []
    for kind in kinds:
        if kind:
            cat_kwargs_k = dict(cat_kwargs)
            cat_kwargs_k["location_kind_like"] = kind
        else:
            cat_kwargs_k = cat_kwargs

        if verbose >= 2:
            click.echo(f"  > catalog query: {cat_kwargs_k}")

        resp = cwms.get_locations_catalog(**cat_kwargs_k)
        batch = resp.json.get("entries", []) if hasattr(resp, "json") else []
        locations.extend(batch)

        # Convert CDA Response to expected Location objects
        if verbose:
            click.echo(f"Fetched {len(locations)} locations from source")
    if dry_run:
        for loc in locations:
            click.echo(
                f"[dry-run] would store Location(name={loc.name}) to {target_cda} ({target_office})"
            )
        return

    # If no target_api_key is provided prompt if the user would like to use their env api key for the target cda
    if not target_api_key and os.getenv("CDA_API_KEY"):
        if click.confirm(
            "No target API key provided. Use CDA_API_KEY environment variable for target?",
            default=True,
        ):
            target_api_key = os.getenv("CDA_API_KEY")
        else:
            click.echo(
                "No target API key provided; Cannot write to target API without key. Exiting."
            )
            return
    errors = 0
    for loc in locations:
        try:
            result = cwms.store_location(data=loc)
            if verbose:
                click.echo(result)
        except Exception as e:
            errors += 1
            click.echo(f"Error storing location {loc}: \n\t{e}", err=True)

    if errors:
        raise click.ClickException(f"Completed with {errors} error(s).")
    if verbose:
        click.echo("Done.")
