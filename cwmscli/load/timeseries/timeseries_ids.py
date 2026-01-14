# cwmscli/load/timeseries_ids.py
from turtle import pd
from typing import Optional

import click
import pandas as pd


def load_timeseries_ids(
    source_cda: str,
    source_office: str,
    target_cda: str,
    target_api_key: Optional[str],
    verbose: int,
    dry_run: bool,
    timeseries_id_regex: Optional[str] = None,
):
    import cwms

    if verbose:
        click.echo(
            f"Loading timeseries IDs from source CDA '{source_cda}' (office '{source_office}') "
            f"to target CDA '{target_cda}'."
        )

    cwms.init_session(api_root=source_cda, api_key=None)
    ts_ids = cwms.get_timeseries_identifiers(
        office_id=source_office, timeseries_id_regex=timeseries_id_regex
    ).df

    cwms.init_session(api_root=target_cda, api_key=target_api_key)
    # only grab time_ids for locations that are in the target database
    locations = cwms.get_locations_catalog(office_id=source_office)
    ts_ids[["location-id", "param", "type", "int", "dur", "ver"]] = ts_ids[
        "time-series-id"
    ].str.split(".", expand=True)
    locs = locations.df.rename(columns={"name": "location-id", "office": "office-id"})
    ts_lo_ids = pd.merge(ts_ids, locs, how="inner", on=["location-id", "office-id"])

    if verbose:
        click.echo(f"Found {len(ts_lo_ids)} timeseries IDs to copy.")

    errors = 0
    for i, row in ts_lo_ids.iterrows():
        ts_id = row["time-series-id"]
        if dry_run:
            click.echo(
                f"[dry-run] would store Timeseries ID(name={ts_id}) to {target_cda} ({source_office})"
            )
            continue
        t_id_json = {
            "office-id": row["office-id"],
            "time-series-id": ts_id,
            "timezone-name": row["timezone-name"],
            "interval-offset-minutes": float(row["interval-offset-minutes"]),
            "active": row["active_x"],
        }
        try:
            result = cwms.store_timeseries_identifier(
                data=t_id_json, fail_if_exists=False
            )
            if verbose:
                click.echo(result)
        except Exception as e:
            errors += 1
            click.echo(f"Error storing location {ts_id}: \n\t{e}", err=True)

    if errors:
        raise click.ClickException(f"Completed with {errors} error(s).")
    if verbose:
        click.echo("Timeseries ID copy operation completed.")
