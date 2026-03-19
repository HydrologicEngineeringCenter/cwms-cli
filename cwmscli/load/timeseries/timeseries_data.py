# cwmscli/load/timeseries/timeseries_data.py
import logging
from datetime import datetime
from typing import Optional

import click


def _load_timeseries_data(
    source_cda: str,
    source_office: str,
    target_cda: str,
    target_api_key: Optional[str],
    verbose: int,
    dry_run: bool,
    ts_ids: Optional[list[str]] = None,
    ts_group: Optional[str] = None,
    ts_group_category_id: Optional[str] = None,
    ts_group_category_office_id: Optional[str] = None,
    begin: Optional[datetime] = None,
    end: Optional[datetime] = None,
):
    import cwms

    def copy_timeseries_for_office(
        current_ts_ids: list[str], current_office: str
    ) -> None:
        ts_data = cwms.get_multi_timeseries_df(
            ts_ids=current_ts_ids,
            office_id=current_office,
            melted=True,
            begin=begin,
            end=end,
        )
        if dry_run:
            click.echo("Dry run enabled. No changes will be made.")
            logging.debug(
                f"Would store {ts_data} for {current_ts_ids}({current_office})"
            )
            return
        if ts_data.empty:
            click.echo(
                f"No data returned for timeseries ({', '.join(current_ts_ids)}) in office {current_office}."
            )
            return
        ts_data = ts_data.dropna(subset=["value"]).copy()
        if ts_data.empty:
            click.echo(
                f"No non-null values returned for timeseries ({', '.join(current_ts_ids)}) in office {current_office}."
            )
            return
        cwms.init_session(api_root=target_cda, api_key=target_api_key)
        cwms.store_multi_timeseries_df(
            data=ts_data,
            office_id=current_office,
            store_rule="REPLACE_ALL",
            override_protection=False,
        )

    if verbose:
        click.echo(
            f"Loading timeseries data from source CDA '{source_cda}' (office '{source_office}') "
            f"to target CDA '{target_cda}'."
        )
    cwms.init_session(api_root=source_cda, api_key=None)
    ts_id_groups: list[tuple[str, list[str]]] = []

    if ts_ids:
        ts_id_groups.append((source_office, ts_ids))

    if ts_group:
        ts_group_data = cwms.get_timeseries_group(
            group_id=ts_group,
            category_id=ts_group_category_id,
            office_id=source_office,
            category_office_id=ts_group_category_office_id,
        )
        logging.info(
            f"Found {len(ts_group_data.json.get('assigned-time-series', []))} timeseries in group {ts_group}."
        )
        logging.info(f"Storing TSID from begin: {begin} to end: {end}")
        ts_ids_by_office: dict[str, list[str]] = {}
        for ts in ts_group_data.json.get("assigned-time-series", []):
            member_office = ts["office-id"]
            ts_ids_by_office.setdefault(member_office, []).append(ts["timeseries-id"])
        ts_id_groups.extend(ts_ids_by_office.items())

    for current_office, current_ts_ids in ts_id_groups:
        try:
            copy_timeseries_for_office(current_ts_ids, current_office)
        except Exception as e:
            click.echo(
                f"Error storing timeseries ({', '.join(current_ts_ids)}) data: {e}",
                err=True,
            )

    if verbose:
        click.echo("Timeseries data copy operation completed.")
