"""File-based storage for named CDA environments.

One JSON file per environment under the user's config dir, mode 0600 on
POSIX (current-user-only ACL on Windows). Same threat model as
~/.aws/credentials, ~/.config/gh, ~/.kube/config: the user account is
the security boundary.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

from cwmscli.utils.paths import config_dir

ENV_DEFAULTS = {
    "prod": {
        "ENVIRONMENT": "prod",
        "CDA_API_ROOT": "https://cwms-data.usace.army.mil/cwms-data",
    },
}


class EnvStoreError(Exception):
    """Raised when an env file cannot be read, written, or deleted."""


def envs_dir() -> Path:
    """Return the directory where env files live, creating it if needed."""
    return config_dir("envs", create=True)


def _env_path(name: str) -> Path:
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        raise EnvStoreError(f"Invalid environment name: {name!r}")
    return envs_dir() / f"{name}.json"


def _restrict_windows_acl(path: Path) -> None:
    """Restrict a file to the current user on Windows via icacls.

    No-op on non-Windows. Failures are swallowed: the file already exists
    in the user's APPDATA, and surfacing icacls errors hurts more than
    it helps.
    """
    if sys.platform != "win32":
        return
    import subprocess

    user = os.environ.get("USERNAME")
    if not user:
        return
    try:
        subprocess.run(
            ["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:F"],
            check=False,
            capture_output=True,
        )
    except (OSError, FileNotFoundError):
        pass


def save_env(name: str, config: Dict[str, str]) -> Path:
    """Write a config dict to <envs_dir>/<name>.json with 0600 perms.

    Uses os.open with O_CREAT|O_TRUNC|O_WRONLY and explicit mode so the
    file is never briefly world-readable between create and chmod.
    """
    path = _env_path(name)
    payload = json.dumps(config, indent=2, sort_keys=True) + "\n"

    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if sys.platform == "win32":
        # Windows ignores the mode arg; ACL is set after the write.
        fd = os.open(path, flags)
    else:
        fd = os.open(path, flags, 0o600)

    try:
        with os.fdopen(fd, "w") as f:
            f.write(payload)
    except OSError as e:
        raise EnvStoreError(f"Failed to write env file {path}: {e}") from e

    if sys.platform != "win32":
        # Re-chmod in case the file already existed with different perms.
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    else:
        _restrict_windows_acl(path)

    return path


def env_exists_on_disk(name: str) -> bool:
    """Return True if a user-created env file exists for *name*."""
    return _env_path(name).exists()


def load_env(name: str) -> Optional[Dict[str, str]]:
    """Read and parse an env file, falling back to built-in defaults."""
    path = _env_path(name)
    if not path.exists():
        return dict(ENV_DEFAULTS[name]) if name in ENV_DEFAULTS else None
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def delete_env(name: str) -> bool:
    """Remove an env file. Returns True if it existed."""
    path = _env_path(name)
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError as e:
        raise EnvStoreError(f"Failed to delete env file {path}: {e}") from e


def list_envs() -> List[str]:
    """Return sorted env names, including built-in defaults."""
    on_disk = {p.stem for p in envs_dir().glob("*.json")}
    return sorted(on_disk | ENV_DEFAULTS.keys())
