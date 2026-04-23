import logging
import os
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

import click


def get_envs_dir() -> Path:
    """Get the directory where environment files are stored."""
    if sys.platform == "win32":
        base_dir = Path(os.environ.get("APPDATA", "~/.config")).expanduser()
    else:
        base_dir = Path("~/.config").expanduser()

    envs_dir = base_dir / "cwms-cli" / "envs"
    return envs_dir


def read_env_file(env_file: Path) -> Dict[str, str]:
    """Read a .env file and return a dictionary of key-value pairs."""
    env_vars = {}
    if not env_file.exists():
        return env_vars

    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()

    return env_vars


def write_env_file(env_file: Path, env_vars: Dict[str, str]) -> None:
    """Write environment variables to a .env file."""
    env_file.parent.mkdir(parents=True, exist_ok=True)

    with open(env_file, "w") as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")

    if sys.platform != "win32":
        os.chmod(env_file, 0o600)


ENV_DEFAULTS = {
    "cwbi-prod": "https://cwms-data.usace.army.mil/cwms-data",
    "localhost": "http://localhost:8082/cwms-data",
}


def detect_shell() -> Tuple[str, Optional[Path]]:
    """Detect user's shell and return (shell_name, rc_file_path)."""
    shell = os.environ.get("SHELL", "")
    home = Path.home()

    if "zsh" in shell:
        return ("zsh", home / ".zshrc")
    elif "bash" in shell:
        return ("bash", home / ".bashrc")

    return ("unknown", None)


def is_function_installed(rc_file: Path) -> bool:
    """Check if cwms-env function is already installed in rc file."""
    if not rc_file.exists():
        return False

    content = rc_file.read_text()
    return "# cwms-cli environment switcher" in content


def install_posix_function(rc_file: Path) -> None:
    """Append cwms-env function to shell rc file."""
    function_block = """
# cwms-cli environment switcher (added by cwms-cli)
cwms-env() { eval $(cwms-cli --quiet env activate "$@"); }
"""

    with open(rc_file, "a") as f:
        f.write(function_block)


def get_windows_batch_dir() -> Path:
    """Get directory for Windows batch files."""
    # Try %USERPROFILE%\bin first, fallback to config dir
    user_bin = Path.home() / "bin"
    if user_bin.exists():
        return user_bin

    # Use cwms-cli config directory
    appdata = Path(os.environ.get("APPDATA", "~/.config")).expanduser()
    return appdata / "cwms-cli" / "bin"


def install_windows_batch(batch_dir: Path) -> Path:
    """Create cwms-env.bat batch file."""
    batch_dir.mkdir(parents=True, exist_ok=True)
    batch_file = batch_dir / "cwms-env.bat"

    batch_content = """@echo off
for /f "delims=" %%i in ('cwms-cli --quiet env activate %*') do %%i
"""

    batch_file.write_text(batch_content)
    return batch_file


def is_in_path(directory: Path) -> bool:
    """Check if directory is in PATH."""
    path_env = os.environ.get("PATH", "")
    path_dirs = path_env.split(os.pathsep)
    dir_str = str(directory.resolve())

    return any(str(Path(p).resolve()) == dir_str for p in path_dirs)


def add_to_user_path_windows(directory: Path) -> bool:
    """Add directory to Windows user PATH via registry."""
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Environment",
            0,
            winreg.KEY_READ | winreg.KEY_WRITE,
        )

        try:
            current_path, _ = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current_path = ""

        dir_str = str(directory)
        if dir_str not in current_path.split(os.pathsep):
            new_path = (
                f"{current_path}{os.pathsep}{dir_str}" if current_path else dir_str
            )
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)

        winreg.CloseKey(key)
        return True

    except Exception:
        return False


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
    envs_dir = get_envs_dir()
    env_file = envs_dir / f"{env_name}.env"

    existing_vars = read_env_file(env_file) if env_file.exists() else {}

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

    write_env_file(env_file, env_vars)

    logging.info(f"Environment '{env_name}' configured at: {env_file}")
    if api_key:
        logging.info("API key stored securely (file permissions set to 600)")


