# Script Entry File
import json
import os
import sys
import time
import traceback
from datetime import datetime, timedelta

import cwms

# Add the current directory to the path
# This is necessary for the script to be run as a standalone script
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))


# Handle imports for local and package use
# This is necessary for the script to be run as a package or as a standalone script
# The script can be run as a standalone script by running `python -m scada_ts` from the parent directory
# or as a package by running `python scada_ts` from the parent directory
try:
    # Relative imports for modules
    from . import __author__, __license__, __version__
    from .utils import (
        colorize,
        colorize_count,
        determine_interval,
        eval_expression,
        load_csv,
        logger,
        parse_date,
        read_config,
        safe_zoneinfo,
        setup_logger,
    )
except ImportError:
    from __init__ import __author__, __license__, __version__
    from utils import (
        colorize,
        colorize_count,
        determine_interval,
        eval_expression,
        load_csv,
        logger,
        parse_date,
        read_config,
        safe_zoneinfo,
        setup_logger,
    )

# Load environment variables
API_KEY = os.getenv("CDA_API_KEY")
OFFICE = os.getenv("CDA_OFFICE", "SWT")
HOST = os.getenv("CDA_HOST")
LOOKBACK_DAYS = int(os.getenv("CDA_LOOKBACK_DAYS", 5))  # Default to 5 days if not set

if [API_KEY, OFFICE, HOST].count(None) > 0:
    raise ValueError(
        "Environment variables CDA_API_KEY, CDA_OFFICE, and CDA_HOST must be set."
    )


def parse_file(file_path, begin_time, lookback, timezone="GMT"):
    csv_data = load_csv(file_path)
    header = csv_data[0]
    data = csv_data[1:]
    ts_data = {}
    lookback_datetime = begin_time - timedelta(hours=lookback)
    logger.debug(f"Begin time: {begin_time}")
    logger.debug(f"Lookback datetime: {lookback_datetime}")
    for row in data:
        # Skip empty rows or rows without a timestamp
        if not row:
            continue
        row_datetime = parse_date(row[0], tz_str=timezone)
        # Skip rows that are before/older than the lookback period and after the begin time
        logger.debug(f"Row datetime: {row_datetime}")
        if row_datetime < lookback_datetime or row_datetime > begin_time:
            continue
        # Guarantee only one entry per timestamp
        ts_data[int(row_datetime.timestamp())] = row
    return {"header": header, "data": ts_data}


def load_timeseries(file_data, project, config):
    header = file_data.get("header", [])
    data = file_data.get("data", {})

    if not header or not data:
        raise ValueError(
            "No data found in the CSV file for the range selected: check the --lookback period and/or --begin time. You will also want to ensure you set the timezone of the CSV file with --tz America/Chicago or similar."
        )

    ts_config = config["projects"][project]["timeseries"]
    project_ts = []

    # Interval in seconds
    interval = config.get("interval")
    if not interval:
        interval = determine_interval(data, 10)
        logger.warning(
            f"Interval not found in configuration. Determined interval: {interval} seconds."
        )
    start_epoch = min(data.keys())
    end_epoch = max(data.keys())

    # Map column names to indexes (case-insensitive)
    header_map = {col.strip().lower(): i for i, col in enumerate(header)}
    logger.debug(f"Header map (column name -> index): {header_map}")

    for name, meta in ts_config.items():
        expr = meta["columns"]
        units = meta.get("units", "")
        precision = meta.get("precision", 2)
        values = []
        epoch = start_epoch
        while epoch <= end_epoch:
            row = data.get(epoch)
            if row:
                value = eval_expression(expr, row, header_map)
                value = round(value, precision) if value is not None else None
                quality = 3 if value is not None else 5
            else:
                value = None
                quality = 5
            logger.debug(
                f"[{name}] {datetime.fromtimestamp(epoch)} -> {value} (quality: {quality})"
            )
            values.append([epoch * 1000, value, quality])
            # Convert seconds to minutes
            epoch += interval

        ts_obj = {"name": name, "units": units, "values": values}
        valid = sum(1 for _, v, _ in values if v is not None)
        total = len(values)
        logger.info(
            f"Built timeseries {colorize(name, 'blue')} with {colorize_count(valid, total)} valid points."
        )
        logger.debug(
            f"Timeseries {name} data range: {colorize(datetime.fromtimestamp(start_epoch), 'blue')} to {colorize(datetime.fromtimestamp(end_epoch), 'blue')}"
        )
        project_ts.append(ts_obj)

    return project_ts


