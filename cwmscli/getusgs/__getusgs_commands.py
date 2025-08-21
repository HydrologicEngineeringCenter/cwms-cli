import click
from cwmscli.getusgs.getUSGS_CDA import getusgs_cda
from cwmscli.getusgs.getUSGS_ratings_CDA import getusgs_rating_cda
from cwmscli.getusgs.rating_ini_file_import import rating_ini_file_import
from cwmscli.getusgs.get_USGS_measurements import getUSGS_measurement_cda

days_back_option = click.option("-d", "--days_back", default="1", type = float, help="Days back from current time to get data.  Can be decimal and integer values")
office_option = click.option("-o", "--office", required=True, envvar='OFFICE', type=str, help="Office to grab data for")
api_root_option = click.option("-a", "--api_root", required=True, envvar='CDA_API_ROOT', type=str, help="Api Root for CDA. Can be user defined or placed in a env variable CDA_API_ROOT")
api_key_option = click.option("-k", "--api_key", default=None, type=str, envvar='CDA_API_KEY', help="api key for CDA. Can be user defined or place in env variable CDA_API_KEY. one of api_key or api_key_loc are required")
api_key_loc_option = click.option("-kl", "--api_key_loc", default=None, type=str, help="file storing Api Key. One of api_key or api_key_loc are required")


def get_api_key(api_key:str, api_key_loc:str) -> str:
    if api_key is not None:
        return api_key   
    elif api_key_loc is not None:
        with open(api_key_loc, "r") as f:
            return f.readline().strip()
    else:
        raise Exception("must add a value to either --api_key(-k) or --api_key_loc(-kl)") 

@click.command(help = "Get USGS timeseries values and store into CWMS database")
@office_option
@days_back_option
@api_root_option
@api_key_option
@api_key_loc_option
def getusgs_timeseries(office, days_back, api_root, api_key, api_key_loc):
    
    api_key = get_api_key(api_key, api_key_loc)
    getusgs_cda(
                api_root=api_root,
                office_id=office,
                days_back=days_back,
                api_key=api_key,
            )
    

@click.command(help = "Get USGS ratings and store into CWMS database")
@office_option
@days_back_option
@api_root_option
@api_key_option
@api_key_loc_option
def getusgs_ratings(office, days_back, api_root, api_key, api_key_loc):
    
    api_key = get_api_key(api_key, api_key_loc)
    getusgs_rating_cda(
                api_root=api_root,
                office_id=office,
                days_back=days_back,
                api_key=api_key,
            )
    



@click.command(help = "Store rating ini file information into database to be used with getusgs_ratings")
@click.option("-f", "--filename", required=True, type=str, help="filename of ini file to be processed")
@api_root_option
@api_key_option
@api_key_loc_option
def getusgs_ratings_INIFileImport(filename, api_root, api_key, api_key_loc):
    
    api_key = get_api_key(api_key, api_key_loc)
    rating_ini_file_import(
                api_root=api_root,
                api_key=api_key,
                ini_filename=filename
            )
    



@click.command(help = "Store USGS measurements into CWMS database")
@click.option(
    "-d",
        "--days_back_modified",
        default="2",
        help="Days back from current time measurements have been modified in USGS database. Can be integer value"
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
def getusgs_measurements(days_back_modified,days_back_collected,office,api_root,api_key,api_key_loc,backfill):
    backfill_group = False
    backfill_list = False
    if backfill is not None:
        if "group" in backfill:
            backfill_group = True
        elif type(args.backfill) == str:
            backfill_list = args.backfill.replace(" ", "").split(",")
    api_key = get_api_key(api_key, api_key_loc)
    getUSGS_measurement_cda(
        api_root=api_root,
        office_id=office,
        api_key=api_key,
        days_back_modified=days_back_modified,
        days_back_collected=days_back_collected,
        backfill_list=backfill_list,
        backfill_group=backfill_group,
    )