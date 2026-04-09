import logging
import re
from typing import Dict, List

import cwms
import pandas as pd


def import_shef_critfile(
    file_path: str,
    office_id: str,
    api_root: str,
    api_key: str,
    group_id: str = "SHEF Data Acquisition",
    category_id: str = "Data Acquisition",
    group_office_id: str = "CWMS",
    category_office_id: str = "CWMS",
    replace_assigned_ts: bool = False,
) -> None:
    """
    Processes a .crit file and saves the information to the SHEF Data Acquisition time series group.

    Parameters
    ----------
    file_path : str
        Path to the .crit file.
    office_id : str
        The ID of the office associated with the specified timeseries.
    group_id : str, optional
        The specified group associated with the timeseries data. Defaults to "SHEF Data Acquisition".
    category_id : str, optional
        The category ID that contains the timeseries group. Defaults to "Data Acquisition".
    group_office_id : str, optional
        The specified office group associated with the timeseries data. Defaults to "CWMS".
    replace_assigned_ts : bool, optional
        Specifies whether to unassign all existing time series before assigning new time series specified in the content body. Default is False.

    Returns
    -------
    None
    """

    api_key = "apikey " + api_key
    cwms.api.init_session(api_root=api_root, api_key=api_key)
    logging.info(f"CDA connection: {api_root}")

    # Parse the file and get the parsed data
    parsed_data = parse_crit_file(file_path)
    logging.info("CRIT file has been parsed")
    # df = pd.DataFrame()
    logging.info(f"Saving Timeseries IDs to group: {group_id}")
    for data in parsed_data:
        # Create DataFrame for the current row
        try:
            df = create_df(office_id, data["Timeseries ID"], data["Alias"])

            # Generate JSON dictionary
            json_dict = cwms.timeseries_group_df_to_json(
                data=df,
                group_id=group_id,
                group_office_id=group_office_id,
                category_office_id=category_office_id,
                category_id=category_id,
            )

            cwms.update_timeseries_groups(
                group_id=group_id,
                office_id=office_id,
                replace_assigned_ts=replace_assigned_ts,
                data=json_dict,
            )
            logging.info(
                f'SUCCESS Stored timeseries ID {data["Timeseries ID"]} to {group_id}'
            )
        except Exception as error:
            logging.error(
                f'FAIL Data could not be stored to CWMS database for -->  {data["Timeseries ID"]},{data["Alias"]} error = {error}'
            )


def parse_crit_file(file_path: str) -> List[Dict[str, str]]:
    """
    Parses a .crit file into a dictionary containing timeseries ID and Alias.

    Parameters
    ----------
        file_path : str
                Path to the .crit file.

    Returns
    -------
    List[Dict[str, str]]
        A list of dictionaries with "Alias" and "Timeseries ID" as keys.
    """
    parsed_data = []
    with open(file_path, "r") as file:
        for line in file:
            # Ignore comment lines and empty lines
            if line.startswith("#") or not line.strip():
                continue

            # Extract alias, timeseries ID, and TZ
            match = re.match(r"([^=]+)=([^;]+);(.+)", line.strip())

            if match:
                alias = match.group(1).strip()
                timeseries_id = match.group(2).strip()
                alias2 = match.group(3).strip()

                parsed_data.append(
                    {
                        "Alias": alias + ":" + alias2,
                        "Timeseries ID": timeseries_id,
                    }
                )

    return parsed_data


def create_df(office_id: str, ts_id: str, alias: str) -> pd.DataFrame:
    """
    Appends a row to the DataFrame.

    Parameters
    ----------
        df : pandas.DataFrame
            The DataFrame to append to.
        office_id : str
            The ID of the office associated with the specified timeseries.
        tsId : str
            The timeseries ID from the file.
        alias : str
            The alias from the file.
    Returns
    -------
    pandas.DataFrame
        The updated DataFrame.
    """
    data = {
        "office-id": [office_id],
        "timeseries-id": [ts_id],
        "alias-id": [alias],
    }
    # df = pd.concat([df, pd.DataFrame(data)])
    df = pd.DataFrame(data)
    return df
