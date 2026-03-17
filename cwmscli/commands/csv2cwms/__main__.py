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
    from cwmscli.utils.colors import c

    from . import __author__, __license__, __version__
    from .utils import (
        determine_interval,
        eval_expression,
        expression_columns,
        interval_parameter_to_seconds,
        load_csv,
        logger,
        parse_date,
        read_config,
        round_datetime_to_interval,
        safe_zoneinfo,
        setup_logger,
    )
except ImportError:
    from __init__ import __author__, __license__, __version__
    from utils import (
        determine_interval,
        eval_expression,
        expression_columns,
        interval_parameter_to_seconds,
        load_csv,
        logger,
        parse_date,
        read_config,
        round_datetime_to_interval,
        safe_zoneinfo,
        setup_logger,
    )

    from cwmscli.utils.colors import c

# Load environment variables
API_KEY = os.getenv("CDA_API_KEY")
OFFICE = os.getenv("CDA_OFFICE", "SWT")
HOST = os.getenv("CDA_HOST")

if [API_KEY, OFFICE, HOST].count(None) > 0:
    raise ValueError(
        "Environment variables CDA_API_KEY, CDA_OFFICE, and CDA_HOST must be set."
    )

VALID_USE_IF_MULTIPLE = {"first", "last", "average", "error"}


def _normalize_epoch_rows(data):
    normalized = {}
    for epoch, rows in data.items():
        # If the value is already a list of rows, keep it as is. Otherwise, wrap it in a list.
        if isinstance(rows, list) and rows and isinstance(rows[0], list):
            normalized[epoch] = rows
        else:
            normalized[epoch] = [rows]
    return normalized


def _resolve_use_if_multiple(config, file_config):
    # File-specific setting takes precedence over global setting, default to "error" if not set
    strategy = file_config.get(
        "use_if_multiple", config.get("use_if_multiple", "error")
    )
    normalized = str(strategy).strip().lower()
    if normalized not in VALID_USE_IF_MULTIPLE:
        valid = ", ".join(sorted(VALID_USE_IF_MULTIPLE))
        raise ValueError(
            f"Invalid use_if_multiple value {c(str(strategy), 'yellow')}. Expected one of {c(valid, 'cyan')}."
        )
    return normalized


def _select_value(name, epoch, rows, expr, header_map, precision, strategy, timezone):
    raw_values = [eval_expression(expr, row, header_map) for row in rows]

    if len(raw_values) > 1:
        logger.warning(
            f"Multiple values found [{c(name, 'blue')}] at "
            f"{c(str(datetime.fromtimestamp(epoch, tz=timezone)), 'cyan')}; "
            f"using [{c(strategy, 'yellow')}]."
        )

    if strategy == "error" and len(raw_values) > 1:
        raise ValueError(
            f"Multiple values found for timeseries {c(name, 'blue')} at "
            f"{c(str(datetime.fromtimestamp(epoch, tz=timezone)), 'cyan')}. "
            "Set use_if_multiple to first, last, or average."
        )

    if strategy == "first":
        value = raw_values[0]
    elif strategy == "last":
        value = raw_values[-1]
    elif strategy == "average":
        numeric_values = [value for value in raw_values if value is not None]
        value = sum(numeric_values) / len(numeric_values) if numeric_values else None
    else:
        value = raw_values[-1]

    value = round(value, precision) if value is not None else None
    quality = 3 if value is not None else 5
    return value, quality


def parse_file(file_path, begin_time, date_format, timezone="GMT"):
    csv_data = load_csv(file_path)
    header = csv_data[0]
    data = csv_data[1:]
    ts_data = {}
    source_timezone = safe_zoneinfo(timezone)
    logger.debug(f"Begin time: {begin_time}")
    for row in data:
        # Skip empty rows or rows without a timestamp
        if not row:
            continue
        row_datetime = parse_date(row[0], tz_str=timezone, date_format=date_format)
        ts_data.setdefault(int(row_datetime.timestamp()), []).append(row)
    return {"header": header, "data": ts_data, "source_timezone": source_timezone}


