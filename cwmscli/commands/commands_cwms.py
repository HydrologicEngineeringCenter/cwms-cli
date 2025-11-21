import click

from cwmscli import requirements as reqs
from cwmscli.callbacks import csv_to_list
from cwmscli.commands import csv2cwms
from cwmscli.utils import api_key_loc_option, common_api_options
from cwmscli.utils.deps import requires


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


# region Blob
# ================================================================================
#  BLOB
# ================================================================================
@click.group(
    "blob",
    help="Manage CWMS Blobs (upload, download, delete, update, list)",
    epilog="""
  * Store a PDF/image as a CWMS blob with optional description
  * Download a blob by id to your local filesystem
  * Update a blob's name/description
  * Bulk list blobs for an office
""",
)
@requires(reqs.cwms)
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
    "--overwrite/--no-overwrite",
    default=False,
    show_default=True,
    help="If true, replace existing blob.",
)
@click.option("--dry-run", is_flag=True, help="Show request; do not send.")
@common_api_options
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
@common_api_options
def blob_download(**kwargs):
    from cwmscli.commands.blob import download_cmd

    download_cmd(**kwargs)


# ================================================================================
#       Delete
# ================================================================================
@blob_group.command("delete", help="[Not implemented] Delete a blob by ID")
@click.option("--blob-id", required=True, type=str, help="Blob ID to delete.")
@common_api_options
def delete_cmd(**kwargs):
    from cwmscli.commands.blob import delete_cmd

    delete_cmd(**kwargs)


# ================================================================================
#       Update
# ================================================================================
@blob_group.command("update", help="[Not implemented] Update/patch a blob by ID")
@click.option("--blob-id", required=True, type=str, help="Blob ID to update.")
@click.option(
    "--input-file",
    required=False,
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=str),
    help="Optional file content to upload with update.",
)
@common_api_options
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
def list_cmd(**kwargs):
    from cwmscli.commands.blob import list_cmd

    list_cmd(**kwargs)


# endregion
