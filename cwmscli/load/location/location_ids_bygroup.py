# cwmscli/load/location_group.py
import logging
import re
from typing import Optional

import click
import cwms

from cwmscli.utils import init_cwms_session

logger = logging.getLogger(__name__)


def exact_or_regex(ids: list[str]) -> str:
    if not ids:
        return r"^$"
    if len(ids) == 1:
        return rf"^{re.escape(ids[0])}$"
    return r"^(" + "|".join(re.escape(x) for x in ids) + r")$"


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
        logger.info(
            f"[load location group] source={source_cda} ({source_office}) -> target={target_cda})"
        )
        logger.info(
            f"  group={group_id}  category={category_id}  "
            f"group_office={group_office_id}  category_office={category_office_id} "
            f"filter_office={filter_office}  dry_run={dry_run}"
        )

    init_cwms_session(cwms, api_root=source_cda)

    try:
        grp = cwms.get_location_group(
            loc_group_id=group_id,
            category_id=category_id,
            office_id=source_office,
            group_office_id=group_office_id,
            category_office_id=category_office_id,
        )
        if verbose:
            logger.info("Fetched Location Group '%s' from source:", group_id)
            if hasattr(grp, "df"):
                logger.info("%s", grp.df)
            else:
                logger.info("%s", grp.json)
    except Exception as e:
        raise click.ClickException(
            f"Failed to read location group '{group_id}' in category '{category_id}': {e}"
        )

    df = getattr(grp, "df", None)
    if df is None or df.empty:
        logger.info("No members found in the specified location group.")
        return

    if filter_office and "office-id" in df.columns:
        df = df[df["office-id"] == source_office].copy()

    member_ids = sorted(df["location-id"].dropna().unique().tolist())
    if verbose:
        logger.info("Group members found: %s", len(member_ids))
    if not member_ids:
        logger.info("No valid location IDs to copy.")
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
                logger.info("Fetched %s matching Locations in batch", len(resp.df))
            if resp and resp.json:
                locations.extend(resp.json)

    except Exception as e:
        raise click.ClickException(f"Failed to fetch locations from source: {e}")

    if verbose:
        logger.info("Fetched %s Location objects from source", len(locations))

    if dry_run:
        for loc in locations:
            logger.info(
                f"[dry-run] would store Location(name={loc['name']}) to {target_cda} ({source_office})"
            )
        return

    try:
        init_cwms_session(cwms, api_root=target_cda, api_key=target_api_key)
    except Exception as e:
        raise click.ClickException(f"Failed to init target session: {e}")

    errors = 0
    for loc in locations:
        try:
            if verbose:
                logger.info("Store: %s", loc["name"])
            cwms.store_location(data=loc, fail_if_exists=False)
            if verbose:
                logger.info("\tStored successfully.")
        except Exception as e:
            errors += 1
            click.echo(f"Error storing location {loc}: \n\t{e}", err=True)

    logger.info(
        "Successfully stored %s / %s locations.",
        len(locations) - errors,
        len(locations),
    )

    if errors:
        raise click.ClickException(f"Completed with {errors} error(s).")