@env_group.command("show", help="Show current environment and available configurations")
def show_cmd():
    """Display current environment and list all configured environments."""
    current_env = os.environ.get("ENVIRONMENT")

    if current_env:
        click.echo(f"Current environment: {click.style(current_env, fg='green')}")
    else:
        click.echo("No environment currently active")

    envs_dir = get_envs_dir()
    if not envs_dir.exists():
        click.echo(f"\nNo environments configured yet. Directory: {envs_dir}")
        click.echo("Run 'cwms-cli env setup <name>' to create one.")
        return

    env_files = sorted(envs_dir.glob("*.env"))

    if not env_files:
        click.echo(f"\nNo environments found in: {envs_dir}")
        click.echo("Run 'cwms-cli env setup <name>' to create one.")
        return

    click.echo(f"\nAvailable environments in {envs_dir}:")
    for env_file in env_files:
        env_name = env_file.stem
        is_current = env_name == current_env
        marker = " (active)" if is_current else ""
        click.echo(f"  - {env_name}{marker}")

    if current_env:
        current_file = envs_dir / f"{current_env}.env"
        if current_file.exists():
            click.echo(f"\nCurrent environment values:")
            env_vars = read_env_file(current_file)
            for key, value in sorted(env_vars.items()):
                if "KEY" in key.upper() and value:
                    display_value = value[:8] + "..." if len(value) > 8 else "***"
                else:
                    display_value = value
                click.echo(f"  {key}={display_value}")


@env_group.command("install", help="Install cwms-env shell helper")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def install_cmd(yes: bool):
    """
    Install shell helper for activating environments.

    On Linux/Mac: Adds cwms-env() function to shell rc file
    On Windows: Creates cwms-env.bat and adds to PATH
    """

    if sys.platform == "win32":
        # Windows: Install batch file
        batch_dir = get_windows_batch_dir()
        batch_file = batch_dir / "cwms-env.bat"

        if batch_file.exists():
            click.echo(f"✓ Already installed: {batch_file}")
            return

        click.echo(f"Will create: {batch_file}")
        if not is_in_path(batch_dir):
            click.echo(f"Will add to PATH: {batch_dir}")

        if not yes and not click.confirm("Continue?"):
            click.echo("Installation cancelled.")
            return

        # Install
        installed_path = install_windows_batch(batch_dir)
        click.echo(f"✓ Created: {installed_path}")

        # Update PATH
        if not is_in_path(batch_dir):
            if add_to_user_path_windows(batch_dir):
                click.echo("✓ Added to PATH")
                click.echo("\n⚠ Restart your terminal for PATH changes to take effect")
            else:
                click.echo("✗ Could not update PATH automatically")
                click.echo(f"\nManually add to your PATH: {batch_dir}")

        click.echo("\nYou can now use: cwms-env <environment-name>")

    else:
        # Linux/Mac: Install shell function
        shell_name, rc_file = detect_shell()

        if not rc_file:
            click.echo("✗ Could not detect shell type")
            click.echo("\nManually add to your shell rc file:")
            click.echo('  cwms-env() { eval $(cwms-cli --quiet env activate "$@"); }')
            return

        if is_function_installed(rc_file):
            click.echo(f"✓ Already installed in: {rc_file}")
            return

        click.echo(f"Will add cwms-env() function to: {rc_file}")

        if not yes and not click.confirm("Continue?"):
            click.echo("Installation cancelled.")
            return

        # Install
        install_posix_function(rc_file)
        click.echo(f"✓ Added cwms-env() function to: {rc_file}")
        click.echo(f"\nReload your shell: source {rc_file}")
        click.echo("Then use: cwms-env <environment-name>")


