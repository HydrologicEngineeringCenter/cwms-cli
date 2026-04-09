import subprocess
import tempfile
from typing import List, Optional


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