def config_check(config):
    """Checks a configuration file for required keys"""
    if not config.get("interval"):
        logger.warning(
            "Configuration file does not contain an 'interval' key (and value in seconds), this is recommended per CSV file to avoid ambiguity."
        )
    if not config.get("projects"):
        raise ValueError("Configuration file must contain a 'projects' key.")
    for proj, proj_data in config.get("projects").items():
        # Only check the specified project or if all projects are specified
        if proj != "all" and proj != proj.lower():
            continue
        if not proj_data.get("timeseries"):
            raise ValueError(
                f"Configuration file must contain a 'timeseries' key for project '{proj}'."
            )
        for ts_name, ts_data in proj_data.get("timeseries").items():
            if not ts_data.get("columns"):
                raise ValueError(
                    f"Configuration file must contain a 'columns' key for timeseries '{ts_name}' in project '{proj}'."
                )


def main(*args, **kwargs):
    """
    Main function to execute the scada_ts script.
    This function serves as the entry point for the script.
    """
    start_time = time.time()
    tz = safe_zoneinfo(kwargs.get("tz"))
    if kwargs.get("begin"):
        try:
            begin_time = datetime.strptime(
                kwargs.get("begin"), "%Y-%m-%dT%H:%M"
            ).replace(tzinfo=tz)
        except ValueError:
            raise ValueError("--begin must be in format YYYY-MM-DDTHH:MM")
    else:
        begin_time = datetime.now(tz)

    cwms.api.init_session(
        api_root=kwargs.get("api_root"), api_key=kwargs.get("api_key")
    )
    # Setup the logger if a path is provided
    setup_logger(kwargs.get("log"), verbose=kwargs.get("verbose"))
    logger.info(f"Begin time: {begin_time}")
    logger.debug(f"Timezone: {tz}")
    logger.debug(f"Lookback period: {kwargs.get("lookback")} hours")
    # Override environment variables if provided in CLI
    if kwargs.get("coop"):
        HOST = os.getenv("CDA_COOP_HOST")
        if not HOST:
            raise ValueError(
                "Environment variable CDA_COOP_HOST must be set to use --coop flag."
            )
    config = read_config(kwargs.get("config_path"))
    config_check(config)
    PROJECTS = config.get("projects")
    # Override projects if one is specified in CLI
    if kwargs.get("project"):
        if kwargs.get("project") == "all":
            PROJECTS = config.get("projects", {}).keys()
        else:
            PROJECTS = [kwargs.get("project")]
    if not PROJECTS:
        raise ValueError("Configuration file must contain a 'projects' key.")
    logger.info(f"Started for {','.join(PROJECTS)} projects.")
    # Input checks
    # if kwargs.get("project") != "all" and kwargs.get("project") not in PROJECTS:
    #     raise ValueError(
    #         f"Invalid project name '{kwargs.get("project")}'. Valid options are: {', '.join(PROJECTS)}"
    #     )
    if kwargs.get("lookback") < 0:
        raise ValueError("Lookback period must be a non-negative integer.")

    # Loop the projects and post the data
    for proj in PROJECTS:
        HYDRO_DIR = config.get("projects", {}).get(proj, {}).get("dir", "")

        # Check if the user wants to override the data file name from what is in the config
        DATA_FILE = kwargs.get("data_file") or config.get("projects", {}).get(
            proj, {}
        ).get("file", "")
        if not DATA_FILE:
            logger.warning(
                f"No data file specified for project '{proj}'. {colorize(f'Skipping {proj}', 'red')}. Please provide a valid CSV file path using --data_file or ensure the 'file' key is set in the config."
            )
            continue
        csv_data = parse_file(
            os.path.join(kwargs.get("data_path"), HYDRO_DIR, DATA_FILE),
            begin_time,
            kwargs.get("lookback"),
            kwargs.get("tz"),
        )
        ts_min_data = load_timeseries(csv_data, proj, config)

        if kwargs.get("dry_run"):
            logger.info("DRY RUN enabled. No data will be posted")
        for ts_object in ts_min_data:
            try:
                ts_object.update({"office-id": kwargs.get("office")})
                if kwargs.get("dry_run"):
                    logger.info(f"DRY RUN: {ts_object}")
                else:
                    cwms.store_timeseries(
                        data=ts_object,
                        store_rule=kwargs.get("store_rule", "REPLACE_ALL"),
                    )
                    logger.info(f"Stored {ts_object['name']} values")
            except Exception as e:
                logger.error(
                    f"Error posting data for {proj}: {e}\n{traceback.format_exc()}"
                )

    logger.debug(f"\tExecution time: {round(time.time() - start_time, 3)} seconds.")
    logger.debug(f"\tMemory usage: {round(os.sys.getsizeof(locals()) / 1024, 2)} KB")


if __name__ == "__main__":
    main()
