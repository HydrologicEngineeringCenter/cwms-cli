# cwmscli/load/timeseries/timeseries_data.py
import logging
from datetime import datetime
from typing import Optional

import click


def _extract_timeseries_groups(payload) -> list[dict]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _group_id(group: dict) -> str:
    value = group.get("id")
    return str(value) if value else "<unknown>"


def _category_id(group: dict) -> Optional[str]:
    category = group.get("time-series-category")
    if isinstance(category, dict) and category.get("id"):
        return str(category["id"])
    return None


def _assigned_timeseries(group: dict) -> list[dict]:
    assigned = group.get("assigned-time-series", [])
    if isinstance(assigned, list):
        return [item for item in assigned if isinstance(item, dict)]
    return []


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
        ts_group_data = cwms.get_timeseries_groups(
            office_id=source_office,
            include_assigned=True,
            timeseries_category_like=ts_group_category_id,
            timeseries_group_like=ts_group,
            category_office_id=ts_group_category_office_id,
        )
        groups = _extract_timeseries_groups(ts_group_data.json)
        if not groups:
            raise click.ClickException(
                f"No timeseries groups matched '{ts_group}' for office '{source_office}'."
            )

        logging.info(
            f"Matched {len(groups)} timeseries group(s) for pattern {ts_group}."
        )
        logging.info(f"Storing TSID from begin: {begin} to end: {end}")

        matched_groups: list[tuple[str, Optional[str], list[str]]] = []
        combined_ts_ids: list[str] = []

        for group in groups:
            group_name = _group_id(group)
            category_name = _category_id(group)
            office_ts_ids = [
                str(item["timeseries-id"])
                for item in _assigned_timeseries(group)
                if item.get("office-id") == source_office and item.get("timeseries-id")
            ]
            matched_groups.append((group_name, category_name, office_ts_ids))
            combined_ts_ids.extend(office_ts_ids)

        click.echo(
            f"Matched {len(matched_groups)} timeseries group(s) for office '{source_office}':"
        )
        for group_name, category_name, office_ts_ids in matched_groups:
            category_text = f" (category: {category_name})" if category_name else ""
            click.echo(
                f"  - {group_name}{category_text}: {len(office_ts_ids)} timeseries for office {source_office}"
            )

        deduped_ts_ids = list(dict.fromkeys(combined_ts_ids))
        if not deduped_ts_ids:
            raise click.ClickException(
                f"No assigned timeseries in the matched group set belong to office '{source_office}'."
            )
        ts_id_groups.append((source_office, deduped_ts_ids))

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
