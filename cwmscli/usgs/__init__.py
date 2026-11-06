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
def usgs_group():
    """USGS utilities"""
    pass


days_back_option = click.option(
    "-d",
    "--days-back",
    default="1",
    type=float,
    help="Days back from current time to get data.  Can be decimal and integer values",
)


@usgs_group.command(
    "timeseries", help="Get USGS timeseries values and store into CWMS database"
)
@office_option
@days_back_option
@api_root_option
@api_key_option
@api_key_loc_option
@click.option(
    "-b",
    "--backfill",
    default=None,
    type=str,
    help='Backfill timeseries ids, use list of timeseries ids (e.g. "ts_id1, ts_id2") to attempt to backfill a subset of timeseries with USGS data',
)
@click.option(
    "-bv",
    "--backfill-version",
    default=None,
    type=str,
    help='Backfill version, save data to a different version of the timeseries (e.g. "Rev-USGS" instead of "Raw-USGS")',
)
@requires(reqs.cwms, reqs.requests)
def getusgs_timeseries(
    office, days_back, api_root, api_key, api_key_loc, backfill, backfill_version
):
    from cwmscli.usgs.getusgs_cda import getusgs_cda

    if backfill is not None:
        backfill_list = [item.strip() for item in backfill.split(",") if item.strip()]
    else:
        backfill_list = None

    api_key = get_api_key(api_key, api_key_loc)
    getusgs_cda(
        api_root=api_root,
        office_id=office,
        days_back=days_back,
        api_key=api_key,
        backfill_tsids=backfill_list,
        backfill_version=backfill_version,
    )


@usgs_group.command(
    "timeseries-v2",
    help="Get USGS timeseries values using the new OGC API and store into CWMS database",
)
@office_option
@days_back_option
@api_root_option
@api_key_option
@api_key_loc_option
@click.option(
    "-b",
    "--backfill",
    default=None,
    type=str,
    help='Backfill timeseries ids, use list of timeseries ids (e.g. "ts_id1, ts_id2") to attempt to backfill a subset of timeseries with USGS data',
)
@click.option(
    "-bv",
    "--backfill-version",
    default=None,
    type=str,
    help='Backfill version, save data to a different version of the timeseries (e.g. "Rev-USGS" instead of "Raw-USGS")',
)
@requires(reqs.cwms, reqs.requests)
def getusgs_timeseries_v2(
    office, days_back, api_root, api_key, api_key_loc, backfill, backfill_version
):
    from cwmscli.usgs.getusgs_cda import getusgs_cda_ogc

    if backfill is not None:
        backfill_list = [item.strip() for item in backfill.split(",") if item.strip()]
    else:
        backfill_list = None

    api_key = get_api_key(api_key, api_key_loc)
    getusgs_cda_ogc(
        api_root=api_root,
        office_id=office,
        days_back=days_back,
        api_key=api_key,
        backfill_tsids=backfill_list,
        backfill_version=backfill_version,
    )


@usgs_group.command("ratings", help="Get USGS ratings and store into CWMS database")
@office_option
@days_back_option
@api_root_option
@api_key_option
@api_key_loc_option
@click.option(
    "-rs",
    "--rating-subset",
    default=None,
    type=str,
    help='subset of rating spec ids to grab latest rating for (e.g. "rating_spec_id1, rating_spec_id2").',
)
@requires(reqs.cwms, reqs.requests, reqs.dataretrieval)
def getusgs_ratings(office, days_back, api_root, api_key, api_key_loc, rating_subset):
    from cwmscli.usgs.getUSGS_ratings_cda import getusgs_rating_cda

    if rating_subset is not None:
        rating_list = [
            item.strip() for item in rating_subset.split(",") if item.strip()
        ]
    else:
        rating_list = None

    api_key = get_api_key(api_key, api_key_loc)
    getusgs_rating_cda(
        api_root=api_root,
        office_id=office,
        days_back=days_back,
        api_key=api_key,
        rating_subset=rating_list,
    )


@usgs_group.command(
    "ratings-ini-file-import",
    help="Store rating ini file information into database to be used with getusgs_ratings",
)
@click.option(
    "-f",
    "--filename",
    required=True,
    type=str,
    help="filename of ratings ini file to be processed",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview changes without updating the database",
)
@api_root_option
@api_key_option
@api_key_loc_option
@requires(reqs.cwms, reqs.requests)
def ratingsinifileimport(filename, dry_run, api_root, api_key, api_key_loc):
    from cwmscli.usgs.rating_ini_file_import import rating_ini_file_import

    api_key = get_api_key(api_key, api_key_loc)
    rating_ini_file_import(
        api_root=api_root, api_key=api_key, ini_filename=filename, dry_run=dry_run
    )


