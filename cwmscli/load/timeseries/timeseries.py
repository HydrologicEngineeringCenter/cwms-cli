from datetime import datetime, timedelta
from typing import Optional

import click

from cwmscli import requirements as reqs
from cwmscli.load.root import (
    load_group,
    shared_source_target_options,
    validate_cda_targets,
)
from cwmscli.utils.deps import requires
from cwmscli.utils.links import CDA_REGEXP_GUIDE_URL


@load_group.group(
    "timeseries", help="Copy timeseries IDs from a source CDA to a target CDA."
)
@click.pass_context
def timeseries(ctx):
    pass


@timeseries.command(
    "ids-all",
    help=(
        "Copy ALL timeseries IDs for locations in a target CDA from a source CDA. "
        f"Regex guide for --timeseries-id-regex: {CDA_REGEXP_GUIDE_URL}"
    ),
)
@shared_source_target_options
@click.option(
    "--timeseries-id-regex",
    "timeseries_id_regex",
    default=None,
    type=str,
    help="Regex filter for timeseries ID (e.g. '^LocID.*').",
)
@requires(reqs.cwms)
@validate_cda_targets
def load_timeseries_ids_all(
    source_cda: str,
    source_office: str,
    target_cda: str,
    target_api_key: Optional[str],
    verbose: int,
    timeseries_id_regex: Optional[str],
    dry_run: bool,
):
    from cwmscli.load.timeseries.timeseries_ids import load_timeseries_ids

    load_timeseries_ids(
        source_cda=source_cda,
        source_office=source_office,
        target_cda=target_cda,
        target_api_key=target_api_key,
        verbose=verbose,
        timeseries_id_regex=timeseries_id_regex,
        dry_run=dry_run,
    )


@timeseries.command(
    "data",
    help="Copy timeseries data (by timeseries ID or timeseries group) into a target CDA from a source CDA.",
)
@shared_source_target_options
@click.option(
    "--ts-id",
    "ts_id",
    default=None,
    type=str,
    help="Timeseries ID to copy, or a comma-delimited list of IDs.",
)
@click.option(
    "--ts-group",
    "ts_group",
    default=None,
    type=str,
    help="ID of the timeseries group to copy (e.g. 'GroupID.*').",
)
@click.option(
    "--ts-group-category-id",
    "ts_group_category_id",
    default=None,
    type=str,
    help="Optional category filter when matching timeseries groups.",
)
@click.option(
    "--ts-group-category-office-id",
    "ts_group_category_office_id",
    default=None,
    type=str,
    help="Optional category office filter when matching timeseries groups.",
)
@click.option(
    "--begin",
    "begin",
    default=(datetime.now().astimezone() - timedelta(days=1)).replace(microsecond=0),
    type=click.DateTime(formats=["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S %Z"]),
    help="Start date for timeseries data (e.g. '2022-01-01T00:00:00-06:00').",
)
@click.option(
    "--end",
    "end",
    default=datetime.now().astimezone().replace(microsecond=0),
    type=click.DateTime(formats=["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S %Z"]),
    help="End date for timeseries data (e.g. '2022-01-31T00:00:00-0600').",
)
@requires(reqs.cwms)
@validate_cda_targets
def load_timeseries_data(
    source_cda: str,
    source_office: str,
    target_cda: str,
    target_api_key: Optional[str],
    verbose: int,
    ts_id: Optional[str],
    dry_run: bool,
    ts_group: Optional[str],
    ts_group_category_id: Optional[str],
    ts_group_category_office_id: Optional[str],
    begin: Optional[datetime] = None,
    end: Optional[datetime] = None,
):
    ts_ids = None
    if ts_id:
        ts_ids = [item.strip() for item in ts_id.split(",") if item.strip()]
        if not ts_ids:
            raise click.UsageError(
                "--ts-id must contain at least one non-empty timeseries ID."
            )
    if (ts_id is None) == (ts_group is None):
        raise click.UsageError("Exactly one of --ts-id or --ts-group must be provided.")
    from cwmscli.load.timeseries.timeseries_data import _load_timeseries_data

    _load_timeseries_data(
        source_cda=source_cda,
        source_office=source_office,
        target_cda=target_cda,
        target_api_key=target_api_key,
        verbose=verbose,
        dry_run=dry_run,
        ts_ids=ts_ids,
        ts_group=ts_group,
        ts_group_category_id=ts_group_category_id,
        ts_group_category_office_id=ts_group_category_office_id,
        begin=begin,
        end=end,
    )
