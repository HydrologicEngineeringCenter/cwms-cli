import os
import subprocess
import sys
import textwrap
from typing import Optional

import click

from cwmscli import requirements as reqs
from cwmscli.callbacks import csv_to_list
from cwmscli.commands import csv2cwms
from cwmscli.utils import api_key_loc_option, colors, common_api_options, to_uppercase
from cwmscli.utils.deps import requires
from cwmscli.utils.update import (
    build_update_package_spec,
    launch_windows_update,
    looks_like_missing_version,
)
from cwmscli.utils.version import get_cwms_cli_version


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


@click.command(
    "update",
    help="Update cwms-cli with pip, optionally targeting a specific version.",
)
@click.option(
    "--target-version",
    "target_version",
    metavar="VERSION",
    help="Install a specific cwms-cli version instead of the latest release.",
)
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
def update_cli_cmd(target_version: Optional[str], pre: bool, yes: bool) -> None:
    current_version = get_cwms_cli_version()
    package_spec = build_update_package_spec(target_version)

    click.echo(
        "Current cwms-cli version: " f"{colors.c(current_version, 'cyan', bright=True)}"
    )
    if target_version:
        click.echo(
            "Requested cwms-cli version: "
            f"{colors.c(target_version, 'cyan', bright=True)}"
        )
    else:
        click.echo("Requested cwms-cli version: latest available release")

    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", package_spec]
    if pre:
        cmd.append("--pre")

    if not yes:
        proceed = click.confirm("Proceed with updating cwms-cli via pip?", default=True)
        if not proceed:
            click.echo(colors.warn("Update canceled."))
            return

    click.echo(f"Running: {' '.join(cmd)}")
    if os.name == "nt":
        try:
            script_path = launch_windows_update(cmd)
        except OSError as e:
            raise click.ClickException(
                f"Unable to launch Windows update process: {e}"
            ) from e
        click.echo(
            colors.ok(
                "Opened a separate command window to complete the update after "
                "cwms-cli exits."
            )
        )
        click.echo(f"Update helper script: {script_path}")
        return

    try:
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as e:
        raise click.ClickException(f"Unable to run pip update command: {e}") from e

    if result.stdout:
        click.echo(result.stdout, nl=False)
    if result.stderr:
        click.echo(result.stderr, err=True, nl=False)

    if result.returncode != 0:
        pip_output = "\n".join(part for part in [result.stdout, result.stderr] if part)
        if target_version and looks_like_missing_version(pip_output, package_spec):
            raise click.ClickException(
                colors.err(
                    f"Requested cwms-cli version '{target_version}' was not found."
                )
            )
        raise click.ClickException(
            colors.err("cwms-cli update failed. Please review pip output above.")
        )

    click.echo(colors.ok("Update complete. Run `cwms-cli --version` to verify."))


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
@blob_group.command(
    "upload",
    help="Upload a single file or a directory of files as CWMS blob(s).",
)
@click.option(
    "--input-file",
    required=False,
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=str),
    help="Path to a single file to upload.",
)
@click.option(
    "--input-dir",
    required=False,
    type=click.Path(exists=True, file_okay=False, readable=True, path_type=str),
    help="Directory containing multiple files to upload.",
)
@click.option(
    "--file-regex",
    default=".*",
    show_default=True,
    type=str,
    help="Regex used to match files in --input-dir (matched against relative path).",
)
@click.option(
    "--recursive/--no-recursive",
    default=False,
    show_default=True,
    help="Recurse into subdirectories when using --input-dir.",
)
@click.option(
    "--blob-id",
    required=False,
    type=str,
    help="Blob ID to create for single-file upload.",
)
@click.option(
    "--blob-id-prefix",
    default="",
    show_default=True,
    type=str,
    help="Prefix added to generated blob IDs for directory uploads.",
)
@click.option("--description", default=None, help="Optional description JSON or text.")
@click.option(
    "--media-type",
    default=None,
    help="Override media type (guessed from file if omitted).",
)
@click.option(
    "--overwrite/--no-overwrite",
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
@click.option(
    "--anonymous",
    is_flag=True,
    help="Do not send credentials for this read request, even if they are configured.",
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
@click.option(
    "--anonymous",
    is_flag=True,
    help="Do not send credentials for this read request, even if they are configured.",
)
@common_api_options
@requires(reqs.cwms)
def list_cmd(**kwargs):
    from cwmscli.commands.blob import list_cmd

    list_cmd(**kwargs)
