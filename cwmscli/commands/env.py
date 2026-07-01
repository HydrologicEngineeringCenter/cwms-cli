import os
import shutil
import subprocess
import sys
import time
from typing import Dict, Optional

import click

from cwmscli.utils.env_store import (
    ENV_DEFAULTS,
    EnvStoreError,
    delete_env,
    env_exists_on_disk,
    list_envs,
    load_env,
    save_env,
)

SENSITIVE_KEYS = {"CDA_API_KEY"}


def _stdout_is_tty() -> bool:
    """Indirection so tests can override TTY detection."""
    return sys.stdout.isatty()


def _check_env(env_config: Dict[str, str]) -> Dict:
    import requests

    api_root = env_config.get("CDA_API_ROOT", "").rstrip("/")
    if not api_root:
        return {
            "reachable": False,
            "latency_ms": None,
            "auth": "skipped",
            "error": "no API root",
        }

    url = f"{api_root}/offices"
    try:
        t0 = time.monotonic()
        resp = requests.get(url, timeout=5)
        latency_ms = int((time.monotonic() - t0) * 1000)
    except requests.RequestException as e:
        return {
            "reachable": False,
            "latency_ms": None,
            "auth": "skipped",
            "error": str(e),
        }

    if resp.status_code >= 400:
        return {
            "reachable": False,
            "latency_ms": latency_ms,
            "auth": "skipped",
            "error": f"HTTP {resp.status_code}",
        }

    api_key = env_config.get("CDA_API_KEY")
    if not api_key:
        return {
            "reachable": True,
            "latency_ms": latency_ms,
            "auth": "skipped",
            "error": None,
        }

    try:
        auth_resp = requests.get(url, headers={"Authorization": api_key}, timeout=5)
    except requests.RequestException:
        return {
            "reachable": True,
            "latency_ms": latency_ms,
            "auth": "failed",
            "error": None,
        }

    if auth_resp.status_code == 401:
        return {
            "reachable": True,
            "latency_ms": latency_ms,
            "auth": "failed",
            "error": None,
        }

    return {"reachable": True, "latency_ms": latency_ms, "auth": "ok", "error": None}


@click.group("env", help="Manage CDA environments and API keys")
def env_group():
    """Environment management commands for cwms-cli."""
    pass


@env_group.command("setup", help="Create or update an environment configuration")
@click.argument("env_name")
@click.option(
    "--api-root",
    help="CDA API root URL (e.g., https://example.mil/cwms-data)",
)
@click.option(
    "--api-key",
    help="API key for authentication",
)
@click.option(
    "--office",
    help="Default office code (e.g., SWT)",
)
def setup_cmd(
    env_name: str,
    api_root: Optional[str],
    api_key: Optional[str],
    office: Optional[str],
):
    """
    Create or update environment configuration.

    ENV_NAME can be: cwbi-dev, cwbi-test, cwbi-prod, onsite, localhost, or custom
    """
    existing = load_env(env_name) or {}
    env_vars = dict(existing)
    env_vars["ENVIRONMENT"] = env_name

    if api_root:
        env_vars["CDA_API_ROOT"] = api_root
    elif "CDA_API_ROOT" not in env_vars and env_name in ENV_DEFAULTS:
        env_vars["CDA_API_ROOT"] = ENV_DEFAULTS[env_name]["CDA_API_ROOT"]

    if api_key:
        env_vars["CDA_API_KEY"] = api_key

    if office:
        env_vars["OFFICE"] = office.upper()

    if "CDA_API_ROOT" not in env_vars:
        click.echo(
            f"Error: --api-root is required for '{env_name}' (not a default environment)",
            err=True,
        )
        click.echo(f"Available defaults: {', '.join(ENV_DEFAULTS.keys())}", err=True)
        sys.exit(1)

    try:
        path = save_env(env_name, env_vars)
    except EnvStoreError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    click.echo(f"Environment '{env_name}' saved to {path}")


