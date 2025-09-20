from __future__ import annotations

import inspect
import os
from dataclasses import dataclass
from typing import Iterable, Optional

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


def _normalize_keys(d: dict) -> dict:
    """
    - convert kebab-case keys to snake_case
    - drop keys not accepted by hec.location.Location
    """
    from hec.location import Location

    _LOCATION_KW = set(inspect.signature(Location).parameters)
    out = {}
    for k, v in d.items():
        key = k.replace("-", "_")
        if key in _LOCATION_KW:
            out[key] = v
    return out


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
    f = click.option(
        "--store-rule",
        type=click.Choice(
            ["REPLACE_ALL", "CREATE_ONLY", "REPLACE_NEWER", "MERGE"],
            case_sensitive=False,
        ),
        default="REPLACE_ALL",
        show_default=True,
        help="Store rule to use for writes.",
    )(f)
    f = click.option(
        "--override-protection/--no-override-protection",
        default=False,
        show_default=True,
        help="Whether to override protection flags when writing.",
    )(f)
    f = click.option(
        "-v",
        "--verbose",
        count=True,
        help="Increase verbosity (repeat for more detail).",
    )(f)
    return f


@click.group(
    name="load", help="Load data into a target CWMS Data API.", context_settings=CONTEXT
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
    default=False,
    show_default=True,
    help="Show what would be written without storing to target.",
)
@requires(reqs.cwms)
def load_locations(
    source_cda: str,
    source_office: str,
    target_cda: str,
    target_office: str,
    target_api_key: Optional[str],
    store_rule: str,
    override_protection: bool,
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
    from hec.datastore import CwmsDataStore
    from hec.location import Location

    if verbose:
        click.echo(
            f"[load locations] source={source_cda} ({source_office}) -> target={target_cda} ({target_office})"
        )
        click.echo(
            f"  like={like or '-'}  kinds={list(location_kind_like) or '-'}  dry_run={dry_run}"
        )

    cwms.init_session(api_root=source_cda)

    with CwmsDataStore.open(source_cda, office=source_office) as src_db:
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
        locations = [Location(**_normalize_keys(e)) for e in locations]
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
    with CwmsDataStore.open(
        target_cda,
        office=target_office,
        api_key=target_api_key,
        store_rule=store_rule,
        read_only=False,
    ) as tgt_db:
        errors = 0
        for loc in locations:
            try:
                result = tgt_db.store(loc, override_protection=override_protection)
                if verbose:
                    click.echo(result)
            except Exception as e:
                errors += 1
                click.echo(f"Error storing location {loc}: \n\t{e}", err=True)

        if errors:
            raise click.ClickException(f"Completed with {errors} error(s).")
        if verbose:
            click.echo("Done.")
