import base64
import json
import logging
import mimetypes
import os
import re
import sys
from typing import Optional, Sequence

import cwms
import pandas as pd
import requests

from cwmscli.utils import get_api_key, has_invalid_chars


def list_clobs(
    office: Optional[str] = None,
    clob_id_like: Optional[str] = None,
    columns: Optional[Sequence[str]] = None,
    sort_by: Optional[Sequence[str]] = None,
    ascending: bool = True,
    limit: Optional[int] = None,
) -> pd.DataFrame:
    logging.info(f"Listing clobs for office: {office!r}...")
    result = cwms.get_clobs(office_id=office, clob_id_like=clob_id_like)

    # Accept either a DataFrame or a JSON/dict-like response
    if isinstance(result, pd.DataFrame):
        df = result.copy()
    else:
        # Expecting normal clob return structure
        data = getattr(result, "json", None)
        if callable(data):
            data = result.json()
        df = pd.DataFrame((data or {}).get("clobs", []))

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

    logging.info(f"Found {len(df):,} clob(s)")
    # List the clobs in the logger
    for _, row in df.iterrows():
        logging.info(f"clob ID: {row['id']}, Description: {row.get('description')}")
    return df


def upload_cmd(
    input_file: str,
    clob_id: str,
    description: str,
    overwrite: bool,
    dry_run: bool,
    office: str,
    api_root: str,
    api_key: str,
):
    cwms.init_session(api_root=api_root, api_key=get_api_key(api_key, ""))
    try:
        file_size = os.path.getsize(input_file)
        with open(input_file, "r") as f:
            file_data = f.read()
        logging.info(f"Read file: {input_file} ({file_size} bytes)")
    except Exception as e:
        logging.error(f"Failed to read file: {e}")
        sys.exit(1)

    clob_id_up = clob_id.upper()
    logging.debug(f"Office={office} clobID={clob_id_up}")

    clob = {
        "office-id": office,
        "id": clob_id_up,
        "description": (
            json.dumps(description)
            if isinstance(description, (dict, list))
            else description
        ),
        "value": file_data,
    }
    params = {"fail-if-exists": not overwrite}

    if dry_run:
        logging.info(f"DRY RUN: would POST {api_root}clobs with params={params}")
        logging.info(
            json.dumps(
                {
                    "url": f"{api_root}clobs",
                    "params": params,
                    "clob": {**clob, "value": f'<{len(clob["value"])} chars>'},
                },
                indent=2,
            )
        )
        return

    try:
        cwms.store_clobs(clob, fail_if_exists=not overwrite)
        logging.info(f"Uploaded clob: {clob_id_up}")
        # IDs with / can't be used directly in the path
        # TODO: check for other disallowed characters
        if has_invalid_chars(clob_id_up):
            logging.info(
                f"View: {api_root}clobs/ignored?clob-id={clob_id_up}&office={office}"
            )
        else:
            logging.info(f"View: {api_root}clobs/{clob_id_up}?office={office}")
    except requests.HTTPError as e:
        detail = getattr(e.response, "text", "") or str(e)
        logging.error(f"Failed to upload (HTTP): {detail}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Failed to upload: {e}")
        sys.exit(1)


def download_cmd(
    clob_id: str, dest: str, office: str, api_root: str, api_key: str, dry_run: bool
):
    if dry_run:
        logging.info(
            f"DRY RUN: would GET {api_root} clob with clob-id={clob_id} office={office}."
        )
        return
    cwms.init_session(api_root=api_root, api_key=get_api_key(api_key, ""))
    bid = clob_id.upper()
    logging.debug(f"Office={office} clobID={bid}")

    try:
        clob = cwms.get_clob(office_id=office, clob_id=bid)
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        sys.stderr.write(repr(clob.json) + "\n")
        with open(dest, "wt") as f:
            f.write(clob.json["value"])

        logging.info(f"Downloaded clob to: {dest}")
    except requests.HTTPError as e:
        detail = getattr(e.response, "text", "") or str(e)
        logging.error(f"Failed to download (HTTP): {detail}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Failed to download: {e}")
        sys.exit(1)


def delete_cmd(clob_id: str, office: str, api_root: str, api_key: str, dry_run: bool):

    if dry_run:
        logging.info(
            f"DRY RUN: would DELETE {api_root} clob with clob-id={clob_id} office={office}"
        )
        return
    cwms.init_session(api_root=api_root, api_key=api_key)
    cwms.delete_clob(office_id=office, clob_id=clob_id)
    logging.info(f"Deleted clob: {clob_id} for office: {office}")


def update_cmd(
    input_file: str,
    clob_id: str,
    description: str,
    ignore_nulls: bool,
    dry_run: bool,
    office: str,
    api_root: str,
    api_key: str,
):
    if dry_run:
        logging.info(
            f"DRY RUN: would PATCH {api_root} clob with clob-id={clob_id} office={office}"
        )
        return
    file_data = None
    if input_file:
        try:
            file_size = os.path.getsize(input_file)
            with open(input_file, "r") as f:
                file_data = f.read()
            logging.info(f"Read file: {input_file} ({file_size} bytes)")
        except Exception as e:
            logging.error(f"Failed to read file: {e}")
            sys.exit(1)
    # Setup minimum required payload
    clob = {"office-id": office, "id": clob_id.upper()}
    if description:
        clob["description"] = description

    if file_data:
        clob["value"] = file_data
    cwms.init_session(api_root=api_root, api_key=api_key)
    cwms.update_clob(clob, clob_id.upper(), ignore_nulls=ignore_nulls)


def list_cmd(
    clob_id_like: str,
    columns: list[str],
    sort_by: list[str],
    desc: bool,
    limit: int,
    to_csv: str,
    office: str,
    api_root: str,
    api_key: str,
):
    cwms.init_session(api_root=api_root, api_key=get_api_key(api_key, None))
    df = list_clobs(
        office=office,
        clob_id_like=clob_id_like,
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
            # Left-align all columns
            logging.info(
                "\n"
                + df.apply(
                    lambda s: (s := s.astype(str).str.strip()).str.ljust(
                        s.str.len().max()
                    )
                ).to_string(index=False, justify="left")
            )
