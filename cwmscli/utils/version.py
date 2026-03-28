from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib import metadata
from pathlib import Path
from typing import Optional
from urllib import error, request

PYPI_JSON_URL = "https://pypi.org/pypi/cwms-cli/json"


@lru_cache(maxsize=1)
def get_cwms_cli_version() -> str:
    """Return installed cwms-cli version, with pyproject fallback for source runs."""
    try:
        return metadata.version("cwms-cli")
    except metadata.PackageNotFoundError:
        pass

    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if not pyproject.exists():
        return "unknown"

    text = pyproject.read_text(encoding="utf-8")

    # Prefer the [tool.poetry] version declaration.
    in_poetry_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_poetry_section = stripped == "[tool.poetry]"
            continue
        if in_poetry_section:
            m = re.match(r'^version\s*=\s*"([^"]+)"\s*$', stripped)
            if m:
                return m.group(1)

    return "unknown"


def _version_key(version: str) -> Optional[tuple[int, ...]]:
    match = re.fullmatch(r"\d+(?:\.\d+)*", version.strip())
    if not match:
        return None
    return tuple(int(part) for part in version.split("."))


def is_newer_version_available(current_version: str, latest_version: str) -> bool:
    current_key = _version_key(current_version)
    latest_key = _version_key(latest_version)
    if current_key is None or latest_key is None:
        return False
    return latest_key > current_key


def get_latest_cwms_cli_version(timeout: float = 1.0) -> Optional[str]:
    try:
        with request.urlopen(PYPI_JSON_URL, timeout=timeout) as response:
            payload = json.load(response)
    except (OSError, ValueError, error.URLError):
        return None

    version = payload.get("info", {}).get("version")
    if not isinstance(version, str) or not version.strip():
        return None
    return version.strip()
