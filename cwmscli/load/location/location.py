# cwmscli/load/locations.py
from typing import Iterable, Optional

import click

from cwmscli import requirements as reqs
from cwmscli.load.root import (
    load_group,
    shared_source_target_options,
    validate_cda_targets,
)
from cwmscli.utils.deps import requires


@load_group.group(
    "location", help="Copy location data from a source CDA to a target CDA."
)
@click.pass_context
def location(ctx):
    pass


@location.command(
    "ids-all",
    help="Copy ALL locations from a source CDA to a target CDA.",
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
    default=["ALL"],
    multiple=True,
    help=(
        "Filter by LOCATION_KIND using LIKE; may be passed multiple times.\n\n"
        "Default is to pull all Location kinds.\n\n"
        "Common kinds: SITE, EMBANKMENT, OVERFLOW, TURBINE, STREAM, PROJECT, "
        "STREAMGAGE, BASIN, OUTLET, LOCK, GATE.\n\n"
        "Examples:\n"
        "  --location-kind-like PROJECT --location-kind-like STREAM\n"
        "  --location-kind-like '(SITE|STREAM)'   # Posix regex"
    ),
)
@requires(reqs.cwms)
@validate_cda_targets
def load_locations(
    source_cda: str,
    source_office: str,
    target_cda: str,
    target_api_key: Optional[str],
    verbose: int,
    dry_run: bool,
    like: Optional[str],
    location_kind_like: Optional[Iterable[str]] = None,
):
    from cwmscli.load.location.location_ids import load_locations as _load_locations

    _load_locations(
        source_cda=source_cda,
        source_office=source_office,
        target_cda=target_cda,
        target_api_key=target_api_key,
        verbose=verbose,
        dry_run=dry_run,
        like=like,
        location_kind_like=location_kind_like,
    )


@location.command(
    "ids-bygroup",
    help="Copy locations from a CWMS Location Group (source CDA) to a target CDA.",
)
@shared_source_target_options
@click.option(
    "--group-id", required=True, help="Location Group ID (e.g., 'Ark Basin')."
)
@click.option(
    "--category-id", required=True, help="Location Category ID (e.g., 'Basin')."
)
@click.option(
    "--group-office-id",
    default=None,
    help="Owning office of the Location Group (defaults to --source-office).",
)
@click.option(
    "--category-office-id",
    default=None,
    help="Owning office of the Category (defaults to --source-office).",
)
@click.option(
    "--filter-office/--no-filter-office",
    default=True,
    show_default=True,
    help="If set, only copy members whose 'office-id' equals --source-office.",
)
@requires(reqs.cwms)
@validate_cda_targets
def load_locations_from_group(
    source_cda: str,
    source_office: str,
    target_cda: str,
    target_api_key: Optional[str],
    verbose: int,
    group_id: str,
    category_id: str,
    group_office_id: Optional[str],
    category_office_id: Optional[str],
    filter_office: bool,
    dry_run: bool,
):
    from cwmscli.load.location.location_ids_bygroup import copy_from_group

    copy_from_group(
        source_cda=source_cda,
        source_office=source_office,
        target_cda=target_cda,
        target_api_key=target_api_key,
        verbose=verbose,
        group_id=group_id,
        category_id=category_id,
        group_office_id=group_office_id,
        category_office_id=category_office_id,
        filter_office=filter_office,
        dry_run=dry_run,
    )
