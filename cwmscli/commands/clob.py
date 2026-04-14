import json
import logging
import os
import sys
from typing import Optional, Sequence

import cwms
import pandas as pd
import requests
from cwms import api as cwms_api

from cwmscli.utils import get_api_key, has_invalid_chars, log_scoped_read_hint


def _join_api_url(api_root: str, path: str) -> str:
    return f"{api_root.rstrip('/')}/{path.lstrip('/')}"


def _resolve_optional_api_key(api_key: Optional[str], anonymous: bool) -> Optional[str]:
    if anonymous or not api_key:
        return None
    return get_api_key(api_key, None)


def _write_clob_content(content: str, dest: str) -> str:
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    with open(dest, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    return dest


def _default_download_dest(clob_id: str) -> str:
    target = clob_id.lstrip("/\\")
    if not target:
        raise ValueError(
            "Clob ID must include a non-root destination name. "
            "Pass --dest explicitly if needed."
        )
    return target


def _clob_endpoint_id(clob_id: str) -> tuple[str, Optional[str]]:
    normalized = clob_id.upper()
    if has_invalid_chars(normalized):
        return "ignored", normalized
    return normalized, None


def _get_special_clob_text(*, office: str, clob_id: str) -> str:
    with cwms_api.SESSION.get(
        "clobs/ignored",
        params={"office": office, "clob-id": clob_id},
        headers={"Accept": "text/plain"},
    ) as response:
        response.raise_for_status()
        return response.text


def list_clobs(
    office: Optional[str] = None,
    clob_id_like: Optional[str] = None,
    columns: Optional[Sequence[str]] = None,
    sort_by: Optional[Sequence[str]] = None,
    ascending: bool = True,
    limit: Optional[int] = None,
    page_size: Optional[int] = None,
) -> pd.DataFrame:
    logging.info(f"Listing clobs for office: {office!r}...")
    fetch_page_size = page_size if page_size is not None else limit
    result = cwms.get_clobs(
        office_id=office,
        clob_id_like=clob_id_like,
        page_size=fetch_page_size,
    )

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
    cwms.init_session(api_root=api_root, api_key=get_api_key(api_key, None))
    try:
        file_size = os.path.getsize(input_file)
        with open(input_file, "r", encoding="utf-8") as f:
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
    view_url = _join_api_url(api_root, f"clobs/{clob_id_up}?office={office}")

    if dry_run:
        logging.info(
            f"DRY RUN: would POST {_join_api_url(api_root, 'clobs')} with params={params}"
        )
        logging.info(
            json.dumps(
                {
                    "url": _join_api_url(api_root, "clobs"),
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
        if has_invalid_chars(clob_id_up):
            logging.info(
                f"View: {_join_api_url(api_root, f'clobs/ignored?clob-id={clob_id_up}&office={office}')}"
            )
        else:
            logging.info(f"View: {view_url}")
    except requests.HTTPError as e:
        detail = getattr(e.response, "text", "") or str(e)
        logging.error(f"Failed to upload (HTTP): {detail}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Failed to upload: {e}")
        sys.exit(1)


def download_cmd(
    clob_id: str,
    dest: str,
    office: str,
    api_root: str,
    api_key: str,
    dry_run: bool,
    anonymous: bool = False,
):
    if dry_run:
        logging.info(
            f"DRY RUN: would GET {api_root} clob with clob-id={clob_id} office={office}."
        )
        return
    resolved_api_key = _resolve_optional_api_key(api_key, anonymous)
    cwms.init_session(api_root=api_root, api_key=resolved_api_key)
    bid = clob_id.upper()
    logging.debug(f"Office={office} clobID={bid}")

    try:
        path_id, query_id = _clob_endpoint_id(bid)
        if query_id is None:
            clob = cwms.get_clob(office_id=office, clob_id=path_id)
            payload = getattr(clob, "json", clob)
            if callable(payload):
                payload = payload()
            if isinstance(payload, dict):
                content = payload.get("value", "")
            else:
                content = str(payload)
        else:
            content = _get_special_clob_text(office=office, clob_id=query_id)
        target = dest or _default_download_dest(bid)
        _write_clob_content(content, target)
        logging.info(f"Downloaded clob to: {target}")
    except requests.HTTPError as e:
        detail = getattr(e.response, "text", "") or str(e)
        logging.error(f"Failed to download (HTTP): {detail}")
        log_scoped_read_hint(
            api_key=resolved_api_key,
            anonymous=anonymous,
            office=office,
            action="download",
            resource="clob content",
        )
        sys.exit(1)
    except Exception as e:
        logging.error(f"Failed to download: {e}")
        log_scoped_read_hint(
            api_key=resolved_api_key,
            anonymous=anonymous,
            office=office,
            action="download",
            resource="clob content",
        )
        sys.exit(1)


def delete_cmd(clob_id: str, office: str, api_root: str, api_key: str, dry_run: bool):

    if dry_run:
        logging.info(
            f"DRY RUN: would DELETE {api_root} clob with clob-id={clob_id} office={office}"
        )
        return
    cwms.init_session(api_root=api_root, api_key=get_api_key(api_key, None))
    cid = clob_id.upper()
    path_id, query_id = _clob_endpoint_id(cid)
    if query_id is None:
        cwms.delete_clob(office_id=office, clob_id=cid)
    else:
        cwms_api.delete(
            f"clobs/{path_id}", params={"office": office, "clob-id": query_id}
        )
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
            with open(input_file, "r", encoding="utf-8") as f:
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
    cwms.init_session(api_root=api_root, api_key=get_api_key(api_key, None))
    cid = clob_id.upper()
    path_id, query_id = _clob_endpoint_id(cid)
    if query_id is None:
        cwms.update_clob(clob, cid, ignore_nulls=ignore_nulls)
    else:
        cwms_api.patch(
            f"clobs/{path_id}",
            data=clob,
            params={"clob-id": query_id, "ignore-nulls": ignore_nulls},
        )
    logging.info(f"Updated clob: {clob_id} for office: {office}")


def list_cmd(
    clob_id_like: str,
    columns: list[str],
    sort_by: list[str],
    desc: bool,
    limit: int,
    page_size: int,
    to_csv: str,
    office: str,
    api_root: str,
    api_key: str,
    anonymous: bool = False,
):
    resolved_api_key = _resolve_optional_api_key(api_key, anonymous)
    cwms.init_session(api_root=api_root, api_key=resolved_api_key)
    try:
        df = list_clobs(
            office=office,
            clob_id_like=clob_id_like,
            columns=columns,
            sort_by=sort_by,
            ascending=not desc,
            limit=limit,
            page_size=page_size,
        )
    except Exception:
        log_scoped_read_hint(
            api_key=resolved_api_key,
            anonymous=anonymous,
            office=office,
            action="list",
            resource="clob content",
        )
        raise
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
