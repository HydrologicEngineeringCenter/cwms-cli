from cwmscli.utils.colors import c

VALID_USE_IF_MULTIPLE = {"first", "last", "average", "error"}


def resolve_use_if_multiple(config, file_config):
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
    if not config.get("input_files"):
        raise ValueError("Configuration file must contain an 'input_files' key.")
    for file_key, file_data in config.get("input_files").items():
        resolve_use_if_multiple(config, file_data)
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


def resolve_input_files(config, input_keys):
    input_files = config.get("input_files", {})
    if input_keys:
        if input_keys == "all":
            return config.get("input_files", {}).keys()
        return input_keys.split(",")
    return input_files
