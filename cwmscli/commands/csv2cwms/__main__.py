# Script Entry File
import os
import sys
import time
from datetime import datetime

import cwms

from cwmscli.utils import init_cwms_session

# Add the current directory to the path
# This is necessary for the script to be run as a standalone script
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    from cwmscli.utils.colors import c

    from . import __author__, __license__, __version__
    from .config import config_check as _config_check
    from .config import resolve_input_files
    from .parser import parse_file as _parse_file
    from .transform import load_timeseries as _load_timeseries
    from .utils import logger, read_config, safe_zoneinfo, setup_logger
    from .writer import write_timeseries
except ImportError:
    from parser import parse_file as _parse_file

    from __init__ import __author__, __license__, __version__
    from config import config_check as _config_check
    from config import resolve_input_files
    from transform import load_timeseries as _load_timeseries
    from utils import logger, read_config, safe_zoneinfo, setup_logger
    from writer import write_timeseries

    from cwmscli.utils.colors import c


def parse_file(file_path, begin_time, date_format, timezone="GMT", file_config=None):
    return _parse_file(
        file_path,
        begin_time,
        date_format,
        timezone=timezone,
        file_config=file_config,
        logger=logger,
    )


def load_timeseries(file_data, file_key, config):
    return _load_timeseries(file_data, file_key, config, logger)


def config_check(config):
    return _config_check(config, logger)


def _resolve_begin_time(tz, begin):
    if begin:
        try:
            return datetime.strptime(begin, "%Y-%m-%dT%H:%M").replace(tzinfo=tz)
        except ValueError as err:
            raise ValueError("--begin must be in format YYYY-MM-DDTHH:MM") from err
    return datetime.now(tz)


def main(*args, **kwargs):
    """
    Main function to execute the scada_ts script.
    This function serves as the entry point for the script.
    """
    start_time = time.time()
    tz = safe_zoneinfo(kwargs.get("tz"))
    begin_time = _resolve_begin_time(tz, kwargs.get("begin"))

    init_cwms_session(
        cwms, api_root=kwargs.get("api_root"), api_key=kwargs.get("api_key")
    )
    setup_logger(kwargs.get("log"), verbose=kwargs.get("verbose"))
    logger.info(f"Begin time: {begin_time}")
    logger.info(f"Timezone: {c(str(tz), 'cyan')}")

    if kwargs.get("coop"):
        host = os.getenv("CDA_COOP_HOST")
        if not host:
            raise ValueError(
                "Environment variable CDA_COOP_HOST must be set to use --coop flag."
            )

    config_path = kwargs.get("config_path")
    config = read_config(config_path)
    config_check(config)
    input_files = resolve_input_files(config, kwargs.get("input_keys"))
    logger.info(f"Started for {','.join(input_files)} input files.")

    for file_name in input_files:
        config_item = config.get("input_files", {}).get(file_name, {})
        data_file = config_item.get("data_path", "")
        if not data_file:
            logger.warning(
                f"No data file specified for input-keys '{file_name}' in {config_path}. {c(f'Skipping {file_name}', 'red')}. Please provide a valid CSV file path by ensuring the 'data_path' key is set in the config."
            )
            continue

        csv_data = parse_file(
            data_file,
            begin_time,
            config_item.get("date_format"),
            kwargs.get("tz"),
            config_item,
        )
        try:
            ts_data = load_timeseries(csv_data, file_name, config)
        except ValueError as err:
            logger.error(f"Error loading timeseries for {file_name}: {err}")
            continue

        write_timeseries(
            file_name=file_name,
            ts_data=ts_data,
            config_item=config_item,
            office=kwargs.get("office"),
            dry_run=kwargs.get("dry_run"),
            config_path=config_path,
            logger=logger,
        )

    logger.debug(f"\tExecution time: {round(time.time() - start_time, 3)} seconds.")
    logger.debug(f"\tMemory usage: {round(os.sys.getsizeof(locals()) / 1024, 2)} KB")


if __name__ == "__main__":
    main()
