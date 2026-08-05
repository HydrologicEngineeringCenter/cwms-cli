import importlib.metadata
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname


@dataclass(frozen=True)
class UpdateEnvironment:
    python_executable: str
    environment_prefix: str
    environment_type: str
    package_location: str
    editable_project_location: Optional[str] = None


def _absolute_path(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))


def _same_path(left: str, right: str) -> bool:
    return os.path.normcase(_absolute_path(left)) == os.path.normcase(
        _absolute_path(right)
    )


def _editable_project_location(
    distribution: importlib.metadata.Distribution,
) -> Optional[str]:
    direct_url_text = distribution.read_text("direct_url.json")
    if not direct_url_text:
        return None

    try:
        direct_url = json.loads(direct_url_text)
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(direct_url, dict):
        return None
    directory_info = direct_url.get("dir_info")
    if not isinstance(directory_info, dict) or not directory_info.get("editable"):
        return None

    url = direct_url.get("url")
    if not isinstance(url, str):
        return None
    parsed_url = urlparse(url)
    if parsed_url.scheme != "file":
        return None

    project_path = url2pathname(unquote(parsed_url.path))
    if parsed_url.netloc and parsed_url.netloc != "localhost":
        project_path = f"//{parsed_url.netloc}{project_path}"
    return _absolute_path(project_path)


def get_update_environment() -> UpdateEnvironment:
    """Describe the Python environment targeted by ``cwms-cli update``."""
    python_executable = _absolute_path(sys.executable)
    environment_prefix = _absolute_path(sys.prefix)
    conda_prefix = os.getenv("CONDA_PREFIX")

    if conda_prefix and _same_path(conda_prefix, sys.prefix):
        environment_type = "Conda environment"
    elif not _same_path(sys.prefix, sys.base_prefix):
        environment_type = "virtual environment"
    else:
        environment_type = "Python installation"

    try:
        distribution = importlib.metadata.distribution("cwms-cli")
        package_location = os.path.realpath(os.fspath(distribution.locate_file("")))
        editable_project_location = _editable_project_location(distribution)
    except importlib.metadata.PackageNotFoundError:
        # This can happen when the CLI is invoked directly from a source checkout.
        package_location = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        editable_project_location = None

    return UpdateEnvironment(
        python_executable=python_executable,
        environment_prefix=environment_prefix,
        environment_type=environment_type,
        package_location=package_location,
        editable_project_location=editable_project_location,
    )


def build_update_package_spec(target_version: Optional[str]) -> str:
    if target_version:
        return f"cwms-cli=={target_version}"
    return "cwms-cli"


def looks_like_missing_version(pip_output: str, package_spec: str) -> bool:
    return (
        "No matching distribution found for" in pip_output
        or "Could not find a version that satisfies the requirement" in pip_output
    ) and package_spec in pip_output


def write_windows_update_script(cmd: List[str]) -> str:
    quoted_cmd = subprocess.list2cmdline(cmd)
    script = "\r\n".join(
        [
            "@echo off",
            "setlocal",
            "echo Waiting for cwms-cli to exit before updating...",
            "timeout /t 1 /nobreak >nul",
            quoted_cmd,
            'set "EXIT_CODE=%ERRORLEVEL%"',
            'if "%EXIT_CODE%"=="0" (',
            "  echo Update complete. Run cwms-cli --version to verify.",
            ") else (",
            "  echo.",
            "  echo cwms-cli update failed. Review pip output above.",
            ")",
            "echo.",
            "echo Press any key to close this window.",
            "pause >nul",
            '(goto) 2>nul & del "%~f0"',
            "exit /b %EXIT_CODE%",
            "",
        ]
    )
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".cmd",
        delete=False,
        encoding="utf-8",
        newline="",
    ) as fh:
        fh.write(script)
        return fh.name


def launch_windows_update(cmd: List[str]) -> str:
    script_path = write_windows_update_script(cmd)
    creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    subprocess.Popen(
        ["cmd.exe", "/c", script_path],
        creationflags=creationflags,
    )
    return script_path
