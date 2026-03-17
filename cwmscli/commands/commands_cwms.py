import subprocess
import sys
import textwrap
from pathlib import Path

import click

from cwmscli import requirements as reqs
from cwmscli.callbacks import csv_to_list
from cwmscli.commands import csv2cwms
from cwmscli.utils import api_key_loc_option, common_api_options, to_uppercase
from cwmscli.utils.deps import requires
from cwmscli.utils.version import get_cwms_cli_version


@click.command(
    "login",
    help="Authenticate with CWBI OIDC using PKCE and save tokens for reuse.",
)
@click.option(
    "--provider",
    type=click.Choice(["federation-eams", "login.gov"], case_sensitive=False),
    default="federation-eams",
    show_default=True,
    help="Identity provider hint to send to Keycloak.",
)
@click.option(
    "--client-id",
    default="cwms",
    show_default=True,
    help="OIDC client ID.",
)
@click.option(
    "--oidc-base-url",
    default="https://identity-test.cwbi.us/auth/realms/cwbi/protocol/openid-connect",
    show_default=True,
    help="OIDC realm base URL ending in /protocol/openid-connect.",
)
@click.option(
    "--scope",
    default="openid profile",
    show_default=True,
    help="OIDC scopes to request.",
)
@click.option(
    "--redirect-host",
    default="127.0.0.1",
    show_default=True,
    help="Local host for the login callback listener.",
)
@click.option(
    "--redirect-port",
    default=5555,
    type=int,
    show_default=True,
    help="Local port for the login callback listener.",
)
@click.option(
    "--token-file",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Path to save the login session JSON. Defaults to a provider-specific file under ~/.config/cwms-cli/auth/.",
)
@click.option(
    "--refresh",
    "refresh_only",
    is_flag=True,
    default=False,
    help="Refresh an existing saved session instead of opening a new browser login.",
)
@click.option(
    "--no-browser",
    is_flag=True,
    default=False,
    help="Print the authorization URL instead of trying to open a browser automatically.",
)
@click.option(
    "--timeout",
    default=30,
    type=int,
    show_default=True,
    help="Seconds to wait for the local login callback.",
)
@click.option(
    "--ca-bundle",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True, path_type=Path),
    default=None,
    help="CA bundle to use for TLS verification.",
)
@requires(reqs.requests)
def login_cmd(
    provider: str,
    client_id: str,
    oidc_base_url: str,
    scope: str,
    redirect_host: str,
    redirect_port: int,
    token_file: Path,
    refresh_only: bool,
    no_browser: bool,
    timeout: int,
    ca_bundle: Path,
):
    from cwmscli.utils.auth import (
        AuthError,
        CallbackBindError,
        LoginTimeoutError,
        OIDCLoginConfig,
        default_token_file,
        login_with_browser,
        refresh_saved_login,
        save_login,
        token_expiry_text,
    )
    from cwmscli.utils.colors import err

    provider = provider.lower()
    token_file = token_file or default_token_file(provider)
    verify = str(ca_bundle) if ca_bundle else None

    try:
        if refresh_only:
            result = refresh_saved_login(token_file=token_file, verify=verify)
            config = result["config"]
            token = result["token"]
        else:
            config = OIDCLoginConfig(
                client_id=client_id,
                oidc_base_url=oidc_base_url.rstrip("/"),
                redirect_host=redirect_host,
                redirect_port=redirect_port,
                scope=scope,
                provider=provider,
                timeout_seconds=timeout,
                verify=verify,
            )
            auth_url_shown = False

            def show_auth_url(url: str) -> None:
                nonlocal auth_url_shown
                click.echo("Visit this URL to authenticate:")
                click.echo(url)
                auth_url_shown = True

            result = login_with_browser(
                config=config,
                launch_browser=not no_browser,
                authorization_url_callback=show_auth_url if no_browser else None,
            )
            config = result.get("config", config)
            if (not auth_url_shown) and (not result["browser_opened"]):
                click.echo("Visit this URL to authenticate:")
                click.echo(result["authorization_url"])
            token = result["token"]

        save_login(token_file=token_file, config=config, token=token)
    except LoginTimeoutError as e:
        click.echo(err(f"ALERT: {e}"), err=True)
        raise click.exceptions.Exit(1) from e
    except CallbackBindError as e:
        click.echo(err(f"ALERT: {e}"), err=True)
        raise click.exceptions.Exit(1) from e
    except AuthError as e:
        raise click.ClickException(str(e)) from e
    except OSError as e:
        raise click.ClickException(f"Login setup failed: {e}") from e

    click.echo(f"Saved login session to {token_file}")
    expiry = token_expiry_text(token)
    if expiry:
        click.echo(f"Access token expires at {expiry}")
    if token.get("refresh_token"):
        click.echo("Refresh token is available for future reuse.")