@usgs_group.command("measurements", help="Store USGS measurements into CWMS database")
@click.option(
    "-d",
    "--days-back-modified",
    default=2,
    type=int,
    help="Days back from current time measurements have been modified in USGS database. Can be integer value",
)
@click.option(
    "-c",
    "--days-back-collected",
    default=365,
    type=int,
    help="Days back from current time measurements have been collected. Can be integer value",
)
@office_option
@api_root_option
@api_key_option
@api_key_loc_option
@click.option(
    "-b",
    "--backfill",
    default=None,
    type=str,
    help="Backfill POR data, use list of USGS IDs (e.g. 05057200, 05051300) or the word 'group' to attempt to backfill all sites in the OFFICE id's Data Acquisition->USGS Measurements group",
)
@requires(reqs.cwms, reqs.requests, reqs.dataretrieval)
def getusgs_measurements(
    days_back_modified,
    days_back_collected,
    office,
    api_root,
    api_key,
    api_key_loc,
    backfill,
):
    from cwmscli.usgs.getusgs_measurements_cda import getusgs_measurement_cda

    backfill_group = False
    backfill_list = False
    if backfill is not None:
        if "group" in backfill:
            backfill_group = True
        elif type(backfill) == str:
            backfill_list = [
                item.strip() for item in backfill.split(",") if item.strip()
            ]
    api_key = get_api_key(api_key, api_key_loc)
    getusgs_measurement_cda(
        api_root=api_root,
        office_id=office,
        api_key=api_key,
        days_back_modified=days_back_modified,
        days_back_collected=days_back_collected,
        backfill_list=backfill_list,
        backfill_group=backfill_group,
    )


@usgs_group.command(
    "migrate-timeseries-ids",
    help=(
        "Migrate legacy numeric USGS method IDs in USGS TS Data Acquisition "
        "group alias-id fields to new USGS time_series_id values"
    ),
)
@office_option
@api_root_option
@api_key_option
@api_key_loc_option
@click.option(
    "--output-dir",
    required=True,
    type=click.Path(
        exists=False,
        file_okay=False,
        dir_okay=True,
        writable=True,
    ),
    help="Directory where migration reports and proposed CWMS updates are written.",
)
@click.option(
    "-m",
    "--legacy-methods-csv",
    default=None,
    type=click.Path(
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    help=(
        "Optional legacy method crosswalk CSV. Required columns: "
        "USGS_St_Num, USGS_PARAMETER, methodID, methodDescription. "
        "If omitted, legacy WaterServices is queried."
    ),
)
@click.option(
    "-t",
    "--timeseries-ids",
    default=None,
    type=str,
    help=(
        "Optional comma-separated CWMS TSIDs to migrate. "
        "Use for initial testing before processing the entire office."
    ),
)
@click.option(
    "--apply/--dry-run",
    default=False,
    help=(
        "Apply eligible alias-id updates to CWMS. Default is --dry-run, "
        "which writes reports but changes nothing in CWMS."
    ),
)
@click.option(
    "--legacy-chunk-size",
    default=100,
    type=click.IntRange(min=1),
    show_default=True,
    help="Maximum USGS stations included per legacy WaterServices request.",
)
@click.option(
    "--compare-timeseries/--no-compare-timeseries",
    default=False,
    help=(
        "Compare candidate USGS time_series_id values against existing CWMS "
        "data before allowing an alias-id update."
    ),
)
@click.option(
    "--compare-days",
    default=3,
    type=click.IntRange(min=1),
    show_default=True,
    help="Number of recent days used for CWMS-to-USGS value comparison.",
)
@click.option(
    "--comparison-tolerance",
    default=0.001,
    type=click.FloatRange(min=0.0),
    show_default=True,
    help=(
        "Maximum absolute value difference considered an agreement after "
        "unit normalization."
    ),
)
@click.option(
    "--comparison-min-records",
    default=20,
    type=click.IntRange(min=1),
    show_default=True,
    help="Minimum overlapping CWMS/USGS observations required for validation.",
)
@click.option(
    "--comparison-min-agreement",
    default=95.0,
    type=click.FloatRange(min=0.0, max=100.0),
    show_default=True,
    help="Minimum percentage of overlapping values within tolerance.",
)
@requires(reqs.cwms, reqs.requests, reqs.dataretrieval)
def migrate_usgs_timeseries_ids_command(
    office,
    api_root,
    api_key,
    api_key_loc,
    output_dir,
    legacy_methods_csv,
    timeseries_ids,
    apply,
    legacy_chunk_size,
    compare_timeseries,
    compare_days,
    comparison_tolerance,
    comparison_min_records,
    comparison_min_agreement,
):
    """Migrate legacy USGS method IDs to new USGS time-series IDs."""

    from cwmscli.usgs.migrate_usgs_tsid import migrate_usgs_timeseries_ids

    if timeseries_ids:
        tsid_list = [item.strip() for item in timeseries_ids.split(",") if item.strip()]
    else:
        tsid_list = None

    api_key = get_api_key(api_key, api_key_loc)

    try:
        migrate_usgs_timeseries_ids(
            api_root=api_root,
            office_id=office,
            api_key=api_key,
            output_dir=output_dir,
            legacy_methods_csv=legacy_methods_csv,
            apply=apply,
            timeseries_ids=tsid_list,
            legacy_chunk_size=legacy_chunk_size,
            compare_timeseries=compare_timeseries,
            compare_days=compare_days,
            comparison_tolerance=comparison_tolerance,
            comparison_min_records=comparison_min_records,
            comparison_min_agreement=comparison_min_agreement,
        )

    except Exception as error:
        raise click.ClickException(
            f"USGS time-series-ID migration failed: {error}"
        ) from error