@env_group.command("show", help="Show current environment and available configurations")
@click.option(
    "--check",
    is_flag=True,
    default=False,
    help="Test connectivity and authentication for each environment.",
)
def show_cmd(check: bool):
    """
    Display current environment and list all configured environments.

    Lists all environments with API root, office, and key status.
    Use --check to test connectivity and API key validity (requires network).
    """
    current_env = os.environ.get("ENVIRONMENT")

    if current_env:
        click.echo(
            f"Current environment: {click.style(current_env, fg='green', bold=True)}\n"
        )
    else:
        click.echo("No environment currently active\n")

    names = list_envs()
    if not names:
        click.echo("No environments configured")
        click.echo("Run 'cwms-cli env setup <name>' to create one")
        return

    click.echo("Available environments:")
    for env_name in names:
        env_config = load_env(env_name)
        if not env_config:
            continue
        marker = "* " if env_name == current_env else "  "
        builtin = " (built-in)" if not env_exists_on_disk(env_name) else ""
        api_root = env_config.get("CDA_API_ROOT", "not set")
        office = env_config.get("OFFICE", "not set")
        has_key = "has API key" if env_config.get("CDA_API_KEY") else "no API key"

        click.echo(f"{marker}{env_name}{builtin}")
        click.echo(f"    API Root: {api_root}")
        click.echo(f"    Office:   {office}")
        click.echo(f"    Status:   {has_key}")

        if check:
            result = _check_env(env_config)
            if result["reachable"]:
                latency = f" ({result['latency_ms']}ms)"
                reach_str = click.style("reachable", fg="green") + latency
            else:
                err = f" — {result['error']}" if result["error"] else ""
                reach_str = click.style("unreachable", fg="red") + err

            auth_str = ""
            if result["auth"] == "ok":
                auth_str = click.style("authenticated", fg="green")
            elif result["auth"] == "failed":
                auth_str = click.style("auth failed", fg="red")

            click.echo(f"    Connect:  {reach_str}")
            if auth_str:
                click.echo(f"    Auth:     {auth_str}")