@click.command(
    "shefcritimport",
    help="Import SHEF crit file into timeseries group for SHEF file processing",
)
@click.option(
    "-f",
    "--filename",
    required=True,
    type=str,
    help="filename of SHEF crit file to be processed",
)
@common_api_options
@api_key_loc_option
@requires(reqs.cwms)
def shefcritimport(filename, office, api_root, api_key, api_key_loc):
    from cwmscli.commands.shef_critfile_import import import_shef_critfile
    from cwmscli.utils import get_api_key

    api_key = get_api_key(api_key, api_key_loc)
    import_shef_critfile(
        file_path=filename,
        office_id=office,
        api_root=api_root,
        api_key=api_key,
    )


@click.command("csv2cwms", help="Store CSV TimeSeries data to CWMS using a config file")
@common_api_options
@click.option(
    "--input-keys",
    "input_keys",
    default="all",
    show_default=True,
    help='Input keys. Defaults to all keys/files with --input-keys=all. These are the keys under "input_files" in a given config file. This option lets you run a single file from a config that contains multiple files. Example: --input-keys=file1',
)
@click.option(
    "-lb",
    "--lookback",
    type=int,
    default=24 * 5,
    show_default=True,
    help="Lookback period in HOURS",
)
@click.option("-v", "--verbose", is_flag=True, help="Verbose logging")
@click.option(
    "-c",
    "--config",
    "config_path",
    required=True,
    type=click.Path(exists=True),
    help="Path to JSON config file",
)
@click.option(
    "-df",
    "--data-file",
    "data_file",
    type=str,
    help="Override CSV file (else use config)",
)
@click.option("--log", show_default=True, help="Path to the log file.")
@click.option("--dry-run", is_flag=True, help="Log only (no HTTP calls)")
@click.option("--begin", type=str, help="YYYY-MM-DDTHH:MM (local to --tz)")
@click.option("-tz", "--timezone", "tz", default="GMT", show_default=True)
@click.option(
    "--ignore-ssl-errors", is_flag=True, help="Ignore TLS errors (testing only)"
)
@click.version_option(version=csv2cwms.__version__)
@requires(reqs.cwms)
def csv2cwms_cmd(**kwargs):
    from cwmscli.commands.csv2cwms.__main__ import main as csv2_main

    # Handle the version for this specific command
    if kwargs.pop("version", False):
        from cwmscli.commands.csv2cwms import __version__

        click.echo(f"csv2cwms v{__version__}")
        return
    csv2_main(**kwargs)


@click.command("update", help="Update cwms-cli to the latest version using pip.")
@click.option(
    "--pre",
    is_flag=True,
    default=False,
    help="Include pre-release versions during update.",
)
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    default=False,
    help="Skip confirmation prompt and run update immediately.",
)
def update_cli_cmd(pre: bool, yes: bool) -> None:
    current_version = get_cwms_cli_version()
    click.echo(f"Current cwms-cli version: {current_version}")

    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "cwms-cli"]
    if pre:
        cmd.append("--pre")

    if not yes:
        proceed = click.confirm("Proceed with updating cwms-cli via pip?", default=True)
        if not proceed:
            click.echo("Update canceled.")
            return

    click.echo(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=False)
    except OSError as e:
        raise click.ClickException(f"Unable to run pip update command: {e}") from e

    if result.returncode != 0:
        raise click.ClickException(
            "cwms-cli update failed. Please review pip output above."
        )

    click.echo("Update complete. Run `cwms-cli --version` to verify.")


