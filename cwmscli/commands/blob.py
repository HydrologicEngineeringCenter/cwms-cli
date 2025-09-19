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

from cwmscli.utils import get_api_key
from cwmscli.utils.deps import requires

# used to rebuild data URL for images
DATA_URL_RE = re.compile(r"^data:(?P<mime>[^;]+);base64,(?P<data>.+)$", re.I | re.S)


@requires(
    {
        "module": "imghdr",
        "package": "standard-imghdr",
        "version": "3.0.0",
        "desc": "Package to help detect image types",
        "link": "https://docs.python.org/3/library/imghdr.html",
    }
)
def _determine_ext(data: bytes | str, write_type: str) -> str:
    """
    Attempt to determine the file extension from the data itself.
    Requires the imghdr module (lazy import) to inspect the bytes for image types.
    If not an image, defaults to .bin

    Args:
        data: The binary data or base64 string to inspect.
        write_type: The mode in which the data will be written ('wb' for binary, 'w' for text).

    Returns:
        The determined file extension, including the leading dot (e.g., '.png', '.jpg').
    """
    import imghdr

    kind = imghdr.what(None, data)
    if kind == "jpeg":
        kind = "jpg"
    return f".{kind}" if kind else ".bin"


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
    data = b64
    compact = re.sub(r"\s+", "", b64)
    base, ext = os.path.splitext(dest)
    # If an image was uploaded, convert it back from base64 encoding
    # TODO: probably should handle this better in cwms-python?
    write_type = "w"
    if ext.lower() in [".png", ".jpg"]:
        write_type = "wb"
        try:
            data = base64.b64decode(compact, validate=True)
        except Exception:
            data = base64.b64decode(compact + "=" * (-len(compact) % 4))
    if not ext:
        # guess extension from mime or bytes
        if media_type:
            ext = mimetypes.guess_extension(media_type.split(";")[0].lower()) or ""
            if ext == ".jpe":
                ext = ".jpg"
        # last resort, try to determine from the data itself
        # requires imghdr to dig into the bytes to determine image type
        if not ext:
            ext = _determine_ext(data, write_type)
        dest = base + ext

    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    with open(dest, write_type) as f:
        f.write(data)
    return dest


def store_blob(**kwargs):
    file_data = kwargs.get("file_data")
    blob_id = kwargs.get("blob_id").upper()
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
    except requests.HTTPError as e:
        # Include response text when available
        detail = getattr(e.response, "text", "") or str(e)
        logging.error(f"Failed to store blob (HTTP): {detail}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Failed to store blob: {e}")
        sys.exit(1)


def retrieve_blob(**kwargs):
    blob_id = kwargs.get("blob_id", "")
    if not blob_id:
        logging.warning(
            "Valid blob_id required to download a blob. cwms-cli blob download --blob-id=myid. Run the list directive to see options for your office."
        )
        sys.exit(0)
    blob_id = blob_id.upper()
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
    if directive in ["upload", "update"]:
        if not input_file or not os.path.isfile(input_file):
            logging.warning(
                "Valid input_file required for upload/update. Use --input-file to specify."
            )
            sys.exit(0)
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
            api_root=api_root,
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


def upload_cmd(
    input_file: str,
    blob_id: str,
    description: str,
    media_type: str,
    overwrite: bool,
    dry_run: bool,
    office: str,
    api_root: str,
    api_key: str,
):
    cwms.api.init_session(api_root=api_root, api_key=get_api_key(api_key, ""))
    try:
        file_size = os.path.getsize(input_file)
        with open(input_file, "rb") as f:
            file_data = f.read()
        logging.info(f"Read file: {input_file} ({file_size} bytes)")
    except Exception as e:
        logging.error(f"Failed to read file: {e}")
        sys.exit(1)

    media = media_type or get_media_type(input_file)
    blob_id_up = blob_id.upper()
    logging.debug(f"Office={office} BlobID={blob_id_up} Media={media}")

    blob = {
        "office-id": office,
        "id": blob_id_up,
        "description": (
            json.dumps(description)
            if isinstance(description, (dict, list))
            else description
        ),
        "media-type-id": media,
        "value": base64.b64encode(file_data).decode("utf-8"),
    }
    params = {"fail-if-exists": not overwrite}

    if dry_run:
        logging.info(f"--dry-run: would POST {api_root}blobs with params={params}")
        logging.info(
            json.dumps(
                {
                    "url": f"{api_root}blobs",
                    "params": params,
                    "blob": {**blob, "value": f'<base64:{len(blob["value"])} chars>'},
                },
                indent=2,
            )
        )
        return

    try:
        cwms.store_blobs(blob, fail_if_exists=overwrite)
        logging.info(f"Uploaded blob: {blob_id_up}")
        logging.info(f"View: {api_root}blobs/{blob_id_up}?office={office}")
    except requests.HTTPError as e:
        detail = getattr(e.response, "text", "") or str(e)
        logging.error(f"Failed to upload (HTTP): {detail}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Failed to upload: {e}")
        sys.exit(1)


def download_cmd(blob_id: str, dest: str, office: str, api_root: str, api_key: str):
    cwms.api.init_session(api_root=api_root, api_key=get_api_key(api_key, ""))
    bid = blob_id.upper()
    logging.debug(f"Office={office} BlobID={bid}")

    try:
        blob_b64 = cwms.get_blob(office_id=office, blob_id=bid)
        target = dest or bid
        _save_base64(blob_b64, dest=target)
        logging.info(f"Downloaded blob to: {target}")
    except requests.HTTPError as e:
        detail = getattr(e.response, "text", "") or str(e)
        logging.error(f"Failed to download (HTTP): {detail}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Failed to download: {e}")
        sys.exit(1)


def delete_cmd(blob_id: str, office: str, api_root: str, api_key: str):
    logging.warning(
        "[NOT IMPLEMENTED] Delete Blob is not supported yet.\n"
        "See: https://github.com/HydrologicEngineeringCenter/cwms-python/issues/192"
    )


def update_cmd(blob_id: str, input_file: str, office: str, api_root: str, api_key: str):
    logging.warning(
        "[NOT IMPLEMENTED] Update Blob is not supported yet. Consider --overwrite with upload.\n"
        "See: https://github.com/HydrologicEngineeringCenter/cwms-python/issues/192"
    )


def list_cmd(
    blob_id_like: str,
    columns: list[str],
    sort_by: list[str],
    desc: bool,
    limit: int,
    to_csv: str,
    office: str,
    api_root: str,
    api_key: str,
):
    cwms.api.init_session(api_root=api_root, api_key=get_api_key(api_key, None))
    df = list_blobs(
        office=office,
        blob_id_like=blob_id_like,
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
