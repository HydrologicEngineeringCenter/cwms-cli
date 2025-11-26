# cwmscli/load/locations.py
import os
from typing import Iterable, Optional

import click

from cwmscli import requirements as reqs
from cwmscli.utils.deps import requires

from .root import load_group, shared_source_target_options, validate_cda_targets


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
    import cwms

    if verbose:
        click.echo(
            f"[load locations] source={source_cda} ({source_office}) -> target={target_cda} ({target_office})"
        )
        click.echo(
            f"  like={like or '-'}  kinds={list(location_kind_like) or '-'}  dry_run={dry_run}"
        )

    cwms.init_session(api_root=source_cda, api_key=None)

    cat_kwargs = {"office_id": source_office}
    if like:
        cat_kwargs["like"] = like
    kinds = list(location_kind_like) if location_kind_like else [None]

    locations = []
    for kind in kinds:
        cat_kwargs_k = dict(cat_kwargs)
        if kind:
            cat_kwargs_k["location_kind_like"] = kind

        if verbose >= 2:
            click.echo(f"  > catalog query: {cat_kwargs_k}")

        resp = cwms.get_locations_catalog(**cat_kwargs_k)
        if resp.df.empty:
            continue

        loc_ids = resp.df["name"].tolist()
        locations_resp = cwms.get_locations(
            office_id=source_office, location_ids=loc_ids
        )
        locations.extend(locations_resp.json or [])

    if verbose:
        click.echo(f"Fetched {len(locations)} locations from source")

    if dry_run:
        for loc in locations:
            click.echo(
                f"[dry-run] would store Location(name={loc.name}) to {target_cda} ({target_office})"
            )
        return

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

    # init target once
    cwms.init_session(api_root=target_cda, api_key=target_api_key)

    errors = 0
    for loc in locations:
        try:
            result = cwms.store_location(data=loc, fail_if_exists=False)
            if verbose:
                click.echo(result)
        except Exception as e:
            errors += 1
            click.echo(f"Error storing location {loc}: \n\t{e}", err=True)

    if errors:
        raise click.ClickException(f"Completed with {errors} error(s).")
    if verbose:
        click.echo("Done.")
