import logging
import math
import re
from typing import Iterable, Optional

import click
import cwms
import pandas as pd

from cwmscli.utils import init_cwms_session
from cwmscli.utils.links import CDA_REGEXP_GUIDE_URL

logger = logging.getLogger(__name__)


def load_locations(
    source_cda: Optional[str],
    source_office: Optional[str],
    target_cda: Optional[str],
    target_api_key: Optional[str],
    verbose: int,
    dry_run: bool,
    like: Optional[str],
    location_kind_like: Optional[Iterable[str]] = "ALL",
    source_csv: Optional[str] = None,
    target_csv: Optional[str] = None,
):
    src_label = source_csv or source_cda or "-"
    tgt_label = target_csv or target_cda or "-"

    if verbose:
        logger.info(
            f"[load locations] source={src_label} ({source_office or '-'}) -> target={tgt_label}"
        )
        logger.info(
            f"  like={like or '-'}  kinds={list(location_kind_like) or '-'}  dry_run={dry_run}"
        )
        if like or (
            location_kind_like
            and list(location_kind_like) != ["ALL"]
            and list(location_kind_like) != []
        ):
            logger.info("  CDA regex guide: %s", CDA_REGEXP_GUIDE_URL)

    if source_csv:
        df = pd.read_csv(source_csv)
        locations = df.to_dict(orient="records")
    else:
        init_cwms_session(cwms, api_root=source_cda)
        locations = _fetch_locations_from_cda(
            source_office=source_office,
            like=like,
            location_kind_like=location_kind_like,
            verbose=verbose,
        )

    if verbose:
        logger.info("Got %s locations from source", len(locations))

    if dry_run:
        for loc in locations:
            logger.info(
                f"[dry-run] would store Location(name={loc['name']}) to {tgt_label} "
                f"({source_office or loc.get('office-id') or '-'})"
            )
        return

    if target_csv:
        pd.DataFrame(locations).to_csv(target_csv, index=False)
        click.echo(f"Wrote {len(locations)} locations to {target_csv}")
        return

    init_cwms_session(cwms, api_root=target_cda, api_key=target_api_key)

    errors = 0
    for loc in locations:
        loc = _clean_row(loc)
        try:
            if loc.get("active") is True:
                result = cwms.store_location(data=loc, fail_if_exists=False)
                if verbose:
                    logger.info("%s", result)
        except Exception as e:
            errors += 1
            click.echo(f"Error storing location {loc}: \n\t{e}", err=True)

    if errors:
        raise click.ClickException(f"Completed with {errors} error(s).")

    click.echo("Done.")


def _fetch_locations_from_cda(
    source_office: str,
    like: Optional[str],
    location_kind_like: Optional[Iterable[str]],
    verbose: int,
) -> list:
    cat_kwargs = {"office_id": source_office}
    if like:
        cat_kwargs["like"] = like
    kinds = list(location_kind_like) if location_kind_like else ["ALL"]
    if "ALL" in kinds:
        kinds = ["ALL"]

    if kinds == ["ALL"] and not like:
        return cwms.get_locations(office_id=source_office).json

    locations = []
    seen_location_ids = set()
    for kind in kinds:
        cat_kwargs_k = dict(cat_kwargs)
        if kind != "ALL":
            cat_kwargs_k["location_kind_like"] = kind

        if verbose >= 2:
            logger.debug("  > catalog query: %s", cat_kwargs_k)

        resp = cwms.get_locations_catalog(**cat_kwargs_k)
        if resp.df.empty:
            continue

        for location_id in resp.df["name"].tolist():
            if location_id in seen_location_ids:
                continue
            seen_location_ids.add(location_id)
            if verbose >= 2:
                logger.debug("  > location fetch: %s", location_id)
            detail_resp = cwms.get_locations(
                office_id=source_office,
                location_ids=rf"^{re.escape(location_id)}$",
            )
            if detail_resp and detail_resp.json:
                locations.extend(detail_resp.json)
    return locations


def _clean_row(loc: dict) -> dict:
    cleaned = {}
    for k, v in loc.items():
        if isinstance(v, float) and math.isnan(v):
            cleaned[k] = None
        elif isinstance(v, str) and v in ("True", "False"):
            cleaned[k] = v == "True"
        else:
            cleaned[k] = v
    return cleaned