# region Blob
# ================================================================================
#  BLOB
# ================================================================================
@click.group(
    "blob",
    help="Manage CWMS Blobs (upload, download, delete, update, list)",
    epilog=textwrap.dedent(
        """
    Example Usage:\n
    - Store a PDF/image as a CWMS blob with optional description\n
    - Download a blob by id to your local filesystem\n
    - Update a blob's name/description/mime-type\n
    - Bulk list blobs for an office  
"""
    ),
)
def blob_group():
    pass


# ================================================================================
#       Upload
# ================================================================================
@blob_group.command("upload", help="Upload a file as a blob")
@click.option(
    "--input-file",
    required=True,
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=str),
    help="Path to the file to upload.",
)
@click.option("--blob-id", required=True, type=str, help="Blob ID to create.")
@click.option("--description", default=None, help="Optional description JSON or text.")
@click.option(
    "--media-type",
    default=None,
    help="Override media type (guessed from file if omitted).",
)
@click.option(
    "--overwrite",
    default=False,
    show_default=True,
    help="If true, replace existing blob.",
)
@click.option("--dry-run", is_flag=True, help="Show request; do not send.")
@common_api_options
@requires(reqs.cwms)
def blob_upload(**kwargs):
    from cwmscli.commands.blob import upload_cmd

    upload_cmd(**kwargs)


# ================================================================================
#       Download
# ================================================================================
@blob_group.command("download", help="Download a blob by ID")
# TODO: test XML
@click.option("--blob-id", required=True, type=str, help="Blob ID to download.")
@click.option(
    "--dest",
    default=None,
    help="Destination file path. Defaults to blob-id.",
)
@click.option("--dry-run", is_flag=True, help="Show request; do not send.")
@common_api_options
@requires(reqs.cwms)
def blob_download(**kwargs):
    from cwmscli.commands.blob import download_cmd

    download_cmd(**kwargs)


# ================================================================================
#       Delete
# ================================================================================
@blob_group.command("delete", help="Delete a blob by ID")
@click.option("--blob-id", required=True, type=str, help="Blob ID to delete.")
@click.option("--dry-run", is_flag=True, help="Show request; do not send.")
@common_api_options
@requires(reqs.cwms)
def delete_cmd(**kwargs):
    from cwmscli.commands.blob import delete_cmd

    delete_cmd(**kwargs)


# ================================================================================
#       Update
# ================================================================================
@blob_group.command("update", help="Update/patch a blob by ID")
@click.option("--blob-id", required=True, type=str, help="Blob ID to update.")
@click.option("--dry-run", is_flag=True, help="Show request; do not send.")
@click.option(
    "--description",
    default=None,
    help="New description JSON or text.",
)
@click.option(
    "--media-type",
    default=None,
    help="New media type (guessed from file if omitted).",
)
@click.option(
    "--input-file",
    required=False,
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=str),
    help="Optional file content to upload with update.",
)
@click.option(
    "--overwrite/--no-overwrite",
    default=False,
    show_default=True,
    help="If true, replace existing blob.",
)
@common_api_options
@requires(reqs.cwms)
def update_cmd(**kwargs):
    from cwmscli.commands.blob import update_cmd

    update_cmd(**kwargs)


# ================================================================================
#       List
# ================================================================================
@blob_group.command("list", help="List blobs with optional filters and sorting")
# TODO: Add link to regex docs when new CWMS-DATA site is deployed to PROD
@click.option(
    "--blob-id-like", help="LIKE filter for blob ID (e.g., ``*PNG``)."
)  # Escape the wildcard/asterisk for RTD generation with double backticks
@click.option(
    "--columns",
    multiple=True,
    callback=csv_to_list,
    help="Columns to show (repeat or comma-separate).",
)
@click.option(
    "--sort-by",
    multiple=True,
    callback=csv_to_list,
    help="Columns to sort by (repeat or comma-separate).",
)
@click.option(
    "--desc/--asc",
    default=False,
    show_default=True,
    help="Sort descending instead of ascending.",
)
@click.option("--limit", type=int, default=None, help="Max rows to show.")
@click.option(
    "--to-csv",
    type=click.Path(dir_okay=False, writable=True, path_type=str),
    help="If set, write results to this CSV file.",
)
@common_api_options
@requires(reqs.cwms)
def list_cmd(**kwargs):
    from cwmscli.commands.blob import list_cmd

    list_cmd(**kwargs)
