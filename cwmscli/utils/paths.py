"""Per-user config directory resolution for cwms-cli.

Single source of truth so saved logins, named environments, and any future
per-user state all live under one root on every platform.
"""

import os
from pathlib import Path


def config_dir(*parts: str, create: bool = False) -> Path:
    """Return cwms-cli's per-user config dir, joined with *parts.

    Uses ``$XDG_CONFIG_HOME/cwms-cli`` when set, else ``~/.config/cwms-cli``,
    on all platforms so a user's tokens and environments share one root.
    Pass ``create=True`` to ensure the directory exists.
    """
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path("~/.config").expanduser()
    path = base.joinpath("cwms-cli", *parts)
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path
