import textwrap

import click

from cwmscli import requirements as reqs
from cwmscli.callbacks import csv_to_list
from cwmscli.commands import csv2cwms
from cwmscli.utils import api_key_loc_option, common_api_options, to_uppercase
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
@click.option("--dry-run", is_flag=True, help="Show request; do not send.")
@common_api_options
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


# region Time Series
# ================================================================================
#  Time Series
# ================================================================================
@click.group(
    "timeseries",
    help="Manage CWMS Time Series",
    epilog=textwrap.dedent(
        """
    Example Usage:\n
    - Manage Time Series Groups\n
    - More Coming Soon!
"""
    ),
)
@requires(reqs.cwms)
def timeseries():
    pass


# region Time Series Group
# ================================================================================
#  Time Series Group
# ================================================================================
@timeseries.group(
    "group",
    help="Manage CWMS Time Series Groups (upload, download, delete, update, list)",
    epilog=textwrap.dedent(
        """
    Example Usage:\n
    - Store Time Series Groups from CLI\n
    - Download a Time Series Group to your local filesystem\n
    - Update a Time Series Group description, category, and identifiers\n
    - Bulk list Time Series Groups for a given office
"""
    ),
)
def timeseries_group():
    pass


# ================================================================================
#       Store
# ================================================================================
@timeseries_group.command("store", help="Store a timeseries group")
@click.option(
    "--overwrite/--no-overwrite",
    default=False,
    show_default=True,
    help="If true, replace existing timeseries group.",
)
@click.option(
    "--input-file",
    required=False,
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=str),
    help="Specify a relative/absolute path to a JSON file containing the request body. If not specified, it will be read from stdin.",
)
@click.option("--dry-run", is_flag=True, help="Show request; do not send.")
@common_api_options
def timeseries_group_upload(**kwargs):
    from cwmscli.commands.timeseries.group import store_cmd

    store_cmd(**kwargs)


# ================================================================================
#       Download
# ================================================================================
@timeseries_group.command("retrieve", help="Download timeseries group")
@click.option(
    "--group-id",
    type=str,
    help="Specifies the timeseries group whose data is to be included in the response",
)
@click.option(
    "--office",
    type=str,
    callback=to_uppercase,
    help="Specifies the owning office of the timeseries assigned to the group whose data is to be included in the response. This will limit the assigned timeseries returned to only those assigned to the specified office.",
)
@click.option(
    "--category-office-id",
    type=str,
    help="Specifies the owning office of the timeseries group category",
)
@click.option(
    "--group-office-id",
    type=str,
    help="Specifies the owning office of the timeseries group",
)
@click.option(
    "--category-id",
    type=str,
    help="Specifies the category containing the timeseries group whose data is to be included in the response.",
)
@click.option("--dry-run", is_flag=True, help="Show request; do not send.")
@click.option(
    "--dest-dir",
    required=False,
    type=click.Path(exists=True, dir_okay=True, readable=True, path_type=str),
    help="""Specify a relative/absolute path to a directory where the output file will be saved.
        The file will be named <office>_<group-id>.json.
        If not specified, it will be written to stdout.""",
)
@common_api_options
def timeseries_group_download(**kwargs):
    from cwmscli.commands.timeseries.group import retrieve_cmd

    retrieve_cmd(**kwargs)


# ================================================================================
#       Delete
# ================================================================================
@timeseries_group.command("delete", help="Delete a timeseries group")
@click.option("--blob-id", required=True, type=str, help="Blob ID to delete.")
@click.option("--dry-run", is_flag=True, help="Show request; do not send.")
@common_api_options
def delete_cmd(**kwargs):
    from cwmscli.commands.timeseries.group import delete_cmd

    delete_cmd(**kwargs)


# ================================================================================
#       Update
# ================================================================================
@timeseries_group.command("update", help="Update/patch a timeseries group")
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
def update_cmd(**kwargs):
    from cwmscli.commands.timeseries.group import update_cmd

    update_cmd(**kwargs)


# timeseries_category_like=timeseries_category_like,
# category_office_id=category_office_id,
# timeseries_group_like=timeseries_group_like,


# ================================================================================
#       List
# ================================================================================
@timeseries_group.command("list", help="List blobs with optional filters and sorting")
@click.option(
    "--include-assigned",
    default=False,
    show_default=True,
    help="Include the assigned timeseries in the returned timeseries groups. (default: true)",
)
@click.option(
    "--timeseries-category-like",
    help="Posix regular expression matching against the timeseries category id",
)
@click.option(
    "--category-office-id",
    help="Specifies the owning office of the timeseries group category",
)
@click.option(
    "--timeseries-group-like",
    help="Posix regular expression matching against the timeseries group id",
)
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
    from cwmscli.commands.timeseries.group import list_cmd

    list_cmd(**kwargs)


# endregion
# endregion
