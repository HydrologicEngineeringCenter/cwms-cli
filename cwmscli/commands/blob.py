import base64
import imghdr
import json
import logging
import mimetypes
import os
import re
import sys
from typing import Optional, Sequence

import click
import cwms
import pandas as pd
import requests

# used to rebuild data URL for images
DATA_URL_RE = re.compile(r"^data:(?P<mime>[^;]+);base64,(?P<data>.+)$", re.I | re.S)


def _save_base64(
    b64_or_dataurl: str,
    dest: str,
    media_type_hint: str | None = None,
) -> str:
    m = DATA_URL_RE.match(b64_or_dataurl.strip())
    if m:
        media_type = m.group("mime")
        b64 = m.group("data")
    else:
        media_type = media_type_hint
        b64 = b64_or_dataurl

    compact = re.sub(r"\s+", "", b64)
    try:
        data = base64.b64decode(compact, validate=True)
    except Exception:
        data = base64.b64decode(compact + "=" * (-len(compact) % 4))

    base, ext = os.path.splitext(dest)
    if not ext:
        # guess extension from mime or bytes
        if media_type:
            ext = mimetypes.guess_extension(media_type.split(";")[0].lower()) or ""
            if ext == ".jpe":
                ext = ".jpg"
        if not ext:
            kind = imghdr.what(None, data)
            if kind == "jpeg":
                kind = "jpg"
            ext = f".{kind}" if kind else ".bin"
        dest = base + ext

    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    with open(dest, "wb") as f:
        f.write(data)
    return dest


def store_blob(**kwargs):
    file_data = kwargs.get("file_data")
    blob_id = kwargs.get("blob_id").upper()
    if file_data is None:
        raise ValueError("store_blob requires file_data")
    # Attempt to determine what media type should be used for the mime-type if one is not presented based on the file extension
    media = kwargs.get("media_type") or get_media_type(kwargs.get("input_file"))

    logging.debug(
        f"Office: {kwargs.get('office')}  Output ID: {blob_id}  Media: {media}"
    )

    blob = {
        "office-id": kwargs.get("office"),
        "id": blob_id,
        "description": json.dumps(kwargs.get("description")),
        "media-type-id": media,
        "value": base64.b64encode(file_data).decode("utf-8"),
    }

    params = {"fail-if-exists": not kwargs.get("overwrite")}

    if kwargs.get("dry_run"):
        logging.info(
            f"--dry-run enabled. Would POST to {kwargs.get('api_root')}/blobs with params={params}"
        )
        logging.info(
            f"Blob payload summary: office-id={kwargs.get('office')}, id={blob_id}, media={media}",
        )
        logging.info(
            json.dumps(
                {
                    "url": f"{kwargs.get('api_root')}blobs",
                    "params": params,
                    "blob": {**blob, "value": f"<base64:{len(blob['value'])} chars>"},
                },
                indent=2,
            )
        )
        sys.exit(0)

    try:
        cwms.store_blobs(blob, fail_if_exists=kwargs.get("overwrite"))
        logging.info(f"Successfully stored blob with ID: {blob_id}")
        logging.info(
            f"View: {kwargs.get('api_root')}blobs/{blob_id}?office={kwargs.get('office')}"
        )
        click.echo(
            f"{kwargs.get('api_root')}blobs/{blob_id}?office={kwargs.get('office')}"
        )
    except requests.HTTPError as e:
        # Include response text when available
        detail = getattr(e.response, "text", "") or str(e)
        logging.error(f"Failed to store blob (HTTP): {detail}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Failed to store blob: {e}")
        sys.exit(1)


def retrieve_blob(**kwargs):
    blob_id = kwargs.get("blob_id").upper()
    logging.debug(f"Office: {kwargs.get('office')}  Blob ID: {blob_id}")
    try:
        blob = cwms.get_blob(
            office_id=kwargs.get("office"),
            blob_id=blob_id,
        )
        logging.info(
            f"Successfully retrieved blob with ID: {blob_id}",
        )
        _save_base64(blob, dest=blob_id)
        logging.info(f"Downloaded blob to: {blob_id}")
    except requests.HTTPError as e:
        detail = getattr(e.response, "text", "") or str(e)
        logging.error(f"Failed to retrieve blob (HTTP): {detail}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Failed to retrieve blob: {e}")
        sys.exit(1)


