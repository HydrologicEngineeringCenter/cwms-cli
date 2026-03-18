from datetime import datetime, timedelta

from cwmscli.utils.colors import c

from .config import resolve_use_if_multiple
from .utils import (
    determine_interval,
    eval_expression,
    expression_columns,
    interval_parameter_to_seconds,
    round_datetime_to_interval,
    safe_zoneinfo,
)


def round_epoch_to_interval_seconds(epoch, interval_seconds, timezone):
    dt = datetime.fromtimestamp(epoch, tz=timezone)
    anchor = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    elapsed = (dt - anchor).total_seconds()
    rounded_seconds = (
        (elapsed + interval_seconds / 2) // interval_seconds
    ) * interval_seconds
    return int((anchor + timedelta(seconds=rounded_seconds)).timestamp())


def normalize_epoch_rows(data):
    normalized = {}
    for epoch, rows in data.items():
        # If the value is already a list of rows, keep it as is. Otherwise, wrap it in a list.
        if isinstance(rows, list) and rows and isinstance(rows[0], list):
            normalized[epoch] = rows
        else:
            normalized[epoch] = [rows]
    return normalized


def select_value(
    name, epoch, rows, expr, header_map, precision, strategy, timezone, logger
):
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


def load_timeseries(file_data, file_key, config, logger):
    header = file_data.get("header", [])
    data = normalize_epoch_rows(file_data.get("data", {}))
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
    use_if_multiple = resolve_use_if_multiple(config, file_config)

    interval = config.get("interval")

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
                (
                    name,
                    column_config,
                    referenced_columns := expr_columns,
                    missing_for_expr,
                )
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
            rounded_data = {}
            if interval:
                ts_interval = interval
                for raw_epoch, raw_rows in data.items():
                    rounded_epoch = round_epoch_to_interval_seconds(
                        raw_epoch, ts_interval, source_timezone
                    )
                    rounded_data.setdefault(rounded_epoch, []).extend(raw_rows)
                logger.info(
                    f"Rounding timestamps for {c(name, 'blue')} to configured interval {c(str(ts_interval), 'cyan')} seconds."
                )
            else:
                interval_parameter = (
                    name.split(".")[3] if len(name.split(".")) > 3 else ""
                )
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

                for raw_epoch, raw_rows in data.items():
                    rounded_epoch = int(
                        round_datetime_to_interval(
                            datetime.fromtimestamp(raw_epoch, tz=source_timezone),
                            interval_parameter,
                        ).timestamp()
                    )
                    rounded_data.setdefault(rounded_epoch, []).extend(raw_rows)
                logger.info(
                    f"Rounding timestamps for {c(name, 'blue')} to nearest {c(interval_parameter, 'cyan')}."
                )
                logger.info(
                    f"No configured interval found for {c(name, 'blue')}; defaulting round_to_nearest to the timeseries interval."
                )

            ts_data = rounded_data
        elif not ts_interval:
            ts_interval = determine_interval(data, 10)
            logger.warning(
                f"Interval not found in configuration. Determined interval: {ts_interval} seconds."
            )

        values = []
        ts_start_epoch = min(ts_data.keys())
        ts_end_epoch = max(ts_data.keys())
        epoch = ts_start_epoch
        while epoch <= ts_end_epoch:
            rows = ts_data.get(epoch)
            if rows:
                value, quality = select_value(
                    name,
                    epoch,
                    rows,
                    expr,
                    header_map,
                    precision,
                    use_if_multiple,
                    source_timezone,
                    logger,
                )
            else:
                value = None
                quality = 5
            logger.debug(
                f"[{name}] {datetime.fromtimestamp(epoch)} -> {value} (quality: {quality})"
            )
            values.append([epoch * 1000, value, quality])
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
