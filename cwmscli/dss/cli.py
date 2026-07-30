from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import click
from click.core import ParameterSource

from cwmscli import requirements as reqs
from cwmscli.dss.naming import (
    ExportResolver,
    ImportResolver,
    MappingError,
    read_export_rules,
    read_filters,
    read_import_rules,
)
from cwmscli.utils import get_api_key, get_saved_login_token, to_uppercase
from cwmscli.utils.auth import DEFAULT_CDA_API_ROOT
from cwmscli.utils.deps import requires


@click.group("dss", help="Transfer time-series data between HEC-DSS and CWMS.")
def dss_group() -> None:
    pass


def _common_options(function):
    options = [
        click.option(
            "-o",
            "--office",
            required=True,
            envvar="OFFICE",
            callback=to_uppercase,
            help="CWMS office identifier.",
        ),
        click.option(
            "-dss",
            "--dss-file",
            required=True,
            type=click.Path(dir_okay=False, path_type=Path),
            help="HEC-DSS file.",
        ),
        click.option(
            "-f",
            "--mapping-file",
            type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
            help="Legacy direction-specific mapping CSV.",
        ),
        click.option(
            "-f2",
            "--filter-file",
            type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
            help="Legacy wildcard filter file.",
        ),
        click.option(
            "-p",
            "--lookback-hours",
            type=click.IntRange(min=1),
            help="Transfer the preceding number of hours, ending now.",
        ),
        click.option("--start", help="Inclusive ISO-8601 start time."),
        click.option("--end", help="Inclusive ISO-8601 end time."),
        click.option(
            "-a",
            "--api-root",
            envvar="CDA_API_ROOT",
            default=DEFAULT_CDA_API_ROOT,
            show_default=True,
            help="CWMS Data API root.",
        ),
        click.option("-k", "--api-key", envvar="CDA_API_KEY", help="CDA API key."),
        click.option(
            "-kl",
            "--api-key-loc",
            type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
            help="File containing a CDA API key.",
        ),
        click.option("--dry-run", is_flag=True, help="Validate without writing."),
        click.option(
            "-v",
            "--verbosity",
            type=click.IntRange(0, 2),
            default=1,
            show_default=True,
            help="Legacy output level: 0=quiet, 1=normal, 2=debug.",
        ),
        click.option(
            "-l",
            "--log-dir",
            type=click.Path(exists=True, file_okay=False, path_type=Path),
            help="Append to a legacy-style dated log file in this directory.",
        ),
        click.option(
            "-db",
            "--db-file",
            type=click.Path(path_type=Path),
            help="Unsupported legacy direct-database connection file.",
        ),
        click.option(
            "-m",
            "--monitor",
            is_flag=True,
            help="Unsupported legacy continuous-monitoring mode.",
        ),
    ]
    for option in reversed(options):
        function = option(function)
    return function


@dss_group.command("import", help="Transfer time-series data from DSS to CWMS.")
@_common_options
@click.option(
    "-id",
    "--identifier",
    help="Unsupported legacy shadow-file checkpoint identifier.",
)
@requires(reqs.hec, reqs.hecdss, reqs.cwms)
def import_cmd(
    office: str,
    dss_file: Path,
    mapping_file: Optional[Path],
    filter_file: Optional[Path],
    lookback_hours: Optional[int],
    start: Optional[str],
    end: Optional[str],
    api_root: str,
    api_key: Optional[str],
    api_key_loc: Optional[Path],
    dry_run: bool,
    verbosity: int,
    log_dir: Optional[Path],
    db_file: Optional[Path],
    monitor: bool,
    identifier: Optional[str],
) -> None:
    _reject_unsupported(db_file=db_file, monitor=monitor, identifier=identifier)
    _validate_files(mapping_file, filter_file)
    if not dss_file.is_file():
        raise click.UsageError(f"DSS source file does not exist: {dss_file}")
    start_time, end_time = _time_window(lookback_hours, start, end)
    _configure_legacy_logging(log_dir, "dss2cwms", verbosity)
    _configure_dss_logging(verbosity)
    try:
        resolver = ImportResolver(
            read_import_rules(mapping_file), read_filters(filter_file)
        )
        resolved_key, token = _credentials(api_key, api_key_loc)
        from cwmscli.dss.transfer import (
            CwmsSink,
            DssSource,
            NullSink,
            transfer_all,
            transform_import,
        )

        source = DssSource(str(dss_file), start_time, end_time)
        sink = None
        try:
            sink = (
                NullSink()
                if dry_run
                else CwmsSink(api_root, office, resolved_key, token)
            )
            summary = transfer_all(
                source=source,
                sink=sink,
                resolve=resolver.resolve,
                transform=transform_import,
                dry_run=dry_run,
                identifiers=resolver.catalog_identifiers(),
            )
        finally:
            source.close()
            if sink is not None and not dry_run:
                sink.close()
    except MappingError as error:
        raise click.ClickException(str(error)) from error
    _finish(summary, verbosity)


