import json
import logging
import os
import sys
from typing import Optional, Sequence

import cwms
import pandas as pd
import requests

from cwmscli.utils import get_api_key
from cwmscli.utils.io import write_to_file


def retrieve_group(
    group_id: str,
    category_office_id: str,
    group_office_id: str,
    category_id: str,
    office: str,
    dest_dir: Optional[str] = None,
):
    if not group_id:
        logging.warning(
            "Valid group_id required to download a group. cwms-cli group download --group-id=myid. Run the list directive to see options for your office."
        )
        sys.exit(0)
    logging.debug(f"Office: {office}  Group ID: {group_id}")
    try:
        group = cwms.get_timeseries_group(
            group_id=group_id,
            category_office_id=category_office_id,
            group_office_id=group_office_id,
            category_id=category_id,
            office_id=office,
        )
        logging.info(
            f"Successfully retrieved group with ID: {group_id}",
        )
        if dest_dir:
            write_to_file(
                file_path=os.path.join((dest_dir or "."), f"{office}_{group_id}.json"),
                data=json.dumps(group.json, indent=2),
            )
        else:
            sys.stdout.write(json.dumps(group.json))
            sys.stdout.write("\n")
            return group
    except requests.HTTPError as e:
        detail = getattr(e.response, "text", "") or str(e)
        logging.error(f"Failed to retrieve group (HTTP): {detail}")
        sys.exit(1)


def delete_group(**kwargs):
    group_id = kwargs.get("group_id").upper()
    logging.debug(f"Office: {kwargs.get('office')}  Group ID: {group_id}")

    try:
        # cwms.delete_group(
        #     office_id=kwargs.get("office"),
        #     group_id=kwargs.get("group_id").upper(),
        # )
        logging.info(f"Successfully deleted group with ID: {group_id}")
    except requests.HTTPError as e:
        details = getattr(e.response, "text", "") or str(e)
        logging.error(f"Failed to delete group (HTTP): {details}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Failed to delete group: {e}")
        sys.exit(1)


def list_groups(
    office: Optional[str] = None,
    include_assigned: Optional[bool] = None,
    timeseries_category_like: Optional[str] = None,
    category_office_id: Optional[str] = None,
    timeseries_group_like: Optional[str] = None,
    columns: Optional[Sequence[str]] = None,
    sort_by: Optional[Sequence[str]] = None,
    ascending: bool = True,
    limit: Optional[int] = None,
) -> pd.DataFrame:
    logging.info(f"Listing groups for office: {office!r}...")
    result = cwms.get_timeseries_groups(
        office_id=office,
        category_office_id=category_office_id,
        timeseries_group_like=timeseries_group_like,
        timeseries_category_like=timeseries_category_like,
        include_assigned=include_assigned,
    )

    # Accept either a DataFrame or a JSON/dict-like response
    if isinstance(result, pd.DataFrame):
        df = result.copy()
    else:
        # Expecting normal group return structure
        data = getattr(result, "json", None)
        if callable(data):
            data = result.json()
        df = pd.DataFrame((data or {}))

    # Allow column filtering
    if columns:
        keep = [c for c in columns if c in df.columns]
        if keep:
            df = df[keep]

    # Sort by option
    if sort_by:
        by = [c for c in sort_by if c in df.columns]
        if by:
            df = df.sort_values(by=by, ascending=ascending, kind="stable")

    # Optional limit
    if limit is not None:
        df = df.head(limit)

    logging.info(f"Found {len(df):,} group(s)")
    # List the groups in the logger
    for _, row in df.iterrows():
        logging.info(f"Group ID: {row['id']}, Description: {row.get('description')}")
    return df


