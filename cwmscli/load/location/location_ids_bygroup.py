# cwmscli/load/location_group.py
import re
from typing import Optional
import cwms
import click


def exact_or_regex(ids: list[str]) -> str:
    if not ids:
        return r"^$"
    if len(ids) == 1:
        return rf"^{re.escape(ids[0])}$"
    return r"^(?:" + "|".join(re.escape(x) for x in ids) + r")$"


def copy_from_group(
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

    group_office_id = group_office_id or source_office
    category_office_id = category_office_id or source_office

    if verbose:
        click.echo(
            f"[load location group] source={source_cda} ({source_office}) -> target={target_cda})"
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
            member_ids[i: i + BATCH] for i in range(0, len(member_ids), BATCH)
        ):
            pattern = exact_or_regex(batch)
            resp = cwms.get_locations(
                office_id=source_office, location_ids=pattern)
            if verbose and getattr(resp, "df", None) is not None:
                click.echo(
                    f"Fetched {len(resp.df)} matching Locations in batch")
            if resp and resp.json:
                locations.extend(resp.json)

    except Exception as e:
        raise click.ClickException(
            f"Failed to fetch locations from source: {e}")

    if verbose:
        click.echo(f"Fetched {len(locations)} Location objects from source")

    if dry_run:
        for loc in locations:
            click.echo(
                f"[dry-run] would store Location(name={loc.name}) to {target_cda} ({source_office})"
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
