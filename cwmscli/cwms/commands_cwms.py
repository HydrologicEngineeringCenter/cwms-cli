import click

from cwmscli import requirements as reqs
from cwmscli.utils import (
    api_key_loc_option,
    api_key_option,
    api_root_option,
    get_api_key,
    office_option,
    script_version_option,
)
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
@office_option
@api_root_option
@api_key_option
@api_key_loc_option
@requires(reqs.cwms)
def shefcritimport(filename, office, api_root, api_key, api_key_loc):
    from cwmscli.cwms.shef_critfile_import import import_shef_critfile

    api_key = get_api_key(api_key, api_key_loc)
    import_shef_critfile(
        file_path=filename,
        office_id=office,
        api_root=api_root,
        api_key=api_key,
    )


@click.command("csv2cwms", help="Store CSV TimeSeries data to CWMS using a config file")
@office_option
@api_root_option
@api_key_option
@script_version_option
@click.option(
    "-l",
    "--location",
    default="all",
    show_default=True,
    help='Location ID. Use "-p=all" for all locations.',
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
@click.option(
    "-dp",
    "--data-path",
    "data_path",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False),
    help="Directory where csv files are stored",
)
@click.option("--dry-run", is_flag=True, help="Log only (no HTTP calls)")
@click.option("--begin", type=str, help="YYYY-MM-DDTHH:MM (local to --tz)")
@click.option("-tz", "--timezone", "tz", default="GMT", show_default=True)
@click.option(
    "--ignore-ssl-errors", is_flag=True, help="Ignore TLS errors (testing only)"
)
def csv2cwms_cmd(**kwargs):
    # Handle the version for this specific command
    if kwargs.pop("version", False):
        from cwmscli.csv2cwms import __version__

        click.echo(f"csv2cwms v{__version__}")
        return
    csv2_main(**kwargs)
