# cwmscli/load/location_group.py
import os
import re
from typing import Optional

import click

from cwmscli import requirements as reqs
from cwmscli.utils.deps import requires

from .root import (
    CONTEXT,
    load_group,
    shared_source_target_options,
    validate_cda_targets,
)


def exact_or_regex(ids: list[str]) -> str:
    if not ids:
        return r"^$"
    if len(ids) == 1:
        return rf"^{re.escape(ids[0])}$"
    return r"^(?:" + "|".join(re.escape(x) for x in ids) + r")$"


@load_group.group(
    name="location",
    help="Location utilities (copy, group operations)",
    context_settings=CONTEXT,
)
def load_location_group():
    pass


@load_location_group.command(
    "group",
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
@click.option(
    "--dry-run/--no-dry-run",
    is_flag=True,
    default=False,
    show_default=True,
    help="Show what would be written without storing to target.",
)
@requires(reqs.cwms)
@validate_cda_targets
def copy_from_group(
    source_cda: str,
    source_office: str,
    target_cda: str,
    target_office: str,
    target_api_key: Optional[str],
    verbose: int,
    group_id: str,
    category_id: str,
    group_office_id: Optional[str],
    category_office_id: Optional[str],
    filter_office: bool,
    dry_run: bool,
):
    import cwms

    group_office_id = group_office_id or source_office
    category_office_id = category_office_id or source_office

    if verbose:
        click.echo(
            f"[load location group] source={source_cda} ({source_office}) -> target={target_cda} ({target_office})"
        )
        click.echo(
            f"  group={group_id}  category={category_id}  "
            f"group_office={group_office_id}  category_office={category_office_id} "
            f"filter_office={filter_office}  dry_run={dry_run}"
        )

    cwms.init_session(api_root=source_cda, api_key=None)

    try:
        grp = cwms.get_location_group(
            loc_group_id=group_id,
            category_id=category_id,
            office_id=source_office,
            group_office_id=group_office_id,
            category_office_id=category_office_id,
        )
        if verbose:
            click.echo(f"Fetched Location Group '{group_id}' from source:")
            if hasattr(grp, "df"):
                click.echo(grp.df)
            else:
                click.echo(grp.json)
    except Exception as e:
        raise click.ClickException(
            f"Failed to read location group '{group_id}' in category '{category_id}': {e}"
        )

    df = getattr(grp, "df", None)
    if df is None or df.empty:
        click.echo("No members found in the specified location group.")
        return

    if filter_office and "office-id" in df.columns:
        df = df[df["office-id"] == source_office].copy()

    member_ids = sorted(df["location-id"].dropna().unique().tolist())
    if verbose:
        click.echo(f"Group members found: {len(member_ids)}")
    if not member_ids:
        click.echo("No valid location IDs to copy.")
        return

    try:
        locations = []
        BATCH = 200  # optional batching
        for batch in (
            member_ids[i : i + BATCH] for i in range(0, len(member_ids), BATCH)
        ):
            pattern = exact_or_regex(batch)
            resp = cwms.get_locations(office_id=source_office, location_ids=pattern)
            if verbose and getattr(resp, "df", None) is not None:
                click.echo(f"Fetched {len(resp.df)} matching Locations in batch")
            if resp and resp.json:
                locations.extend(resp.json)

    except Exception as e:
        raise click.ClickException(f"Failed to fetch locations from source: {e}")

    if verbose:
        click.echo(f"Fetched {len(locations)} Location objects from source")

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

    try:
        cwms.init_session(api_root=target_cda, api_key=target_api_key)
    except Exception as e:
        raise click.ClickException(f"Failed to init target session: {e}")

    errors = 0
    for loc in locations:
        try:
            if verbose:
                click.echo(f"Store: {loc['name']}")
            cwms.store_location(data=loc, fail_if_exists=False)
            if verbose:
                click.echo("\tStored successfully.")
        except Exception as e:
            errors += 1
            click.echo(f"Error storing location {loc}: \n\t{e}", err=True)

    click.echo(
        f"Successfully stored {len(locations) - errors} / {len(locations)} locations."
    )

    if errors:
        raise click.ClickException(f"Completed with {errors} error(s).")