def load_timeseries(file_data, file_key, config):
    header = file_data.get("header", [])
    data = _normalize_epoch_rows(file_data.get("data", {}))
    source_timezone = file_data.get("source_timezone", safe_zoneinfo("UTC"))

    if not header or not data:
        raise ValueError(
            "No data found in the CSV file for the range selected. Please ensure you set the timezone of the CSV file with --tz America/Chicago or similar."
        )

    ts_config = config["input_files"][file_key]["timeseries"]
    file_ts = []
    file_config = config["input_files"][file_key]
    round_to_nearest = file_config.get(
        "round_to_nearest", config.get("round_to_nearest", False)
    )
    use_if_multiple = _resolve_use_if_multiple(config, file_config)

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
    available_columns = [col.strip() for col in header]

    missing_columns = []
    for name, meta in ts_config.items():
        column_config = meta["columns"]
        expr_columns = expression_columns(column_config)
        missing_for_expr = [
            col for col in expr_columns if col.strip().lower() not in header_map
        ]
        if missing_for_expr:
            missing_columns.append(
                (name, column_config, expr_columns, missing_for_expr)
            )

    if missing_columns:
        details = []
        for (
            name,
            column_config,
            referenced_columns,
            missing_for_expr,
        ) in missing_columns:
            config_label = (
                "column" if len(referenced_columns) == 1 else "column expression"
            )
            details.append(
                "Timeseries "
                f"{c(name, 'blue')}: configured {config_label} {c(column_config, 'yellow')} "
                f"references missing CSV columns {c(', '.join(missing_for_expr), 'red')}"
            )

        raise ValueError(
            "Configured CSV columns were not found in the input file. "
            f"Skipping {c(file_key, 'red')}.\n"
            + "\n".join(details)
            + "\n"
            + "Available CSV columns: "
            + c(", ".join(available_columns), "cyan")
        )

    for name, meta in ts_config.items():
        expr = meta["columns"]
        units = meta.get("units", "")
        precision = meta.get("precision", 2)
        ts_data = data
        ts_interval = interval

        if round_to_nearest:
            interval_parameter = name.split(".")[3] if len(name.split(".")) > 3 else ""
            if not interval_parameter:
                raise ValueError(
                    f"Unable to determine interval from timeseries {c(name, 'blue')} for round_to_nearest."
                )
            try:
                ts_interval = interval_parameter_to_seconds(interval_parameter)
            except ValueError as err:
                raise ValueError(
                    f"Unable to determine rounding interval from timeseries {c(name, 'blue')}: {c(str(err), 'red')}"
                ) from err

            rounded_data = {}
            for raw_epoch, raw_rows in data.items():
                rounded_epoch = int(
                    round_datetime_to_interval(
                        datetime.fromtimestamp(raw_epoch, tz=source_timezone),
                        interval_parameter,
                    ).timestamp()
                )
                rounded_data.setdefault(rounded_epoch, []).extend(raw_rows)
            ts_data = rounded_data
            logger.info(
                f"Rounding timestamps for {c(name, 'blue')} to nearest {c(interval_parameter, 'cyan')}."
            )

        values = []
        ts_start_epoch = min(ts_data.keys())
        ts_end_epoch = max(ts_data.keys())
        epoch = ts_start_epoch
        while epoch <= ts_end_epoch:
            rows = ts_data.get(epoch)
            if rows:
                value, quality = _select_value(
                    name,
                    epoch,
                    rows,
                    expr,
                    header_map,
                    precision,
                    use_if_multiple,
                    source_timezone,
                )
            else:
                value = None
                quality = 5
            logger.debug(
                f"[{name}] {datetime.fromtimestamp(epoch)} -> {value} (quality: {quality})"
            )
            values.append([epoch * 1000, value, quality])
            # Convert seconds to minutes
            epoch += ts_interval

        ts_obj = {"name": name, "units": units, "values": values}
        valid = sum(1 for _, v, _ in values if v is not None)
        total = len(values)
        percent = valid / total if total else 0
        count_color = "red" if valid == 0 else "green" if percent >= 0.95 else "yellow"
        logger.info(
            f"Built timeseries {c(name, 'blue')} with {c(f'{valid}/{total}', count_color)} valid points."
        )
        logger.debug(
            f"Timeseries {name} data range: {c(str(datetime.fromtimestamp(ts_start_epoch)), 'blue')} to {c(str(datetime.fromtimestamp(ts_end_epoch)), 'blue')}"
        )
        file_ts.append(ts_obj)

    return file_ts


def config_check(config):
    """Checks a configuration file for required keys"""
    _resolve_use_if_multiple(config, {})
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
        _resolve_use_if_multiple(config, file_data)
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
    logger.info(f"Timezone: {c(str(tz), 'cyan')}")
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
                f"No data file specified for input-keys '{file_name}' in {config_path}. {c(f'Skipping {file_name}', 'red')}. Please provide a valid CSV file path by ensuring the 'data_path' key is set in the config."
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
