# Script Entry File
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

if [API_KEY, OFFICE, HOST].count(None) > 0:
    raise ValueError(
        "Environment variables CDA_API_KEY, CDA_OFFICE, and CDA_HOST must be set."
    )


def parse_file(file_path, begin_time, date_format, timezone="GMT"):
    csv_data = load_csv(file_path)
    header = csv_data[0]
    data = csv_data[1:]
    ts_data = {}
    logger.debug(f"Begin time: {begin_time}")
    for row in data:
        # Skip empty rows or rows without a timestamp
        if not row:
            continue
        row_datetime = parse_date(row[0], tz_str=timezone, date_format=date_format)
        # Guarantee only one entry per timestamp
        ts_data[int(row_datetime.timestamp())] = row
    return {"header": header, "data": ts_data}


def load_timeseries(file_data, file_key, config):
    header = file_data.get("header", [])
    data = file_data.get("data", {})

    if not header or not data:
        raise ValueError(
            "No data found in the CSV file for the range selected. Please ensure you set the timezone of the CSV file with --tz America/Chicago or similar."
        )

    ts_config = config["input_files"][file_key]["timeseries"]
    file_ts = []

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
        file_ts.append(ts_obj)

    return file_ts


def config_check(config):
    """Checks a configuration file for required keys"""
    if not config.get("interval"):
        logger.warning(
            "Configuration file does not contain an 'interval' key (and value in seconds), this is recommended per CSV file to avoid ambiguity."
        )
    if config.get("projects"):
        logger.warning(
            "Configuration file contains a 'projects' key, this has been renamed to 'input_files' for clarity. Continuing for backwards compatibility."
        )
        config["input_files"] = config.pop("projects")
    if not config.get("input_files"):
        raise ValueError("Configuration file must contain an 'input_files' key.")
    for file_key, file_data in config.get("input_files").items():
        # Only check the specified keys or if all keys are specified
        if file_key != "all" and file_key != file_key.lower():
            continue
        if not file_data.get("timeseries"):
            raise ValueError(
                f"Configuration file must contain a 'timeseries' key for file '{file_key}'."
            )
        for ts_name, ts_data in file_data.get("timeseries").items():
            if not ts_data.get("columns"):
                raise ValueError(
                    f"Configuration file must contain a 'columns' key for timeseries '{ts_name}' in file '{file_key}'."
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
    # Override environment variables if provided in CLI
    if kwargs.get("coop"):
        HOST = os.getenv("CDA_COOP_HOST")
        if not HOST:
            raise ValueError(
                "Environment variable CDA_COOP_HOST must be set to use --coop flag."
            )
    config_path = kwargs.get("config_path")
    config = read_config(config_path)
    config_check(config)
    INPUT_FILES = config.get("input_files", {})
    # Override file names if one is specified in CLI
    if kwargs.get("input_keys"):
        if kwargs.get("input_keys") == "all":
            INPUT_FILES = config.get("input_files", {}).keys()
        else:
            INPUT_FILES = kwargs.get("input_keys").split(",")
    logger.info(f"Started for {','.join(INPUT_FILES)} input files.")
    # Input checks
    # if kwargs.get("file_name") != "all" and kwargs.get("file_name") not in INPUT_FILES:
    #     raise ValueError(
    #         f"Invalid file name '{kwargs.get("file_name")}'. Valid options are: {', '.join(INPUT_FILES)}"
    #     )

    # Loop the file names and post the data
    for file_name in INPUT_FILES:
        # Grab the csv file path from the config
        CONFIG_ITEM = config.get("input_files", {}).get(file_name, {})
        DATA_FILE = CONFIG_ITEM.get("data_path", "")
        if not DATA_FILE:
            logger.warning(
                # TODO: List URL to example in doc site once available
                f"No data file specified for input-keys '{file_name}' in {config_path}. {colorize(f'Skipping {file_name}', 'red')}. Please provide a valid CSV file path by ensuring the 'data_path' key is set in the config."
            )
            continue
        csv_data = parse_file(
            DATA_FILE,
            begin_time,
            CONFIG_ITEM.get("date_format"),
            kwargs.get("tz"),
        )
        try:
            ts_min_data = load_timeseries(csv_data, file_name, config)
        except ValueError as e:
            logger.error(f"Error loading timeseries for {file_name}: {e}")
            continue

        if kwargs.get("dry_run"):
            logger.info("DRY RUN enabled. No data will be posted")
        for ts_object in ts_min_data:
            try:
                ts_object.update({"office-id": kwargs.get("office")})
                logger.info(
                    "Store Rule: " + CONFIG_ITEM.get("store_rule", "")
                    if CONFIG_ITEM.get("store_rule", "")
                    else f"No Store Rule specified, will default to REPLACE_ALL in {config_path}."
                )
                if kwargs.get("dry_run"):
                    logger.info(f"DRY RUN: {ts_object}")
                else:
                    cwms.store_timeseries(
                        data=ts_object,
                        store_rule=CONFIG_ITEM.get("store_rule", "REPLACE_ALL"),
                    )
                    logger.info(f"Stored {ts_object['name']} values")
            except Exception as e:
                logger.error(
                    f"Error posting data for {file_name}: {e}\n{traceback.format_exc()}"
                )

    logger.debug(f"\tExecution time: {round(time.time() - start_time, 3)} seconds.")
    logger.debug(f"\tMemory usage: {round(os.sys.getsizeof(locals()) / 1024, 2)} KB")


if __name__ == "__main__":
    main()
