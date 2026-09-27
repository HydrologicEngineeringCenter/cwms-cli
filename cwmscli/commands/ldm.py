"""Click command implementations for the CWBI Local Data Manager API."""

import json
import logging
import mimetypes
import os
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

import requests


def _url(api_root: str, path: str) -> str:
    return f"{api_root.rstrip('/')}/{path.lstrip('/')}"


def _headers(api_key: Optional[str]) -> dict[str, str]:
    return (
        {"Accept": "application/json", "key": api_key}
        if api_key
        else {"Accept": "application/json"}
    )


def _request(
    method: str,
    api_root: str,
    path: str,
    api_key: Optional[str],
    **kwargs: Any,
) -> requests.Response:
    response = requests.request(
        method,
        _url(api_root, path),
        headers={**_headers(api_key), **kwargs.pop("headers", {})},
        timeout=kwargs.pop("timeout", 30),
        **kwargs,
    )
    response.raise_for_status()
    return response


def _emit(response: requests.Response) -> None:
    if not response.content:
        return
    try:
        print(json.dumps(response.json(), indent=2, default=str))
    except ValueError:
        print(response.text)


def _load_json(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as stream:
            payload = json.load(stream)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read JSON payload {path!r}: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError("The JSON payload must be an object.")
    return payload


def list_products(api_root: str, api_key: Optional[str]) -> None:
    _emit(_request("GET", api_root, "products", api_key))


def get_product(api_root: str, api_key: Optional[str], product_slug: str) -> None:
    _emit(
        _request("GET", api_root, f"products/{quote(product_slug, safe='')}", api_key)
    )


def create_product(api_root: str, api_key: Optional[str], input_json: str) -> None:
    _emit(_request("POST", api_root, "products", api_key, json=_load_json(input_json)))


def update_product(
    api_root: str, api_key: Optional[str], product_slug: str, input_json: str
) -> None:
    _emit(
        _request(
            "PUT",
            api_root,
            f"products/{quote(product_slug, safe='')}",
            api_key,
            json=_load_json(input_json),
        )
    )


def list_product_files(
    api_root: str,
    api_key: Optional[str],
    product_slug: Optional[str],
    start: Optional[str],
    end: Optional[str],
) -> None:
    params = {
        key: value for key, value in {"start": start, "end": end}.items() if value
    }
    path = (
        f"products/{quote(product_slug, safe='')}/files"
        if product_slug
        else "productfiles"
    )
    _emit(_request("GET", api_root, path, api_key, params=params))


def upload_product_file(
    api_root: str,
    api_key: Optional[str],
    product_slug: str,
    input_file: str,
) -> None:
    path = Path(input_file)
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    with path.open("rb") as stream:
        response = _request(
            "POST",
            api_root,
            "productfiles",
            api_key,
            files={"files": (path.name, stream, content_type)},
            data={"product_slug": product_slug},
        )
    _emit(response)


def download_product_file(
    api_root: str,
    api_key: Optional[str],
    file_key: str,
    destination: Optional[str],
) -> None:
    response = _request(
        "GET",
        api_root,
        f"ldm/{file_key.lstrip('/')}",
        api_key,
        headers={"Accept": "*/*"},
    )
    target = destination or os.path.basename(file_key)
    with open(target, "wb") as stream:
        stream.write(response.content)
    logging.info("Downloaded product file to %s", target)
