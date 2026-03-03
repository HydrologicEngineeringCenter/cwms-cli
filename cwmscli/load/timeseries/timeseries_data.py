# cwmscli/load/timeseries/timeseries_data.py
import logging
from datetime import datetime
from typing import Optional

import click
import pandas as pd


def _load_timeseries_data(
    source_cda: str,
    source_office: str,
    target_cda: str,
    target_api_key: Optional[str],
    verbose: int,
    dry_run: bool,
    ts_id: Optional[str] = None,
    ts_group: Optional[str] = None,
    ts_group_category_id: Optional[str] = None,
    ts_group_category_office_id: Optional[str] = None,
    begin: Optional[datetime] = None,
    end: Optional[datetime] = None,
):
    import cwms

    if verbose:
        click.echo(
            f"Loading timeseries data from source CDA '{source_cda}' (office '{source_office}') "
            f"to target CDA '{target_cda}'."
        )
    cwms.init_session(api_root=source_cda, api_key=None)
    # User has a ts_id
    if ts_id and not ts_group:
        ts_data = cwms.get_timeseries(
            ts_id=ts_id,
            office_id=source_office,
            begin=begin,
            end=end,
        )
        # store the retrieved timeseries data into the target database
        try:
            if dry_run:
                click.echo("Dry run enabled. No changes will be made.")
                logging.debug(f"Would store {ts_data} for {ts_id}({source_office})")
            else:
                cwms.init_session(api_root=target_cda, api_key=target_api_key)
                cwms.store_timeseries(
                    data=ts_data.json,
                    store_rule="REPLACE_ALL",
                    override_protection=False,
                )
        except Exception as e:
            click.echo(f"Error storing timeseries ({ts_id}) data: {e}", err=True)
    # User did not have a ts_id but has a ts_group
    if ts_group:
        ts_ids = cwms.get_timeseries_group(
            group_id=ts_group,
            category_id=ts_group_category_id,
            office_id=source_office,
            category_office_id=ts_group_category_office_id,
        )
        logging.info(
            f"Found {len(ts_ids.json.get('assigned-time-series', []))} timeseries in group {ts_group}."
        )
        logging.info(f"Storing TSID from begin: {begin} to end: {end}")
        for ts in ts_ids.json.get("assigned-time-series", []):
            try:
                if dry_run:
                    click.echo(
                        f"Would store timeseries data for {ts['timeseries-id']}({ts['office-id']})"
                    )
                else:
                    cwms.init_session(api_root=source_cda, api_key=None)
                    ts_data = cwms.get_timeseries(
                        ts_id=ts["timeseries-id"],
                        office_id=ts["office-id"],
                        begin=begin,
                        end=end,
                    )
                    cwms.init_session(api_root=target_cda, api_key=target_api_key)
                    # Convert the TS Values to a format CDA expects
                    ts_cda_format_values = [
                        [
                            pd.to_datetime(value["date-time"]).isoformat(),
                            value["value"],
                            value["quality-code"],
                        ]
                        for value in ts_data.json.get("values", [])
                    ]
                    # Build a payload dict with formatted values instead of copying the response object
                    ts_data_copy = ts_data.json.copy()
                    ts_data_copy["values"] = ts_cda_format_values
                    cwms.store_timeseries(
                        data=ts_data_copy,
                        store_rule="REPLACE_ALL",
                        override_protection=False,
                    )
                    click.echo(
                        f"Wrote {len(ts_data_copy.get('values', []))} values to {ts['timeseries-id']}."
                    )
            except Exception as e:
                logging.warning(
                    f"Error storing timeseries ({ts['timeseries-id']}) data: {e}",
                    exc_info=True,
                )

    if verbose:
        click.echo("Timeseries data copy operation completed.")
