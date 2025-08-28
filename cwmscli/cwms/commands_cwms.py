import click

from cwmscli.cwms.shef_critfile_import import import_shef_critfile
from cwmscli.utils import (
    api_key_loc_option,
    api_key_option,
    api_root_option,
    get_api_key,
    office_option,
)


@click.command(
    "shefcritimport", help="Get USGS timeseries values and store into CWMS database"
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
def shefcritimport(filename, office, api_root, api_key, api_key_loc):

    api_key = get_api_key(api_key, api_key_loc)
    import_shef_critfile(
        file_path=filename,
        office_id=office,
        api_root=api_root,
        api_key=api_key,
    )
