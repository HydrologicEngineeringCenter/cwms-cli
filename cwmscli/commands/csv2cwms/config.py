from cwmscli.utils.colors import c

from .doclinks import COMPLETE_CONFIG_DOC_URL, with_doc_links

VALID_USE_IF_MULTIPLE = {"first", "last", "average", "error"}
TOP_LEVEL_CONFIG_KEYS = {
    "interval",
    "round_to_nearest",
    "use_if_multiple",
    "input_files",
    "projects",
}
FILE_CONFIG_KEYS = {
    "data_path",
    "store_rule",
    "date_col",
    "date_format",
    "round_to_nearest",
    "use_if_multiple",
    "timeseries",
}
TIMESERIES_CONFIG_KEYS = {"columns", "units", "precision"}


def _raise_invalid_keys(level_name, owner_name, invalid_keys):
    invalid = ", ".join(sorted(invalid_keys))
    owner = f" for {owner_name}" if owner_name else ""
    raise ValueError(
        with_doc_links(
            f"Invalid configuration key(s) {c(invalid, 'yellow')} found in {level_name}{owner}.",
            COMPLETE_CONFIG_DOC_URL,
        )
    )


def _validate_allowed_keys(config, logger):
    invalid_top_level = set(config) - TOP_LEVEL_CONFIG_KEYS
    if invalid_top_level:
        _raise_invalid_keys("top-level config", None, invalid_top_level)

    input_files = config.get("input_files", {})
    for file_key, file_data in input_files.items():
        invalid_file_keys = set(file_data) - FILE_CONFIG_KEYS
        if invalid_file_keys:
            _raise_invalid_keys("input file config", file_key, invalid_file_keys)

        timeseries = file_data.get("timeseries", {})
        for ts_name, ts_data in timeseries.items():
            invalid_ts_keys = set(ts_data) - TIMESERIES_CONFIG_KEYS
            if invalid_ts_keys:
                _raise_invalid_keys("timeseries config", ts_name, invalid_ts_keys)


def resolve_use_if_multiple(config, file_config):
    # File-specific setting takes precedence over global setting, default to "error" if not set
    strategy = file_config.get(
        "use_if_multiple", config.get("use_if_multiple", "error")
    )
    normalized = str(strategy).strip().lower()
    if normalized not in VALID_USE_IF_MULTIPLE:
        valid = ", ".join(sorted(VALID_USE_IF_MULTIPLE))
        raise ValueError(
            with_doc_links(
                f"Invalid use_if_multiple value {c(str(strategy), 'yellow')}. Expected one of {c(valid, 'cyan')}.",
                COMPLETE_CONFIG_DOC_URL,
            )
        )
    return normalized


def config_check(config, logger):
    """Checks a configuration file for required keys."""
    resolve_use_if_multiple(config, {})
    if not config.get("interval"):
        logger.warning(
            "Configuration file does not contain an 'interval' key (and value in seconds), this is recommended per CSV file to avoid ambiguity."
        )
    if config.get("projects"):
        logger.warning(
            "Configuration file contains a 'projects' key, this has been renamed to 'input_files' for clarity. Continuing for backwards compatibility."
        )
        config["input_files"] = config.pop("projects")
    _validate_allowed_keys(config, logger)
    if not config.get("input_files"):
        raise ValueError(
            with_doc_links(
                "Configuration file must contain an 'input_files' key.",
                COMPLETE_CONFIG_DOC_URL,
            )
        )
    for file_key, file_data in config.get("input_files").items():
        resolve_use_if_multiple(config, file_data)
        # Only check the specified keys or if all keys are specified
        if file_key != "all" and file_key != file_key.lower():
            continue
        if not file_data.get("timeseries"):
            raise ValueError(
                with_doc_links(
                    f"Configuration file must contain a 'timeseries' key for file '{file_key}'.",
                    COMPLETE_CONFIG_DOC_URL,
                )
            )
        for ts_name, ts_data in file_data.get("timeseries").items():
            if not ts_data.get("columns"):
                raise ValueError(
                    with_doc_links(
                        f"Configuration file must contain a 'columns' key for timeseries '{ts_name}' in file '{file_key}'.",
                        COMPLETE_CONFIG_DOC_URL,
                    )
                )


def resolve_input_files(config, input_keys):
    input_files = config.get("input_files", {})
    if input_keys:
        if input_keys == "all":
            return config.get("input_files", {}).keys()
        return input_keys.split(",")
    return input_files
