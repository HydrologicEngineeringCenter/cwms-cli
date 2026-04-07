import base64
import binascii
import json
import logging
import mimetypes
import os
import re
import sys
from collections import defaultdict
from typing import Optional, Sequence, Tuple

from cwmscli.utils import colors, get_api_key, init_cwms_session, log_scoped_read_hint
from cwmscli.utils.click_help import DOCS_BASE_URL
from cwmscli.utils.deps import requires

# used to rebuild data URL for images
DATA_URL_RE = re.compile(r"^data:(?P<mime>[^;]+);base64,(?P<data>.+)$", re.I | re.S)
BASE64_TEXT_RE = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")
BLOB_DOCS_URL = f"{DOCS_BASE_URL}/cli/blob.html"


@requires(
    {
        "module": "imghdr",
        "package": "standard-imghdr",
        "version": "3.0.0",
        "desc": "Package to help detect image types",
        "link": "https://docs.python.org/3/library/imghdr.html",
    }
)
def _determine_ext(data: bytes) -> str:
    """
    Attempt to determine the file extension from the data itself.
    Requires the imghdr module (lazy import) to inspect the bytes for image types.
    If not an image, defaults to .bin

    Args:
        data: The binary data to inspect.

    Returns:
        The determined file extension, including the leading dot (e.g., '.png', '.jpg').
    """
    import imghdr

    kind: Optional[str] = imghdr.what(None, data)
    if kind == "jpeg":
        kind = "jpg"
    return f".{kind}" if kind else ".bin"


def _decode_base64_data(raw: str) -> bytes:
    compact = re.sub(r"\s+", "", raw)
    try:
        return base64.b64decode(compact, validate=True)
    except binascii.Error:
        return base64.b64decode(compact + "=" * (-len(compact) % 4))


def _looks_like_base64(raw: str) -> bool:
    compact = re.sub(r"\s+", "", raw)
    if len(compact) < 16 or len(compact) % 4 != 0:
        return False
    return bool(BASE64_TEXT_RE.fullmatch(compact))


def _save_blob_content(
    content: bytes | str,
    dest: str,
    media_type_hint: Optional[str] = None,
) -> str:
    media_type = media_type_hint
    data: bytes | str = content

    if isinstance(content, str):
        m = DATA_URL_RE.match(content.strip())
        if m:
            media_type = m.group("mime")
            data = _decode_base64_data(m.group("data"))
        elif (
            media_type
            and media_type.lower().startswith("image/")
            and _looks_like_base64(content)
        ):
            data = _decode_base64_data(content)

    base, ext = os.path.splitext(dest)

    write_type = "wb" if isinstance(data, bytes) else "w"
    if not ext:
        if media_type:
            ext = mimetypes.guess_extension(media_type.split(";")[0].lower()) or ""
            if ext == ".jpe":
                ext = ".jpg"
        if not ext and isinstance(data, bytes):
            ext = _determine_ext(data)
        dest = base + ext

    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    encoding = None if write_type == "wb" else "utf-8"
    newline = None if write_type == "wb" else ""
    with open(dest, write_type, encoding=encoding, newline=newline) as f:
        f.write(data)
    return dest


def _blob_media_type(cwms_module, office: str, blob_id: str) -> Optional[str]:
    try:
        result = cwms_module.get_blobs(office_id=office, blob_id_like=blob_id)
    except Exception:
        return None

    df = getattr(result, "df", result)
    if df is None or getattr(df, "empty", True):
        return None
    if "id" not in df.columns or "media-type-id" not in df.columns:
        return None

    matches = df[df["id"].astype(str).str.upper() == blob_id.upper()]
    if matches.empty:
        return None

    media_type = matches.iloc[0].get("media-type-id")
    return str(media_type) if media_type else None


def _join_api_url(api_root: str, path: str) -> str:
    return f"{api_root.rstrip('/')}/{path.lstrip('/')}"


def _resolve_optional_api_key(api_key: Optional[str], anonymous: bool) -> Optional[str]:
    if anonymous or not api_key:
        return None
    return get_api_key(api_key, None)


def _resolve_credential_kind(api_key: Optional[str], anonymous: bool) -> Optional[str]:
    if anonymous:
        return None
    from cwmscli.utils import get_saved_login_token

    if get_saved_login_token():
        return "token"
    if _resolve_optional_api_key(api_key, anonymous):
        return "api_key"
    return None


def _response_status_code(exc: BaseException) -> Optional[int]:
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None)


