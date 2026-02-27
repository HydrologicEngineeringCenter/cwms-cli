from __future__ import annotations

import re
from functools import lru_cache
from importlib import metadata
from pathlib import Path


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