@env_group.command("delete", help="Delete an environment configuration")
@click.argument("env_name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def delete_cmd(env_name: str, yes: bool):
    """
    Delete an environment configuration.

    Examples:
        cwms-cli env delete myenv
        cwms-cli env delete myenv --yes
    """
    if not yes and not click.confirm(f"Delete environment '{env_name}'?"):
        click.echo("Cancelled")
        return

    try:
        existed = delete_env(env_name)
    except EnvStoreError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if existed:
        click.echo(f"Environment '{env_name}' deleted")
    else:
        click.echo(f"Environment '{env_name}' not found", err=True)
        sys.exit(1)


def _detect_shell() -> str:
    """Best-effort detection of the user's interactive shell."""
    if sys.platform == "win32":
        # PowerShell sets PSModulePath; prefer pwsh/powershell when present.
        if os.environ.get("PSModulePath"):
            for candidate in ("pwsh", "powershell"):
                found = shutil.which(candidate)
                if found:
                    return found
        return os.environ.get("COMSPEC", "cmd.exe")

    return os.environ.get("SHELL", "/bin/bash")


def _detect_shell_kind() -> str:
    """Map the detected shell path to a known kind, defaulting to 'bash'."""
    path = _detect_shell().lower()
    base = os.path.basename(path)
    if "pwsh" in base or "powershell" in base:
        return "powershell"
    if "cmd" in base:
        return "cmd"
    if "fish" in base:
        return "fish"
    if "zsh" in base:
        return "zsh"
    if "bash" in base or "sh" in base:
        return "bash"
    return "bash"


def _export_help_lines(env_name: str) -> str:
    """Per-shell instructions for loading an env into the current shell."""
    recipes = {
        "bash": f'eval "$(cwms-cli env export {env_name} --format bash)"',
        "zsh": f'eval "$(cwms-cli env export {env_name} --format bash)"',
        "powershell": (
            f"cwms-cli env export {env_name} --format powershell "
            "| Out-String | Invoke-Expression"
        ),
        "cmd": (
            f"cwms-cli env export {env_name} --format cmd "
            f"--output %TEMP%\\cwms-env.cmd && call %TEMP%\\cwms-env.cmd"
        ),
        "fish": f"cwms-cli env export {env_name} --format fish | source",
    }
    detected = _detect_shell_kind()
    primary = recipes.get(detected, recipes["bash"])

    lines = [
        f"To load '{env_name}' into your current shell ({detected} detected):",
        f"  {primary}",
        "",
        "For other shells:",
    ]
    label_width = max(len(k) for k in recipes)
    for kind, recipe in recipes.items():
        if kind == detected:
            continue
        lines.append(f"  {kind.ljust(label_width)}  {recipe}")
    lines.extend(
        [
            "",
            f"Write a .env file:  cwms-cli env export {env_name} --output .env",
            "Print to terminal anyway: --show-key",
        ]
    )
    return "\n".join(lines)


def spawn_shell_with_env(env_vars: Dict[str, str], env_name: str):
    """Spawn a new shell with environment variables set."""
    user_shell = _detect_shell()
    new_env = os.environ.copy()
    new_env.update(env_vars)

    click.echo(
        f"Activating environment: {click.style(env_name, fg='green', bold=True)}",
        err=True,
    )
    click.echo(f"Shell: {user_shell}", err=True)
    click.echo(
        "Type 'exit' or press Ctrl+D to return to your original environment\n",
        err=True,
    )

    try:
        result = subprocess.run([user_shell], env=new_env)
        sys.exit(result.returncode)
    except OSError as e:
        click.echo(f"Error spawning shell: {e}", err=True)
        sys.exit(1)


@env_group.command("activate", help="Activate an environment in a new shell")
@click.argument("env_name")
def activate_cmd(env_name: str):
    """
    Activate an environment in a new shell session.

    The environment variables will be set in the new shell and persist
    until you exit the shell. Type 'exit' to return to your original environment.

    Note: This spawns a child shell. Your parent shell, and any IDE
    already open, will not see these variables. To populate the current
    shell, use:  eval "$(cwms-cli env export <name> --format bash)"

    Examples:
        cwms-cli env activate cwbi-prod
        cwms-cli env activate localhost
    """
    env_vars = load_env(env_name)
    if not env_vars:
        click.echo(f"Error: Environment '{env_name}' not found", err=True)
        click.echo(f"Run 'cwms-cli env setup {env_name}' to create it", err=True)
        sys.exit(1)

    spawn_shell_with_env(env_vars, env_name)


def _quote_dotenv(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _quote_bash(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def _quote_powershell(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _quote_cmd(value: str) -> str:
    # set "K=V" handles spaces and most special chars. Escape embedded " and %.
    return value.replace("%", "%%").replace('"', '""')


def _quote_fish(value: str) -> str:
    # Fish single-quoted strings: backslash escapes \ and '.
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _format_env(env_vars: Dict[str, str], fmt: str) -> str:
    items = sorted(env_vars.items())
    lines = []
    for key, value in items:
        value = str(value)
        if fmt == "dotenv":
            lines.append(f"{key}={_quote_dotenv(value)}")
        elif fmt == "bash":
            lines.append(f"export {key}={_quote_bash(value)}")
        elif fmt == "powershell":
            lines.append(f"$env:{key} = {_quote_powershell(value)}")
        elif fmt == "cmd":
            # @ prefix suppresses cmd's default echoing of each line when run via `call`.
            lines.append(f'@set "{key}={_quote_cmd(value)}"')
        elif fmt == "fish":
            lines.append(f"set -gx {key} {_quote_fish(value)}")
        else:
            raise ValueError(f"Unknown format: {fmt}")
    return "\n".join(lines)


@env_group.command(
    "export",
    help="Export an environment's variables to your current shell or a .env file",
)
@click.argument("env_name")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["dotenv", "bash", "powershell", "cmd", "fish"]),
    default="dotenv",
    show_default=True,
    help="Output syntax. Match this to your shell, or use 'dotenv' for a .env file.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False, writable=True, resolve_path=True),
    default=None,
    help="Write to FILE (mode 0600) instead of standard output.",
)
@click.option(
    "--no-key",
    is_flag=True,
    default=False,
    help="Omit CDA_API_KEY (useful for sharing templates).",
)
@click.option(
    "--show-key",
    is_flag=True,
    default=False,
    help="Allow the API key to be displayed in your terminal.",
)
def export_cmd(
    env_name: str,
    fmt: str,
    output: Optional[str],
    no_key: bool,
    show_key: bool,
):
    """
    Export a stored environment so your current shell, IDE, or another tool
    can use its variables.

    A child process cannot directly modify its parent shell, so this command
    emits values that you (or your shell) load. Three common ways:

    \b
        # Load into the current bash/zsh shell
        eval "$(cwms-cli env export cwbi-prod --format bash)"

        # Load into the current PowerShell session
        cwms-cli env export cwbi-prod --format powershell | Out-String | Invoke-Expression

        # Write a .env file for an IDE, docker-compose, or direnv to read
        cwms-cli env export cwbi-prod --output .env

    Run with no flags in an interactive terminal to see the right recipe
    for your detected shell. The API key is never displayed in a terminal
    unless you pass --show-key.
    """
    env_vars = load_env(env_name)
    if env_vars is None:
        click.echo(f"Error: Environment '{env_name}' not found", err=True)
        sys.exit(1)

    if no_key:
        env_vars = {k: v for k, v in env_vars.items() if k not in SENSITIVE_KEYS}

    has_key = any(k in env_vars for k in SENSITIVE_KEYS)
    writing_to_file = output is not None

    if has_key and not writing_to_file and _stdout_is_tty() and not show_key:
        click.echo(_export_help_lines(env_name), err=True)
        sys.exit(1)

    rendered = _format_env(env_vars, fmt)

    if writing_to_file:
        path = output
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        if sys.platform == "win32":
            fd = os.open(path, flags)
        else:
            fd = os.open(path, flags, 0o600)
        try:
            with os.fdopen(fd, "w") as f:
                f.write(rendered + "\n")
            if sys.platform != "win32":
                os.chmod(path, 0o600)
        except OSError as e:
            click.echo(f"Error writing {path}: {e}", err=True)
            sys.exit(1)
        click.echo(f"Wrote {path} (0600)", err=True)
        if path.endswith(".env") or os.path.basename(path).startswith(".env"):
            click.echo("Reminder: add this file to .gitignore.", err=True)
        return

    click.echo(rendered)