def store_cmd(
    api_key: str,
    input_file: Optional[str],
    overwrite: Optional[bool],
    dry_run: Optional[bool],
    office: Optional[str],
    api_root: Optional[str],
):
    cwms.init_session(api_root=api_root, api_key=get_api_key(api_key, ""))
    # ----------------------------
    # Read file or stdin
    # ----------------------------
    file_data = None
    try:
        if input_file:
            file_size = os.path.getsize(input_file)
            with open(input_file, "rb") as f:
                file_data = f.read().decode("utf-8")
            logging.info(f"Read file: {input_file} ({file_size} bytes)")
        else:
            # Read from stdin (binary)
            logging.info("Reading input from stdin...")
            file_data = sys.stdin.buffer.read().decode("utf-8")
            if not file_data:
                logging.error("No input provided on stdin and no file specified.")
                sys.exit(1)
            logging.info(f"Read {len(file_data)} bytes from stdin")
    except Exception as e:
        logging.error(f"Failed to read input: {e}")
        sys.exit(1)

    params = {"fail-if-exists": not overwrite}

    # ----------------------------
    # Dry run
    # ----------------------------
    if dry_run:
        logging.info(f"DRY RUN: would POST {api_root}group with params={params}")
        logging.info(
            json.dumps(
                file_data,
                indent=2,
            )
        )
        return

    # ----------------------------
    # Upload
    # ----------------------------
    try:
        logging.debug(f"Uploading timeseries group: {file_data}")
        cwms.store_timeseries_groups(file_data, fail_if_exists=not overwrite)
        logging.info(f"Uploaded group successfully.")
    except requests.HTTPError as e:
        detail = getattr(e.response, "text", "") or str(e)
        logging.error(f"Failed to upload (HTTP): {detail}")
        sys.exit(1)


def retrieve_cmd(
    group_id: str,
    category_office_id: str,
    group_office_id: str,
    category_id: str,
    office: str,
    api_root: str,
    api_key: str,
    dry_run: bool,
    dest_dir: Optional[str] = None,
):
    if dry_run:
        logging.info(
            f"DRY RUN: would GET {api_root} group with group-id={group_id} office={office}."
        )
        return

    cwms.init_session(api_root=api_root, api_key=api_key)

    retrieve_group(
        group_id=group_id,
        category_office_id=category_office_id,
        group_office_id=group_office_id,
        category_id=category_id,
        office=office,
        dest_dir=dest_dir,
    )


def delete_cmd(
    group_id: str,
    category_id: str,
    office: str,
    api_root: str,
    api_key: str,
    dry_run: bool,
):

    if dry_run:
        logging.info(
            f"DRY RUN: would DELETE {api_root} group with group-id={group_id} office={office}"
        )
        return
    cwms.init_session(api_root=api_root, api_key=api_key)
    cwms.delete_timeseries_group(
        office_id=office, group_id=group_id, category_id=category_id
    )
    logging.info(f"Deleted group: {group_id} for office: {office}")


def update_cmd(
    input_file: str,
    group_id: str,
    description: str,
    media_type: str,
    overwrite: bool,
    dry_run: bool,
    office: str,
    api_root: str,
    api_key: str,
):
    if dry_run:
        logging.info(
            f"DRY RUN: would PATCH {api_root} group with group-id={group_id} office={office}"
        )
        return
    file_data = None
    if input_file:
        file_size = os.path.getsize(input_file)
        with open(input_file, "rb") as f:
            file_data = f.read()
        logging.info(f"Read file: {input_file} ({file_size} bytes)")
    # Setup minimum required payload
    group = {"office-id": office, "id": group_id.upper()}
    if description:
        group["description"] = description
    if media_type:
        group["media-type-id"] = media_type
    else:
        logging.info("Media type not specified; Retrieving existing media type...")
        group_metadata = cwms.get_groups(office_id=office, group_id_like=group_id)
        group["media-type-id"] = group_metadata.df.get(
            "media-type-id", "application/octet-stream"
        )[0]
        logging.info(f"Using existing media type: {group['media-type-id']}")

    if file_data:
        group["value"] = base64.b64encode(file_data).decode("utf-8")
    cwms.init_session(api_root=api_root, api_key=api_key)
    cwms.update_group(group, fail_if_not_exists=not overwrite)


def list_cmd(
    include_assigned: bool,
    timeseries_category_like: str,
    category_office_id: str,
    timeseries_group_like: str,
    columns: list[str],
    sort_by: list[str],
    desc: bool,
    limit: int,
    to_csv: str,
    office: str,
    api_root: str,
    api_key: str,
):
    cwms.init_session(api_root=api_root, api_key=api_key)
    df = list_groups(
        office=office,
        include_assigned=include_assigned,
        timeseries_category_like=timeseries_category_like,
        category_office_id=category_office_id,
        timeseries_group_like=timeseries_group_like,
        columns=columns,
        sort_by=sort_by,
        ascending=not desc,
        limit=limit,
    )
    if to_csv:
        df.to_csv(to_csv, index=False)
        logging.info(f"Wrote {len(df)} rows to {to_csv}")
    else:
        # Friendly console preview
        with pd.option_context("display.max_rows", 500, "display.max_columns", None):
            logging.info(df.to_string(index=False))
