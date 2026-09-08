from urllib.parse import urlparse

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

_LOCAL_INPUT_PATH = click.Path(exists=True, dir_okay=False, readable=True)


def validate_input_source(ctx, param, value):
    """Accept an existing local file or a well-formed HTTP(S) URL."""
    parsed = urlparse(value)
    if parsed.scheme.lower() in {"http", "https"}:
        if not parsed.netloc:
            raise click.BadParameter("HTTP(S) URLs must include a host")
        return value
    if "://" in value:
        raise click.BadParameter("only HTTP(S) URLs are supported")
    return _LOCAL_INPUT_PATH.convert(value, param, ctx)


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
        "(--config) or read from a CWMS blob (--config-blob-id). If neither is "
        "given, the blob CONFIG_PIXML is fetched from the target office."
    ),
)
@click.option(
    "-i",
    "--input",
    required=True,
    type=str,
    callback=validate_input_source,
    help=(
        "Existing local file or HTTP(S) URL for the PI-XML product. Raw XML "
        "may be extensionless; .gz and .zip suffixes are uncompressed "
        "automatically (case-insensitive)."
    ),
)
@click.option(
    "-c",
    "--config",
    default=None,
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Path to a JSON config file.",
)
@click.option(
    "--config-blob-id",
    default=None,
    type=str,
    help="Blob id of a JSON config stored in the target CDA. "
    "If neither --config nor --config-blob-id is given, defaults to CONFIG_PIXML.",
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
    input,
    config,
    config_blob_id,
    office,
    api_root,
    api_key,
    api_key_loc,
    dry_run,
):
    from cwmscli.nws.load_pixml import load_pixml

    if config is not None and config_blob_id is not None:
        raise click.UsageError("--config and --config-blob-id are mutually exclusive.")
    if config is None and config_blob_id is None:
        config_blob_id = "CONFIG_PIXML"

    # API key is optional: a saved cwms-cli login token (resolved inside
    # init_cwms_session) takes precedence. Only resolve a key if one was given.
    resolved_key = None
    if api_key is not None or api_key_loc is not None:
        resolved_key = get_api_key(api_key, api_key_loc)

    load_pixml(
        input_=input,
        config_file=config,
        config_blob_id=config_blob_id,
        office=office,
        api_root=api_root,
        api_key=resolved_key,
        dry_run=dry_run,
    )