@env_group.command(
    "activate", help="[Advanced] Generate shell export commands to activate an environment"
)
@click.argument("env_name")
@click.option(
    "--force",
    is_flag=True,
    hidden=True,
    help="Skip safety warnings (use with caution)",
)
@click.pass_context
def activate_cmd(ctx: click.Context, env_name: str, force: bool):
    """
    Output shell commands to activate an environment.

    RECOMMENDED WORKFLOW:
        1. First install the shell helper:
           cwms-cli env install

        2. Then switch environments using:
           cwms-env <environment-name>

    ADVANCED USAGE:
        Direct eval (not recommended for environments with API keys):
        eval $(cwms-cli env activate cwbi-dev)
    """
    envs_dir = get_envs_dir()
    env_file = envs_dir / f"{env_name}.env"

    if not env_file.exists():
        click.echo(
            f"# Error: Environment '{env_name}' not found at: {env_file}",
            err=True,
        )
        click.echo(
            "# Run 'cwms-cli env show' to see available environments",
            err=True,
        )
        click.echo(
            f"# Or run 'cwms-cli env setup {env_name}' to create it",
            err=True,
        )
        sys.exit(1)

    env_vars = read_env_file(env_file)

    # Security warning: Check if environment contains sensitive data and stdout is a TTY
    has_api_key = any("KEY" in key.upper() for key in env_vars.keys())
    if has_api_key and sys.stdout.isatty() and not force:
        click.echo(
            click.style("\n⚠️  SECURITY WARNING", fg="red", bold=True),
            err=True,
        )
        click.echo(
            click.style(
                "This environment contains API keys that will be printed to your terminal.",
                fg="yellow",
            ),
            err=True,
        )
        click.echo(
            "Running this command without 'eval' or the shell wrapper can expose secrets in:",
            err=True,
        )
        click.echo("  • Terminal history", err=True)
        click.echo("  • Script logs", err=True)
        click.echo("  • Screen recordings or screenshots", err=True)
        click.echo("", err=True)
        click.echo(
            click.style("Recommended usage:", fg="green", bold=True),
            err=True,
        )
        click.echo(
            f"  {click.style(f'eval $(cwms-cli --quiet env activate {env_name})', bold=True)}",
            err=True,
        )
        click.echo("", err=True)
        click.echo(
            f"Or install the shell wrapper: {click.style('cwms-cli env install', bold=True)}",
            err=True,
        )
        click.echo(
            f"and run: {click.style(f'cwms-env {env_name}', bold=True)}",
            err=True,
        )

        click.echo("", err=True)
        if not click.confirm(
            click.style("Continue anyway?", fg="red"),
            default=False,
            err=True,
        ):
            click.echo("Activation cancelled.", err=True)
            sys.exit(1)

    # Show helpful message to stderr (won't interfere with eval) unless logging is disabled
    # We check if INFO level logging is active - quiet mode sets it to WARNING
    if logging.getLogger().isEnabledFor(logging.INFO):
        if sys.platform == "win32":
            click.echo(
                "# To activate: FOR /F %i IN ('cwms-cli --quiet env activate "
                + env_name
                + "') DO %i",
                err=True,
            )
            click.echo(
                "# Or create cwms-env.bat with: @FOR /F %i IN ('cwms-cli --quiet env activate %*') DO %i",
                err=True,
            )
        else:
            click.echo(
                f"# To activate: eval $(cwms-cli --quiet env activate {env_name})",
                err=True,
            )
            click.echo(
                '# Or add to ~/.bashrc: cwms-env() { eval $(cwms-cli --quiet env activate "$@"); }',
                err=True,
            )

    # Output export commands to stdout (will be eval'd by shell)
    if sys.platform == "win32":
        for key, value in env_vars.items():
            click.echo(f"set {key}={value}")
    else:
        for key, value in env_vars.items():
            click.echo(f"export {key}={value}")