def delete_blob(**kwargs):
    blob_id = kwargs.get("blob_id").upper()
    logging.debug(f"Office: {kwargs.get('office')}  Blob ID: {blob_id}")

    try:
        # cwms.delete_blob(
        #     office_id=kwargs.get("office"),
        #     blob_id=kwargs.get("blob_id").upper(),
        # )
        logging.info(f"Successfully deleted blob with ID: {blob_id}")
    except requests.HTTPError as e:
        details = getattr(e.response, "text", "") or str(e)
        logging.error(f"Failed to delete blob (HTTP): {details}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Failed to delete blob: {e}")
        sys.exit(1)


def list_blobs(
    office: Optional[str] = None,
    blob_id_like: Optional[str] = None,
    columns: Optional[Sequence[str]] = None,
    sort_by: Optional[Sequence[str]] = None,
    ascending: bool = True,
    limit: Optional[int] = None,
) -> pd.DataFrame:
    logging.info(f"Listing blobs for office: {office!r}...")
    result = cwms.get_blobs(office_id=office, blob_id_like=blob_id_like)

    # Accept either a DataFrame or a JSON/dict-like response
    if isinstance(result, pd.DataFrame):
        df = result.copy()
    else:
        # Expecting normal blob return structure
        data = getattr(result, "json", None)
        if callable(data):
            data = result.json()
        df = pd.DataFrame((data or {}).get("blobs", []))

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

    logging.info(f"Found {len(df):,} blobs")
    # List the blobs in the logger
    for _, row in df.iterrows():
        logging.info(f"Blob ID: {row['id']}, Description: {row.get('description')}")
    return df


def get_media_type(file_path: str) -> str:
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type or "application/octet-stream"


def main(
    directive: str,
    input_file: str,
    blob_id: str,
    description: Optional[str],
    media_type: Optional[str],
    office: str,
    api_root: str,
    api_key: str,
    overwrite: Optional[bool] = True,
    dry_run: Optional[bool] = False,
):
    """
    Upload, Download, Delete, or Update blob data in CWMS.

    DIRECTIVE is the action to perform (upload, download, delete, update).
    INPUT_FILE is the path to the file on disk.
    BLOB_ID   is the blob ID to store under.
    """

    cwms.api.init_session(api_root=api_root, api_key=api_key)
    file_data = None
    if input_file and directive in ["upload", "update"]:
        try:
            file_size = os.path.getsize(input_file)
            with open(input_file, "rb") as f:
                file_data = f.read()
            logging.info(f"Read file: {input_file} ({file_size} bytes)")
        except Exception as e:
            logging.error(f"Failed to read file: {e}")
            sys.exit(1)

    # Determine what should be done based on directive
    if directive == "upload":
        store_blob(
            office=office,
            input_file=input_file,
            blob_id=blob_id,
            description=description,
            media_type=media_type,
            file_data=file_data,
            overwrite=overwrite,
            dry_run=dry_run,
        )
    elif directive == "list":
        list_blobs(office=office, blob_id_like=blob_id, sort_by="blob_id")
    elif directive == "download":
        retrieve_blob(
            office=office,
            blob_id=blob_id,
        )
    elif directive == "delete":
        # TODO: Delete endpoint does not exist in cwms-python yet
        logging.warning(
            "[NOT IMPLEMENTED] Delete Blob is not supported yet!\n\thttps://github.com/HydrologicEngineeringCenter/cwms-python/issues/192"
        )
        pass
    elif directive == "update":
        # TODO: Patch endpoint does not exist in cwms-python yet
        logging.warning(
            "[NOT IMPLEMENTED] Update Blob is not supported yet! Consider overwriting instead if a rename is not needed.\n\thttps://github.com/HydrologicEngineeringCenter/cwms-python/issues/192"
        )
        pass