def store_blob(**kwargs):
    import cwms
    import requests

    file_data = kwargs.get("file_data")
    blob_id = kwargs.get("blob_id", "").upper()
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
    view_url = _join_api_url(
        kwargs.get("api_root"), f"blobs/{blob_id}?office={kwargs.get('office')}"
    )

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
                    "url": _join_api_url(kwargs.get("api_root"), "blobs"),
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
        logging.info(f"View: {view_url}")
    except requests.HTTPError as e:
        # Include response text when available
        detail = getattr(e.response, "text", "") or str(e)
        logging.error(f"Failed to store blob (HTTP): {detail}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Failed to store blob: {e}")
        sys.exit(1)


def retrieve_blob(**kwargs):
    import cwms
    import requests

    blob_id = kwargs.get("blob_id", "").upper()
    if not blob_id:
        logging.warning(
            "Valid blob_id required to download a blob. cwms-cli blob download --blob-id=myid. Run the list directive to see options for your office."
        )
        sys.exit(0)
    logging.debug(f"Office: {kwargs.get('office')}  Blob ID: {blob_id}")
    try:
        blob = cwms.get_blob(
            office_id=kwargs.get("office"),
            blob_id=blob_id,
        )
        logging.info(
            f"Successfully retrieved blob with ID: {blob_id}",
        )
        _save_blob_content(
            blob,
            dest=blob_id,
            media_type_hint=_blob_media_type(cwms, kwargs.get("office"), blob_id),
        )
        logging.info(f"Downloaded blob to: {blob_id}")
    except requests.HTTPError as e:
        detail = getattr(e.response, "text", "") or str(e)
        logging.error(f"Failed to retrieve blob (HTTP): {detail}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Failed to retrieve blob: {e}")
        sys.exit(1)


def delete_blob(**kwargs):
    import cwms
    import requests

    blob_id = kwargs.get("blob_id").upper()
    logging.debug(f"Office: {kwargs.get('office')}  Blob ID: {blob_id}")

    try:
        cwms.delete_blob(
            office_id=kwargs.get("office"),
            blob_id=kwargs.get("blob_id").upper(),
        )
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
):
    logging.info(f"Listing blobs for office: {office!r}...")
    import cwms
    import pandas as pd

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

    logging.info(f"Found {len(df):,} blob(s)")
    # List the blobs in the logger
    for _, row in df.iterrows():
        logging.info(f"Blob ID: {row['id']}, Description: {row.get('description')}")
    return df


def get_media_type(file_path: str) -> str:
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type or "application/octet-stream"


def _read_file_bytes(input_file: str) -> bytes:
    file_size = os.path.getsize(input_file)
    with open(input_file, "rb") as f:
        file_data = f.read()
    logging.info(f"Read file: {input_file} ({file_size} bytes)")
    return file_data


def _store_blob_payload(
    *,
    file_data: bytes,
    input_file: str,
    blob_id: str,
    description: str,
    media_type: str,
    overwrite: bool,
    office: str,
):
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
    return blob, params, blob_id_up


def _list_matching_files(
    input_dir: str, file_regex: str, recursive: bool
) -> list[Tuple[str, str]]:
    try:
        pattern = re.compile(file_regex)
    except re.error as e:
        raise ValueError(f"Invalid --file-regex: {e}") from e

    matches: list[Tuple[str, str]] = []
    for root, _, files in os.walk(input_dir):
        for name in files:
            full_path = os.path.join(root, name)
            rel_path = os.path.relpath(full_path, input_dir).replace(os.sep, "/")
            if pattern.search(rel_path):
                matches.append((full_path, rel_path))
        if not recursive:
            break
    matches.sort(key=lambda x: x[1].lower())
    return matches


def _blob_id_for_path(input_dir: str, rel_path: str, blob_id_prefix: str) -> str:
    rel_no_ext = os.path.splitext(rel_path)[0].replace("/", "_")
    return f"{blob_id_prefix}{rel_no_ext}".upper()


def _find_blob_id_collisions(
    matches: list[Tuple[str, str]], input_dir: str, blob_id_prefix: str
) -> dict[str, list[str]]:
    collisions: dict[str, list[str]] = defaultdict(list)
    for _, rel_path in matches:
        blob_id = _blob_id_for_path(
            input_dir=input_dir,
            rel_path=rel_path,
            blob_id_prefix=blob_id_prefix,
        )
        collisions[blob_id].append(rel_path)
    return {
        blob_id: rel_paths
        for blob_id, rel_paths in collisions.items()
        if len(rel_paths) > 1
    }


