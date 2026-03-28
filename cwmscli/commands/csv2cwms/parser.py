from cwmscli.utils.colors import c

from .doclinks import COMPLETE_CONFIG_DOC_URL, with_doc_links
from .utils import load_csv, parse_date, safe_zoneinfo


def resolve_date_column(header, file_config):
    date_col = file_config.get("date_col")
    if date_col is None:
        return 0, header[0] if header else ""

    normalized_header = {col.strip().lower(): i for i, col in enumerate(header)}
    date_col_name = str(date_col).strip()
    date_col_index = normalized_header.get(date_col_name.lower())
    if date_col_index is None:
        raise ValueError(
            with_doc_links(
                "Configured date_col "
                f"{c(date_col_name, 'yellow')} was not found in the input file. "
                "Available CSV columns: "
                f"{c(', '.join(header), 'cyan')}",
                COMPLETE_CONFIG_DOC_URL,
            )
        )
    return date_col_index, header[date_col_index]


def parse_file(
    file_path, begin_time, date_format, timezone="GMT", file_config=None, logger=None
):
    file_config = file_config or {}
    csv_data = load_csv(file_path)
    header = csv_data[0]
    data = csv_data[1:]
    ts_data = {}
    source_timezone = safe_zoneinfo(timezone)
    date_col_index, date_col_label = resolve_date_column(header, file_config)
    if logger:
        logger.debug(f"Begin time: {begin_time}")
    for row in data:
        # Skip empty rows or rows without a timestamp
        if not row:
            continue
        if date_col_index >= len(row):
            raise ValueError(
                with_doc_links(
                    f"Configured date_col {c(date_col_label, 'yellow')} is missing from a CSV row in {c(file_path, 'red')}.",
                    COMPLETE_CONFIG_DOC_URL,
                )
            )
        try:
            row_datetime = parse_date(
                row[date_col_index], tz_str=timezone, date_format=date_format
            )
        except ValueError as err:
            if date_col_index == 0:
                raise ValueError(
                    with_doc_links(
                        "Unable to parse a timestamp from the first CSV column "
                        f"{c(date_col_label, 'yellow')} with value {c(str(row[0]), 'red')} in {c(file_path, 'red')}. "
                        "If the timestamp is in a different column, set "
                        f"{c('date_col', 'cyan')} in the input file config to that column name.",
                        COMPLETE_CONFIG_DOC_URL,
                    )
                ) from err
            raise ValueError(
                with_doc_links(
                    f"Unable to parse a timestamp from configured date_col {c(date_col_label, 'yellow')} "
                    f"with value {c(str(row[date_col_index]), 'red')} in {c(file_path, 'red')}.",
                    COMPLETE_CONFIG_DOC_URL,
                )
            ) from err
        ts_data.setdefault(int(row_datetime.timestamp()), []).append(row)
    return {"header": header, "data": ts_data, "source_timezone": source_timezone}
