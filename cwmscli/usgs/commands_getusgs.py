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

days_back_option = click.option(
    "-d",
    "--days_back",
    default="1",
    type=float,
    help="Days back from current time to get data.  Can be decimal and integer values",
)


@click.command(
    "getusgs-timeseries", help="Get USGS timeseries values and store into CWMS database"
)
@office_option
@days_back_option
@api_root_option
@api_key_option
@api_key_loc_option
@requires(reqs.cwms, reqs.requests)
def getusgs_timeseries(office, days_back, api_root, api_key, api_key_loc):
    from cwmscli.getusgs.getugsg_cda import getusgs_cda

    api_key = get_api_key(api_key, api_key_loc)
    getusgs_cda(
        api_root=api_root,
        office_id=office,
        days_back=days_back,
        api_key=api_key,
    )


@click.command("getusgs-ratings", help="Get USGS ratings and store into CWMS database")
@office_option
@days_back_option
@api_root_option
@api_key_option
@api_key_loc_option
@requires(reqs.cwms, reqs.requests, reqs.dataretrieval)
def getusgs_ratings(office, days_back, api_root, api_key, api_key_loc):
    from cwmscli.getusgs.getUSGS_ratings_CDA import getusgs_rating_cda

    api_key = get_api_key(api_key, api_key_loc)
    getusgs_rating_cda(
        api_root=api_root,
        office_id=office,
        days_back=days_back,
        api_key=api_key,
    )


@click.command(
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
@api_root_option
@api_key_option
@api_key_loc_option
@requires(reqs.cwms, reqs.requests)
def ratingsinifileimport(filename, api_root, api_key, api_key_loc):
    from cwmscli.getusgs.rating_ini_file_import import rating_ini_file_import

    api_key = get_api_key(api_key, api_key_loc)
    rating_ini_file_import(api_root=api_root, api_key=api_key, ini_filename=filename)


@click.command(
    "getusgs-measurements", help="Store USGS measurements into CWMS database"
)
@click.option(
    "-d",
    "--days_back_modified",
    default="2",
    help="Days back from current time measurements have been modified in USGS database. Can be integer value",
)
@click.option(
    "-c",
    "--days_back_collected",
    default="365",
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
    from cwmscli.getusgs.getusgs_measurements_cda import getusgs_measurement_cda

    backfill_group = False
    backfill_list = False
    if backfill is not None:
        if "group" in backfill:
            backfill_group = True
        elif type(args.backfill) == str:
            backfill_list = args.backfill.replace(" ", "").split(",")
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