@dss_group.command("export", help="Transfer time-series data from CWMS to DSS.")
@_common_options
@click.option(
    "-tz",
    "--dss-time-zone",
    default="UTC",
    show_default=True,
    help="Time zone used for data written to DSS.",
)
@requires(reqs.hec, reqs.hecdss, reqs.cwms)
def export_cmd(
    office: str,
    dss_file: Path,
    mapping_file: Optional[Path],
    filter_file: Optional[Path],
    lookback_hours: Optional[int],
    start: Optional[str],
    end: Optional[str],
    api_root: str,
    api_key: Optional[str],
    api_key_loc: Optional[Path],
    dry_run: bool,
    verbosity: int,
    log_dir: Optional[Path],
    db_file: Optional[Path],
    monitor: bool,
    dss_time_zone: str,
) -> None:
    _reject_unsupported(db_file=db_file, monitor=monitor)
    _validate_files(mapping_file, filter_file)
    _validate_time_zone(dss_time_zone)
    start_time, end_time = _time_window(lookback_hours, start, end)
    _configure_legacy_logging(log_dir, "cwms2dss", verbosity)
    _configure_dss_logging(verbosity)
    try:
        resolver = ExportResolver(
            read_export_rules(mapping_file), read_filters(filter_file)
        )
        resolved_key, token = _credentials(api_key, api_key_loc)
        from cwmscli.dss.transfer import (
            CwmsSource,
            DssSink,
            NullSink,
            transfer_all,
            transform_export,
        )

        source = CwmsSource(api_root, office, start_time, end_time, resolved_key, token)
        sink = None
        try:
            sink = NullSink() if dry_run else DssSink(str(dss_file))
            summary = transfer_all(
                source=source,
                sink=sink,
                resolve=resolver.resolve,
                transform=lambda timeseries, rule: transform_export(
                    timeseries, rule, dss_time_zone
                ),
                dry_run=dry_run,
                identifiers=resolver.catalog_identifiers(),
            )
        finally:
            source.close()
            if sink is not None and not dry_run:
                sink.close()
    except MappingError as error:
        raise click.ClickException(str(error)) from error
    _finish(summary, verbosity)


def _credentials(
    api_key: Optional[str], api_key_loc: Optional[Path]
) -> tuple[Optional[str], Optional[str]]:
    if api_key is not None or api_key_loc is not None:
        return get_api_key(api_key, str(api_key_loc) if api_key_loc else None), None
    return None, get_saved_login_token()


def _reject_unsupported(
    *,
    db_file: Optional[Path],
    monitor: bool,
    identifier: Optional[str] = None,
) -> None:
    if db_file is not None:
        raise click.UsageError(
            "-db/--db-file is not supported. This port uses CDA; pass --api-root "
            "and authenticate with cwms-cli login, --api-key, or --api-key-loc."
        )
    if monitor:
        raise click.UsageError(
            "-m/--monitor is not supported in the batch-only first release."
        )
    if identifier is not None:
        raise click.UsageError(
            "-id/--identifier shadow-file checkpointing is deferred with monitoring."
        )


def _validate_files(mapping_file: Optional[Path], filter_file: Optional[Path]) -> None:
    if mapping_file and filter_file:
        raise click.UsageError(
            "--mapping-file and --filter-file are mutually exclusive."
        )


def _time_window(
    lookback_hours: Optional[int], start: Optional[str], end: Optional[str]
) -> tuple[datetime, datetime]:
    if lookback_hours is not None:
        if start is not None or end is not None:
            raise click.UsageError(
                "--lookback-hours cannot be combined with --start or --end."
            )
        end_time = datetime.now(timezone.utc)
        return end_time - timedelta(hours=lookback_hours), end_time
    if start is None or end is None:
        raise click.UsageError(
            "Specify either -p/--lookback-hours or both --start and --end."
        )
    try:
        start_time = _parse_datetime(start)
        end_time = _parse_datetime(end)
    except ValueError as error:
        raise click.BadParameter(
            "times must be valid ISO-8601 values", param_hint="--start/--end"
        ) from error
    if start_time >= end_time:
        raise click.UsageError("--start must be earlier than --end.")
    return start_time, end_time


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _configure_legacy_logging(
    log_dir: Optional[Path], program: str, verbosity: int
) -> None:
    root = logging.getLogger()
    context = click.get_current_context(silent=True)
    direct_legacy_entry = context is None or context.parent is None
    verbosity_is_explicit = (
        context is not None
        and context.get_parameter_source("verbosity") == ParameterSource.COMMANDLINE
    )
    if direct_legacy_entry or verbosity_is_explicit:
        root.setLevel((logging.WARNING, logging.INFO, logging.DEBUG)[verbosity])
    if log_dir is None:
        return
    filename = log_dir / f"{program}.{datetime.now():%Y.%m.%d}.log"
    handler = logging.FileHandler(filename, mode="a", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    root.addHandler(handler)


def _configure_dss_logging(verbosity: int) -> None:
    from hec import DssDataStore

    DssDataStore.set_message_level((0, 1, 5)[verbosity])


def _validate_time_zone(value: str) -> None:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as error:
        raise click.BadParameter(
            f"unknown time zone: {value}", param_hint="--dss-time-zone"
        ) from error


def _finish(summary, verbosity: int) -> None:
    message = (
        f"Discovered: {summary.discovered}; transferred: {summary.transferred}; "
        f"skipped: {summary.skipped}; failed: {summary.failed}"
    )
    if verbosity > 0 or summary.failed:
        click.echo(message, err=bool(summary.failed))
    if summary.failed:
        raise click.ClickException(
            f"Transfer completed with {summary.failed} failed time series."
        )
