import click

from cwmscli import requirements as reqs
from cwmscli.utils import (
    api_key_loc_option,
    api_key_option,
    api_root_option,
    get_api_key,
    office_option,
)
from cwmscli.utils.deps import requires


@click.group()
def nws_group():
    """NWS utilities"""
    pass


@nws_group.command(
    "pixml",
    help=(
        "Load an NWS/RFC Delft-FEWS PI-XML forecast product into a CWMS database. "
        "Behavior (parameter mapping, timeseries-group overrides, versioning, "
        "issued-time tracking) is driven by a JSON config, provided as a file "
        "(--config) or read from a CWMS blob (--config-blob). If neither is "
        "given, the blob CONFIG_PIXML is fetched from the target office."
    ),
)
@click.option(
    "-i",
    "--input",
    "input_",
    required=True,
    type=str,
    help="Path or URL to the PI-XML product. URLs ending in .gz or .zip are unzipped automatically.",
)
@click.option(
    "-c",
    "--config",
    "config_file",
    default=None,
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Path to a JSON config file.",
)
@click.option(
    "--config-blob",
    "config_blob",
    default=None,
    type=str,
    help="Blob id of a JSON config stored in the target CDA. "
    "If neither --config nor --config-blob is given, defaults to CONFIG_PIXML.",
)
@office_option
@api_root_option
@api_key_option
@api_key_loc_option
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Parse and resolve everything, print what would be written, but make no API calls.",
)
@requires(reqs.cwms, reqs.requests)
def nws_pixml(
    input_,
    config_file,
    config_blob,
    office,
    api_root,
    api_key,
    api_key_loc,
    dry_run,
):
    from cwmscli.nws.load_pixml import load_pixml

    if config_file is not None and config_blob is not None:
        raise click.UsageError("--config and --config-blob are mutually exclusive.")
    if config_file is None and config_blob is None:
        config_blob = "CONFIG_PIXML"

    # API key is optional: a saved cwms-cli login token (resolved inside
    # init_cwms_session) takes precedence. Only resolve a key if one was given.
    resolved_key = None
    if api_key is not None or api_key_loc is not None:
        resolved_key = get_api_key(api_key, api_key_loc)

    load_pixml(
        input_=input_,
        config_file=config_file,
        config_blob=config_blob,
        office=office,
        api_root=api_root,
        api_key=resolved_key,
        dry_run=dry_run,
    )