def upload_cmd(
    input_file: Optional[str],
    input_dir: Optional[str],
    file_regex: str,
    recursive: bool,
    blob_id: Optional[str],
    blob_id_prefix: str,
    description: str,
    media_type: str,
    overwrite: bool,
    dry_run: bool,
    office: str,
    api_root: str,
    api_key: str,
):
    import cwms
    import requests

    init_cwms_session(cwms, api_root=api_root, api_key=api_key)

    using_single = bool(input_file)
    using_multi = bool(input_dir)
    if using_single == using_multi:
        logging.error("Choose exactly one input source: --input-file or --input-dir.")
        sys.exit(2)

    uploads: list[Tuple[str, str]] = []
    if using_single:
        if not blob_id:
            logging.error("--blob-id is required when using --input-file.")
            sys.exit(2)
        uploads = [(input_file, blob_id)]
    else:
        try:
            matches = _list_matching_files(input_dir, file_regex, recursive)
        except ValueError as e:
            logging.error(str(e))
            sys.exit(2)
        if not matches:
            logging.error(
                f"No files in {input_dir!r} matched --file-regex {file_regex!r}."
            )
            sys.exit(1)
        collisions = _find_blob_id_collisions(matches, input_dir, blob_id_prefix)
        if collisions:
            for blob_id, rel_paths in collisions.items():
                logging.error(
                    "Generated blob ID collision for %s from files: %s",
                    blob_id,
                    ", ".join(rel_paths),
                )
            logging.error(
                "Bulk upload aborted. Adjust file names or use --blob-id-prefix to avoid duplicate generated blob IDs. Docs: %s#blob-bulk-collisions",
                BLOB_DOCS_URL,
            )
            sys.exit(2)
        uploads = [
            (
                full_path,
                _blob_id_for_path(
                    input_dir=input_dir,
                    rel_path=rel_path,
                    blob_id_prefix=blob_id_prefix,
                ),
            )
            for full_path, rel_path in matches
        ]
        logging.info(
            colors.c(
                f"Matched {len(uploads)} file(s) in {input_dir} with regex: {file_regex}",
                "cyan",
                bright=True,
            )
        )

    failures = 0
    for file_path, next_blob_id in uploads:
        try:
            file_data = _read_file_bytes(file_path)
            blob, params, blob_id_up = _store_blob_payload(
                file_data=file_data,
                input_file=file_path,
                blob_id=next_blob_id,
                description=description,
                media_type=media_type,
                overwrite=overwrite,
                office=office,
            )
            if dry_run:
                logging.info(
                    colors.c(
                        f"[DRY RUN] {file_path} -> {blob_id_up}",
                        "yellow",
                        bright=True,
                    )
                )
                logging.info(
                    json.dumps(
                        {
                            "url": _join_api_url(api_root, "blobs"),
                            "params": params,
                            "blob": {
                                **blob,
                                "value": f'<base64:{len(blob["value"])} chars>',
                            },
                        },
                        indent=2,
                    )
                )
                continue

            cwms.store_blobs(blob, fail_if_exists=not overwrite)
            view_url = _join_api_url(api_root, f"blobs/{blob_id_up}?office={office}")
            logging.info(
                colors.c(
                    f"[OK] Uploaded {file_path} as {blob_id_up}",
                    "green",
                    bright=True,
                )
            )
            logging.info(f"View: {view_url}")
        except requests.HTTPError as e:
            failures += 1
            detail = getattr(e.response, "text", "") or str(e)
            logging.error(
                colors.c(
                    f"[FAIL] {file_path} -> {next_blob_id.upper()} (HTTP): {detail}",
                    "red",
                    bright=True,
                )
            )
        except Exception as e:
            failures += 1
            logging.error(
                colors.c(
                    f"[FAIL] {file_path} -> {next_blob_id.upper()}: {e}",
                    "red",
                    bright=True,
                )
            )

    success_count = len(uploads) - failures
    if failures:
        logging.warning(
            colors.c(
                f"Upload completed with failures: {success_count}/{len(uploads)} succeeded, {failures} failed.",
                "yellow",
                bright=True,
            )
        )
        sys.exit(1)
    logging.info(
        colors.c(
            f"Upload completed successfully: {success_count}/{len(uploads)} file(s).",
            "green",
            bright=True,
        )
    )


