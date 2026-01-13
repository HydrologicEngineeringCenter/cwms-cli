from typing import Optional

import click

from cwmscli import requirements as reqs
from cwmscli.load.root import (
    load_group,
    shared_source_target_options,
    validate_cda_targets,
)
from cwmscli.utils.deps import requires


@load_group.group(
    "timeseries", help="Copy timeseries IDs from a source CDA to a target CDA."
)
@click.pass_context
def timeseries(ctx):
    pass


@timeseries.command(
    "ids-all",
    help="Copy ALL timeseries IDs for locations in a target CDA from a source CDA.",
)
@shared_source_target_options
@click.option(
    "--timeseries-id-regex",
    "timeseries_id_regex",
    default=None,
    type=str,
    help="regex filter for timeseries ID (e.g. 'LocID.*').",
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
