import os
import sys
from pathlib import Path
from typing import Dict, Optional

import click

from cwmscli.utils.credentials import (
    CredentialStorageError,
    add_to_environment_index,
    delete_environment,
    get_environment,
    get_environment_from_os_environ,
    get_environment_index,
    is_keyring_available,
    remove_from_environment_index,
    store_environment,
)


def get_envs_dir() -> Path:
    """Get the directory where environment files are stored."""
    if sys.platform == "win32":
        base_dir = Path(os.environ.get("APPDATA", "~/.config")).expanduser()
    else:
        base_dir = Path("~/.config").expanduser()

    envs_dir = base_dir / "cwms-cli" / "envs"
    return envs_dir


ENV_DEFAULTS = {
    "cwbi-prod": "https://cwms-data.usace.army.mil/cwms-data",
}


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
    # Get existing config from keyring, if any
    existing_vars = get_environment(env_name) or {}

    env_vars = existing_vars.copy()
    env_vars["ENVIRONMENT"] = env_name

    if api_root:
        env_vars["CDA_API_ROOT"] = api_root
    elif "CDA_API_ROOT" not in env_vars and env_name in ENV_DEFAULTS:
        env_vars["CDA_API_ROOT"] = ENV_DEFAULTS[env_name]

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

    # Store in keyring
    try:
        store_environment(env_name, env_vars)
        add_to_environment_index(env_name)
        click.echo(f"Environment '{env_name}' configured securely in system keyring")
    except CredentialStorageError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@env_group.command("show", help="Show current environment and available configurations")
def show_cmd():
    """
    Display current environment and list all configured environments.

    Lists all environments with API root, office, and key status.
    """
    current_env = os.environ.get("ENVIRONMENT")

    # List all environments
    if current_env:
        click.echo(
            f"Current environment: {click.style(current_env, fg='green', bold=True)}\n"
        )
    else:
        click.echo("No environment currently active\n")

    environments = get_environment_index()

    if environments:
        click.echo("Available environments:")
        for env_name in environments:
            env_config = get_environment(env_name)
            if env_config:
                is_active = env_name == current_env
                marker = "* " if is_active else "  "

                api_root = env_config.get("CDA_API_ROOT", "not set")
                office = env_config.get("OFFICE", "not set")
                has_key = (
                    "has API key" if env_config.get("CDA_API_KEY") else "no API key"
                )

                click.echo(f"{marker}{env_name}")
                click.echo(f"    API Root: {api_root}")
                click.echo(f"    Office: {office}")
                click.echo(f"    Status: {has_key}")
    else:
        click.echo("No environments configured")
        click.echo("Run 'cwms-cli env setup <name>' to create one")

    # Check for old .env files (for migration purposes)
    envs_dir = get_envs_dir()
    env_files = []
    if envs_dir.exists():
        env_files = sorted(envs_dir.glob("*.env"))

    if env_files:
        click.echo("\nOld .env files found (not migrated to keyring):")
        for env_file in env_files:
            env_name = env_file.stem
            click.echo(f"  - {env_name}")


@env_group.command("delete", help="Delete an environment configuration")
@click.argument("env_name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def delete_cmd(env_name: str, yes: bool):
    """
    Delete an environment configuration from keyring.

    Examples:
        cwms-cli env delete myenv
        cwms-cli env delete myenv --yes
    """
    if not yes:
        if not click.confirm(f"Delete environment '{env_name}'?"):
            click.echo("Cancelled")
            return

    try:
        delete_environment(env_name)
        remove_from_environment_index(env_name)
        click.echo(f"Environment '{env_name}' deleted")
    except CredentialStorageError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def spawn_shell_with_env(env_vars: Dict[str, str], env_name: str):
    """Spawn a new shell with environment variables set."""
    import subprocess

    # Detect user's shell
    user_shell = os.environ.get("SHELL")
    if not user_shell:
        if sys.platform == "win32":
            user_shell = os.environ.get("COMSPEC", "cmd.exe")
        else:
            user_shell = "/bin/bash"

    # Create environment dict
    new_env = os.environ.copy()
    new_env.update(env_vars)

    # Show activation message
    click.echo(
        f"Activating environment: {click.style(env_name, fg='green', bold=True)}"
    )
    click.echo(f"Shell: {user_shell}")
    click.echo("Type 'exit' or press Ctrl+D to return to your original environment\n")

    # Spawn shell with modified environment
    try:
        result = subprocess.run([user_shell], env=new_env)
        sys.exit(result.returncode)
    except Exception as e:
        click.echo(f"Error spawning shell: {e}", err=True)
        sys.exit(1)


@env_group.command("activate", help="Activate an environment in a new shell")
@click.argument("env_name")
def activate_cmd(env_name: str):
    """
    Activate an environment in a new shell session.

    The environment variables will be set in the new shell and persist
    until you exit the shell. Type 'exit' to return to your original environment.

    Examples:
        cwms-cli env activate cwbi-prod
        cwms-cli env activate localhost
    """
    # Try to get environment from keyring
    env_vars = get_environment(env_name)

    if not env_vars:
        # If not in keyring and keyring not available, try OS environment as fallback
        if not is_keyring_available():
            fallback_vars = get_environment_from_os_environ()
            if fallback_vars:
                click.echo(
                    f"Using environment variables from current shell (keyring not available)",
                    err=True,
                )
                env_vars = fallback_vars
                env_vars["ENVIRONMENT"] = env_name
            else:
                click.echo(
                    "Error: Keyring not available and no environment variables found.",
                    err=True,
                )
                click.echo(
                    "Set CDA_API_ROOT, CDA_API_KEY, and OFFICE in your environment,",
                    err=True,
                )
                click.echo(
                    "or run 'cwms-cli env setup <name>' on a system with keyring support.",
                    err=True,
                )
                sys.exit(1)
        else:
            click.echo(
                f"Error: Environment '{env_name}' not found in keyring",
                err=True,
            )
            click.echo(
                "Run 'cwms-cli env show --name <env>' to see if it exists",
                err=True,
            )
            click.echo(f"Or run 'cwms-cli env setup {env_name}' to create it", err=True)
            sys.exit(1)

    # Always spawn a new shell
    spawn_shell_with_env(env_vars, env_name)