def download_cmd(
    blob_id: str,
    dest: str,
    office: str,
    api_root: str,
    api_key: str,
    dry_run: bool,
    anonymous: bool = False,
):
    import cwms
    import requests

    if dry_run:
        logging.info(
            f"DRY RUN: would GET {api_root} blob with blob-id={blob_id} office={office}."
        )
        return
    credential_kind = _resolve_credential_kind(api_key, anonymous)
    init_cwms_session(cwms, api_root=api_root, api_key=api_key, anonymous=anonymous)
    bid = blob_id.upper()
    logging.debug(f"Office={office} BlobID={bid}")

    try:
        blob_content = cwms.get_blob(office_id=office, blob_id=bid)
        target = dest or bid
        _save_blob_content(
            blob_content,
            dest=target,
            media_type_hint=_blob_media_type(cwms, office, bid),
        )
        logging.info(f"Downloaded blob to: {target}")
    except requests.HTTPError as e:
        detail = getattr(e.response, "text", "") or str(e)
        logging.error(f"Failed to download (HTTP): {detail}")
        log_scoped_read_hint(
            credential_kind=credential_kind,
            anonymous=anonymous,
            office=office,
            action="download",
            resource="blob content",
        )
        sys.exit(1)
    except Exception as e:
        logging.error(f"Failed to download: {e}")
        log_scoped_read_hint(
            credential_kind=credential_kind,
            anonymous=anonymous,
            office=office,
            action="download",
            resource="blob content",
        )
        sys.exit(1)


def delete_cmd(blob_id: str, office: str, api_root: str, api_key: str, dry_run: bool):
    import cwms
    import requests

    if dry_run:
        logging.info(
            f"DRY RUN: would DELETE {api_root} blob with blob-id={blob_id} office={office}"
        )
        return
    init_cwms_session(cwms, api_root=api_root, api_key=api_key)
    try:
        cwms.delete_blob(office_id=office, blob_id=blob_id)
    except requests.HTTPError as e:
        if _response_status_code(e) == 404:
            logging.info(
                "Blob %s was already absent in office %s. Nothing to delete.",
                blob_id,
                office,
            )
            return
        raise
    logging.info(f"Deleted blob: {blob_id} for office: {office}")


def update_cmd(
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
    import cwms

    if dry_run:
        logging.info(
            f"DRY RUN: would PATCH {api_root} blob with blob-id={blob_id} office={office}"
        )
        return
    init_cwms_session(cwms, api_root=api_root, api_key=api_key)
    file_data = None
    if input_file:
        try:
            file_size = os.path.getsize(input_file)
            with open(input_file, "rb") as f:
                file_data = f.read()
            logging.info(f"Read file: {input_file} ({file_size} bytes)")
        except Exception as e:
            logging.error(f"Failed to read file: {e}")
            sys.exit(1)
    # Setup minimum required payload
    blob = {"office-id": office, "id": blob_id.upper()}
    if description:
        blob["description"] = description
    if media_type:
        blob["media-type-id"] = media_type
    else:
        logging.info("Media type not specified; Retrieving existing media type...")
        blob_metadata = cwms.get_blobs(office_id=office, blob_id_like=blob_id)
        blob["media-type-id"] = blob_metadata.df.get(
            "media-type-id", "application/octet-stream"
        )[0]
        logging.info(f"Using existing media type: {blob['media-type-id']}")

    if file_data:
        blob["value"] = base64.b64encode(file_data).decode("utf-8")
    cwms.update_blob(blob, fail_if_not_exists=not overwrite)


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
    anonymous: bool = False,
):
    import cwms
    import pandas as pd

    credential_kind = _resolve_credential_kind(api_key, anonymous)
    init_cwms_session(cwms, api_root=api_root, api_key=api_key, anonymous=anonymous)
    try:
        df = list_blobs(
            office=office,
            blob_id_like=blob_id_like,
            columns=columns,
            sort_by=sort_by,
            ascending=not desc,
            limit=limit,
        )
    except Exception:
        log_scoped_read_hint(
            credential_kind=credential_kind,
            anonymous=anonymous,
            office=office,
            action="list",
            resource="blob content",
        )
        raise
    if to_csv:
        df.to_csv(to_csv, index=False)
        logging.info(f"Wrote {len(df)} rows to {to_csv}")
    else:
        # Friendly console preview
        with pd.option_context("display.max_rows", 500, "display.max_columns", None):
            logging.info(df.to_string(index=False))
