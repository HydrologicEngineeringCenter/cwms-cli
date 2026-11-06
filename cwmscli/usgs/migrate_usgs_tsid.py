"""
Migrate legacy USGS WaterServices method IDs stored in the CWMS
Data Acquisition / USGS TS Data Acquisition group alias-id field
to new USGS Water Data API time_series_id values.

The script:
    1. Reads configured USGS CWMS time series and existing alias-id values.
    2. Gets the legacy methodDescription for each legacy methodID.
    3. Gets new USGS time-series metadata.
    4. Reconstructs the legacy methodDescription from:
           sublocation_identifier
           web_description
    5. Matches the legacy description to the new time_series_id.
    6. Updates only CWMS alias-id values for unambiguous matches.

The existing CWMS group attribute value is preserved.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable

import cwms
import pandas as pd
import requests
from dataretrieval import waterdata

from cwmscli.usgs.getusgs_cda import get_CMWS_TS_Loc_Data
from cwmscli.utils import colors, init_cwms_session

USGS_LEGACY_IV_URL = "https://waterservices.usgs.gov/nwis/iv/"

GROUP_ID = "USGS TS Data Acquisition"
CATEGORY_ID = "Data Acquisition"
GROUP_OFFICE_ID = "CWMS"
CATEGORY_OFFICE_ID = "CWMS"

LEGACY_METHOD_COLUMNS = [
    "USGS_St_Num",
    "USGS_PARAMETER",
    "methodID",
    "methodDescription",
]

REPORT_COLUMNS = [
    "office-id",
    "timeseries-id",
    "USGS_St_Num",
    "USGS_PARAMETER",
    "legacy_method_id",
    "methodDescription",
    "sublocation_identifier",
    "web_description",
    "reconstructed_method_description",
    "time_series_id",
    "new_time_series_id_count",
    "mapping_status",
    "metadata_mapping_status",
    "comparison_status",
    "comparison_error",
    "matched_record_count",
    "agreement_percent",
    "mean_absolute_difference",
    "max_absolute_difference",
    "cwms_unit",
    "usgs_unit",
    "unaliased_comparison_status",
    "unaliased_returned_time_series_ids",
    "unaliased_returned_time_series_count",
    "unaliased_metadata_time_series_ids",
    "unaliased_metadata_time_series_count",
    "unaliased_metadata_matches_returned_id",
    "unaliased_agreement_percent",
    "unaliased_matched_record_count",
    "unaliased_mean_absolute_difference",
    "unaliased_max_absolute_difference",
    "unaliased_usgs_unit",
    "unaliased_error",
]
COMPARISON_DETAIL_COLUMNS = [
    "office-id",
    "timeseries-id",
    "time_series_id",
    "USGS_St_Num",
    "USGS_PARAMETER",
    "legacy_method_id",
    "cwms_time",
    "usgs_time",
    "old_usgs_time",
    "time_delta_seconds",
    "cwms_value",
    "usgs_raw_value",
    "usgs_value_comparison",
    "old_usgs_value",
    "absolute_difference",
    "cwms_unit",
    "usgs_unit",
    "old_usgs_unit",
    "unit_conversion_applied",
    "approval_status",
    "qualifier",
    "old_usgs_qualifiers",
    "old_usgs_status",
    "within_tolerance",
    "comparison_result",
    "comparison_status",
]

COMPARISON_BASE_DETAIL_COLUMNS = [
    "time_series_id",
    "cwms_time",
    "usgs_time",
    "time_delta_seconds",
    "cwms_value",
    "usgs_raw_value",
    "usgs_value_comparison",
    "absolute_difference",
    "cwms_unit",
    "usgs_unit",
    "unit_conversion_applied",
    "approval_status",
    "qualifier",
    "within_tolerance",
    "comparison_result",
    "comparison_status",
]


def normalize_optional_string(value: Any) -> str | None:
    """Return a stripped string or None for null/empty values."""

    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    value = str(value).strip()

    return value if value else None


def normalize_for_match(value: Any) -> str | None:
    """Normalize a description for case- and whitespace-insensitive matching."""

    value = normalize_optional_string(value)

    if value is None:
        return None

    return re.sub(r"\s+", " ", value).casefold()


def normalize_station_number(value: Any) -> str | None:
    """Convert USGS station number to a zero-padded eight-digit string."""

    value = normalize_optional_string(value)

    if value is None:
        return None

    value = re.sub(r"\.0$", "", value)

    if not value.isdigit():
        return None

    return value.zfill(8)


def normalize_parameter_code(value: Any) -> str | None:
    """Convert USGS parameter code to a zero-padded five-digit string."""

    value = normalize_optional_string(value)

    if value is None:
        return None

    value = re.sub(r"\.0$", "", value)

    if not value.isdigit():
        return None

    return value.zfill(5)


def normalize_method_id(value: Any) -> str | None:
    """Normalize an old numeric USGS methodID."""

    value = normalize_optional_string(value)

    if value is None:
        return None

    value = re.sub(r"\.0$", "", value)

    return value if value.isdigit() else None


def format_legacy_method_description(
    sublocation_identifier: Any,
    web_description: Any,
) -> str | None:
    """
    Reconstruct legacy WaterServices methodDescription formatting.

    Both fields:
        <sublocation_identifier>, [<web_description>]

    Sublocation only:
        <sublocation_identifier>

    Web description only:
        [<web_description>]
    """

    sublocation = normalize_optional_string(sublocation_identifier)
    description = normalize_optional_string(web_description)

    if sublocation and description:
        return f"{sublocation}, [{description}]"

    if sublocation:
        return sublocation

    if description:
        return f"[{description}]"

    return None


def chunks(values: Iterable[str], chunk_size: int) -> Iterable[list[str]]:
    """Yield a sequence in chunks."""

    values = list(values)

    for index in range(0, len(values), chunk_size):
        yield values[index : index + chunk_size]


def write_csv(data: pd.DataFrame, output_file: Path) -> None:
    """Write a DataFrame to CSV and log the destination."""

    output_file.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(output_file, index=False)

    logging.info("Wrote report: %s", output_file)


def get_current_group_assignments(office_id: str) -> pd.DataFrame:
    """
    Retrieve current USGS TS Data Acquisition group assignments.

    The group is owned by CWMS. Assigned TSIDs belong to the requested office.
    """

    response = cwms.get_timeseries_group(
        group_id=GROUP_ID,
        category_id=CATEGORY_ID,
        office_id=office_id,
        category_office_id=CATEGORY_OFFICE_ID,
        group_office_id=GROUP_OFFICE_ID,
    )

    group_df = response.df.copy()

    if group_df is None or group_df.empty:
        raise RuntimeError(
            f"No time-series-group assignments returned for office {office_id}."
        )

    required_columns = {"office-id", "timeseries-id"}
    missing_columns = required_columns.difference(group_df.columns)

    if missing_columns:
        raise RuntimeError(
            "CWMS group response is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    group_df = group_df.loc[group_df["office-id"].astype("string").eq(office_id)].copy()

    if group_df.empty:
        raise RuntimeError(
            f"No USGS TS Data Acquisition assignments found for office {office_id}."
        )

    if "alias-id" not in group_df.columns:
        group_df["alias-id"] = None

    if "attribute" not in group_df.columns:
        group_df["attribute"] = 0

    return group_df


def parse_legacy_station_and_parameter(
    time_series: dict,
) -> tuple[str | None, str | None]:
    """
    Extract station and parameter information from legacy NWIS IV JSON.
    """

    station = None
    parameter = None

    try:
        station = (
            time_series.get("sourceInfo", {}).get("siteCode", [{}])[0].get("value")
        )
    except (AttributeError, IndexError, TypeError):
        station = None

    try:
        parameter = (
            time_series.get("variable", {}).get("variableCode", [{}])[0].get("value")
        )
    except (AttributeError, IndexError, TypeError):
        parameter = None

    # Typical fallback name structure:
    # USGS:<station number>:<parameter code>:<statistic code>
    if not station or not parameter:
        name = normalize_optional_string(time_series.get("name"))

        if name:
            parts = name.split(":")

            if len(parts) >= 3:
                station = station or parts[1]
                parameter = parameter or parts[2]

    return (
        normalize_station_number(station),
        normalize_parameter_code(parameter),
    )


def fetch_legacy_method_descriptions(
    requested_pairs: pd.DataFrame,
    chunk_size: int = 100,
    timeout_seconds: int = 90,
) -> pd.DataFrame:
    """
    Retrieve old methodID/methodDescription data from WaterServices.

    Uses access=3, consistent with the existing getUSGS method-ID workflow.
    """

    request_df = (
        requested_pairs[["USGS_St_Num", "USGS_PARAMETER"]].drop_duplicates().copy()
    )

    request_df["USGS_St_Num"] = request_df["USGS_St_Num"].map(normalize_station_number)
    request_df["USGS_PARAMETER"] = request_df["USGS_PARAMETER"].map(
        normalize_parameter_code
    )

    request_df = request_df.dropna(subset=["USGS_St_Num", "USGS_PARAMETER"])

    output_rows: list[dict[str, Any]] = []

    for station_chunk in chunks(
        sorted(request_df["USGS_St_Num"].unique()),
        chunk_size,
    ):
        parameter_codes = sorted(
            request_df.loc[
                request_df["USGS_St_Num"].isin(station_chunk),
                "USGS_PARAMETER",
            ]
            .dropna()
            .unique()
            .tolist()
        )

        params = {
            "format": "json",
            "sites": ",".join(station_chunk),
            "parameterCd": ",".join(parameter_codes),
            "period": "P7D",
            "access": "3",
            "siteStatus": "all",
        }

        logging.info(
            "Requesting legacy metadata for %s station(s) and %s parameter(s).",
            len(station_chunk),
            len(parameter_codes),
        )

        response = requests.get(
            USGS_LEGACY_IV_URL,
            params=params,
            timeout=timeout_seconds,
        )
        response.raise_for_status()

        payload = response.json()

        for time_series in payload.get("value", {}).get("timeSeries", []):
            station, parameter = parse_legacy_station_and_parameter(time_series)

            if not station or not parameter:
                continue

            for values_entry in time_series.get("values", []):
                methods = values_entry.get("method", [])

                for method in methods:
                    method_id = normalize_method_id(method.get("methodID"))
                    method_description = normalize_optional_string(
                        method.get("methodDescription")
                    )

                    if not method_id or not method_description:
                        continue

                    output_rows.append(
                        {
                            "USGS_St_Num": station,
                            "USGS_PARAMETER": parameter,
                            "methodID": method_id,
                            "methodDescription": method_description,
                        }
                    )

    if not output_rows:
        return pd.DataFrame(columns=LEGACY_METHOD_COLUMNS)

    legacy_df = pd.DataFrame(output_rows)

    return legacy_df.drop_duplicates(
        subset=[
            "USGS_St_Num",
            "USGS_PARAMETER",
            "methodID",
            "methodDescription",
        ]
    ).reset_index(drop=True)


def load_legacy_methods_csv(csv_file: Path) -> pd.DataFrame:
    """Load a legacy method crosswalk CSV."""

    legacy_df = pd.read_csv(
        csv_file,
        dtype={
            "USGS_St_Num": "string",
            "USGS_PARAMETER": "string",
            "methodID": "string",
            "methodDescription": "string",
        },
    )

    missing_columns = set(LEGACY_METHOD_COLUMNS).difference(legacy_df.columns)

    if missing_columns:
        raise ValueError(
            "Legacy methods CSV is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    legacy_df = legacy_df[LEGACY_METHOD_COLUMNS].copy()

    legacy_df["USGS_St_Num"] = legacy_df["USGS_St_Num"].map(normalize_station_number)
    legacy_df["USGS_PARAMETER"] = legacy_df["USGS_PARAMETER"].map(
        normalize_parameter_code
    )
    legacy_df["methodID"] = legacy_df["methodID"].map(normalize_method_id)
    legacy_df["methodDescription"] = legacy_df["methodDescription"].map(
        normalize_optional_string
    )

    legacy_df = legacy_df.dropna(
        subset=[
            "USGS_St_Num",
            "USGS_PARAMETER",
            "methodID",
            "methodDescription",
        ]
    )

    return legacy_df.drop_duplicates().reset_index(drop=True)


def get_new_usgs_timeseries_metadata(
    requested_pairs: pd.DataFrame,
) -> pd.DataFrame:
    """
    Retrieve new USGS continuous time-series metadata and the actual
    UUID-like time_series_id values.

    Process:
        1. Query combined-metadata for data_type='Continuous values'.
           This identifies which statistic IDs are valid for each requested
           station/parameter combination.

        2. Query time-series-metadata for each parameter/statistic grouping.
           This endpoint returns the actual time_series_id needed for the
           CWMS USGS TS Data Acquisition group alias-id field.

    Notes:
        * combined_meta_id is NOT used as the CWMS alias-id.
        * parent_time_series_id is NOT used as the CWMS alias-id.
        * time_series_id from time-series-metadata is the desired value.
    """

    request_df = (
        requested_pairs[["USGS_St_Num", "USGS_PARAMETER"]].drop_duplicates().copy()
    )

    request_df["USGS_St_Num"] = request_df["USGS_St_Num"].map(normalize_station_number)
    request_df["USGS_PARAMETER"] = request_df["USGS_PARAMETER"].map(
        normalize_parameter_code
    )

    request_df = request_df.dropna(subset=["USGS_St_Num", "USGS_PARAMETER"])

    request_df["monitoring_location_id"] = "USGS-" + request_df["USGS_St_Num"]

    # -----------------------------------------------------------------------
    # Step 1: Discover valid continuous statistic IDs.
    # -----------------------------------------------------------------------
    available_frames: list[pd.DataFrame] = []

    for parameter_code, parameter_group in request_df.groupby("USGS_PARAMETER"):
        monitoring_locations = sorted(
            parameter_group["monitoring_location_id"].unique().tolist()
        )

        logging.info(
            "Discovering continuous USGS metadata for parameter %s at %s station(s).",
            parameter_code,
            len(monitoring_locations),
        )

        available_df, _ = waterdata.get_combined_metadata(
            monitoring_location_id=monitoring_locations,
            parameter_code=parameter_code,
            data_type="Continuous values",
            skip_geometry=True,
        )

        if available_df is None or available_df.empty:
            logging.warning(
                "No continuous metadata was returned for parameter %s.",
                parameter_code,
            )
            continue

        available_frames.append(available_df.copy())

    if not available_frames:
        return pd.DataFrame(
            columns=[
                "monitoring_location_id",
                "USGS_PARAMETER",
                "statistic_id",
                "data_type",
                "time_series_id",
                "sublocation_identifier",
                "web_description",
                "reconstructed_method_description",
                "reconstructed_method_description_normalized",
            ]
        )

    continuous_available = pd.concat(
        available_frames,
        ignore_index=True,
    )

    required_available_columns = {
        "monitoring_location_id",
        "parameter_code",
        "statistic_id",
    }

    missing_available_columns = required_available_columns.difference(
        continuous_available.columns
    )

    if missing_available_columns:
        raise RuntimeError(
            "USGS combined metadata response is missing expected columns: "
            f"{sorted(missing_available_columns)}"
        )

    continuous_available = continuous_available.rename(
        columns={
            "parameter_code": "USGS_PARAMETER",
        }
    )

    continuous_available["USGS_PARAMETER"] = continuous_available["USGS_PARAMETER"].map(
        normalize_parameter_code
    )

    continuous_available["statistic_id"] = continuous_available["statistic_id"].map(
        normalize_optional_string
    )

    continuous_available = continuous_available.dropna(
        subset=[
            "monitoring_location_id",
            "USGS_PARAMETER",
            "statistic_id",
        ]
    )

    # Keep only the information needed to constrain the actual
    # time-series-metadata requests.
    continuous_available = continuous_available[
        [
            "monitoring_location_id",
            "USGS_PARAMETER",
            "statistic_id",
        ]
    ].drop_duplicates()

    logging.info(
        "Found %s continuous station/parameter/statistic combination(s).",
        len(continuous_available),
    )

    # -----------------------------------------------------------------------
    # Step 2: Retrieve actual time_series_id values.
    # -----------------------------------------------------------------------
    metadata_frames: list[pd.DataFrame] = []

    for (
        parameter_code,
        statistic_id,
    ), metadata_group in continuous_available.groupby(
        ["USGS_PARAMETER", "statistic_id"]
    ):
        monitoring_locations = sorted(
            metadata_group["monitoring_location_id"].unique().tolist()
        )

        logging.info(
            "Requesting time-series IDs for parameter %s, statistic %s, "
            "at %s station(s).",
            parameter_code,
            statistic_id,
            len(monitoring_locations),
        )

        metadata_df, _ = waterdata.get_time_series_metadata(
            monitoring_location_id=monitoring_locations,
            parameter_code=parameter_code,
            statistic_id=statistic_id,
        )

        if metadata_df is None or metadata_df.empty:
            logging.warning(
                "No time-series metadata was returned for parameter %s, "
                "statistic %s.",
                parameter_code,
                statistic_id,
            )
            continue

        metadata_frames.append(metadata_df.copy())

    if not metadata_frames:
        return pd.DataFrame(
            columns=[
                "monitoring_location_id",
                "USGS_PARAMETER",
                "statistic_id",
                "data_type",
                "time_series_id",
                "sublocation_identifier",
                "web_description",
                "reconstructed_method_description",
                "reconstructed_method_description_normalized",
            ]
        )

    metadata = pd.concat(
        metadata_frames,
        ignore_index=True,
    )

    # dataretrieval normally names this time_series_id. Retain the fallback
    # because the raw API property is named id.
    if "time_series_id" not in metadata.columns and "id" in metadata.columns:
        metadata = metadata.rename(
            columns={
                "id": "time_series_id",
            }
        )

    required_metadata_columns = {
        "monitoring_location_id",
        "parameter_code",
        "statistic_id",
        "time_series_id",
    }

    missing_metadata_columns = required_metadata_columns.difference(metadata.columns)

    if missing_metadata_columns:
        raise RuntimeError(
            "USGS time-series metadata response is missing expected columns: "
            f"{sorted(missing_metadata_columns)}. "
            f"Returned columns: {sorted(metadata.columns.tolist())}"
        )

    metadata = metadata.rename(
        columns={
            "parameter_code": "USGS_PARAMETER",
        }
    )

    metadata["USGS_PARAMETER"] = metadata["USGS_PARAMETER"].map(
        normalize_parameter_code
    )

    metadata["statistic_id"] = metadata["statistic_id"].map(normalize_optional_string)

    # This confirms every returned UUID corresponds to an available
    # continuous series. It also removes any accidental station/parameter/
    # statistic cross-product results.
    metadata = metadata.merge(
        continuous_available,
        how="inner",
        on=[
            "monitoring_location_id",
            "USGS_PARAMETER",
            "statistic_id",
        ],
    )

    # time-series-metadata does not need to carry data_type because it is
    # already constrained through the combined-metadata inventory query.
    metadata["data_type"] = "Continuous values"

    if "sublocation_identifier" not in metadata.columns:
        metadata["sublocation_identifier"] = None

    if "web_description" not in metadata.columns:
        metadata["web_description"] = None

    metadata["reconstructed_method_description"] = metadata.apply(
        lambda row: format_legacy_method_description(
            row["sublocation_identifier"],
            row["web_description"],
        ),
        axis=1,
    )

    metadata["reconstructed_method_description_normalized"] = metadata[
        "reconstructed_method_description"
    ].map(normalize_for_match)

    metadata = metadata[
        [
            "monitoring_location_id",
            "USGS_PARAMETER",
            "statistic_id",
            "data_type",
            "time_series_id",
            "sublocation_identifier",
            "web_description",
            "reconstructed_method_description",
            "reconstructed_method_description_normalized",
        ]
    ].drop_duplicates()

    return metadata.reset_index(drop=True)


def build_crosswalk(
    configured_ts: pd.DataFrame,
    legacy_methods: pd.DataFrame,
    new_metadata: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build a legacy methodID to new USGS time_series_id crosswalk.
    """

    configured = configured_ts.copy()

    configured["USGS_St_Num"] = configured["USGS_St_Num"].map(normalize_station_number)
    configured["USGS_PARAMETER"] = configured["USGS_PARAMETER"].map(
        normalize_parameter_code
    )
    configured["legacy_method_id"] = configured["USGS_Method_TS"].map(
        normalize_method_id
    )
    configured["monitoring_location_id"] = "USGS-" + configured["USGS_St_Num"]

    configured = configured.drop_duplicates(
        subset=[
            "office-id",
            "timeseries-id",
            "USGS_St_Num",
            "USGS_PARAMETER",
            "legacy_method_id",
        ]
    )

    legacy = legacy_methods.copy()

    legacy["USGS_St_Num"] = legacy["USGS_St_Num"].map(normalize_station_number)
    legacy["USGS_PARAMETER"] = legacy["USGS_PARAMETER"].map(normalize_parameter_code)
    legacy["legacy_method_id"] = legacy["methodID"].map(normalize_method_id)
    legacy["legacy_method_description_normalized"] = legacy["methodDescription"].map(
        normalize_for_match
    )

    configured = configured.merge(
        legacy[
            [
                "USGS_St_Num",
                "USGS_PARAMETER",
                "legacy_method_id",
                "methodDescription",
                "legacy_method_description_normalized",
            ]
        ],
        how="left",
        on=[
            "USGS_St_Num",
            "USGS_PARAMETER",
            "legacy_method_id",
        ],
    )

    crosswalk = configured.merge(
        new_metadata,
        how="left",
        left_on=[
            "monitoring_location_id",
            "USGS_PARAMETER",
            "legacy_method_description_normalized",
        ],
        right_on=[
            "monitoring_location_id",
            "USGS_PARAMETER",
            "reconstructed_method_description_normalized",
        ],
    )

    match_counts = (
        crosswalk.groupby(
            [
                "office-id",
                "timeseries-id",
                "USGS_St_Num",
                "USGS_PARAMETER",
                "legacy_method_id",
            ],
            dropna=False,
        )["time_series_id"]
        .nunique()
        .reset_index(name="new_time_series_id_count")
    )

    crosswalk = crosswalk.merge(
        match_counts,
        how="left",
        on=[
            "office-id",
            "timeseries-id",
            "USGS_St_Num",
            "USGS_PARAMETER",
            "legacy_method_id",
        ],
    )

    crosswalk["mapping_status"] = "unreviewed"

    crosswalk.loc[
        crosswalk["legacy_method_id"].isna(),
        "mapping_status",
    ] = "no_numeric_legacy_method_id"

    crosswalk.loc[
        crosswalk["legacy_method_id"].notna() & crosswalk["methodDescription"].isna(),
        "mapping_status",
    ] = "legacy_method_description_not_found"

    crosswalk.loc[
        crosswalk["legacy_method_id"].notna()
        & crosswalk["methodDescription"].notna()
        & crosswalk["time_series_id"].isna(),
        "mapping_status",
    ] = "no_new_metadata_description_match"

    crosswalk.loc[
        crosswalk["new_time_series_id_count"].eq(1),
        "mapping_status",
    ] = "matched"

    crosswalk.loc[
        crosswalk["new_time_series_id_count"].gt(1),
        "mapping_status",
    ] = "ambiguous_multiple_new_time_series_ids"

    return crosswalk


def resolve_ambiguous_mappings_by_comparison(
    crosswalk: pd.DataFrame,
) -> pd.DataFrame:
    """
    Resolve metadata-ambiguous USGS time_series_id candidates using value
    comparison results.

    An ambiguous mapping is promoted only when exactly one candidate has:

        comparison_status = values_agree

    Other candidates remain in the report with a rejected status. The original
    metadata-only mapping status is retained in metadata_mapping_status.
    """

    resolved = crosswalk.copy()

    if "mapping_status" not in resolved.columns:
        return resolved

    if "comparison_status" not in resolved.columns:
        return resolved

    if "metadata_mapping_status" not in resolved.columns:
        resolved["metadata_mapping_status"] = resolved["mapping_status"]

    key_columns = [
        "office-id",
        "timeseries-id",
        "USGS_St_Num",
        "USGS_PARAMETER",
        "legacy_method_id",
    ]

    missing_columns = set(key_columns).difference(resolved.columns)

    if missing_columns:
        logging.warning(
            "Cannot resolve ambiguous mappings by comparison because the "
            "crosswalk is missing columns: %s",
            sorted(missing_columns),
        )
        return resolved

    resolvable_statuses = [
        "ambiguous_multiple_new_time_series_ids",
        "no_new_metadata_description_match_candidate_found",
    ]

    ambiguous_mask = resolved["mapping_status"].isin(resolvable_statuses)

    ambiguous_rows = resolved.loc[
        ambiguous_mask & resolved["time_series_id"].notna()
    ].copy()

    if ambiguous_rows.empty:
        return resolved

    for _, candidate_group in ambiguous_rows.groupby(
        key_columns,
        dropna=False,
    ):
        agreeing_ids = (
            candidate_group.loc[
                candidate_group["comparison_status"].eq("values_agree"),
                "time_series_id",
            ]
            .dropna()
            .unique()
            .tolist()
        )

        # Do not automatically resolve if no candidate agrees or if multiple
        # candidates agree. The latter remains a genuine ambiguity.
        if len(agreeing_ids) != 1:
            continue

        selected_time_series_id = agreeing_ids[0]

        group_index = candidate_group.index

        selected_mask = resolved.index.isin(group_index) & resolved[
            "time_series_id"
        ].eq(selected_time_series_id)

        rejected_mask = resolved.index.isin(group_index) & ~resolved[
            "time_series_id"
        ].eq(selected_time_series_id)

        resolved.loc[
            selected_mask,
            "mapping_status",
        ] = "matched_by_value_comparison"

        resolved.loc[
            rejected_mask,
            "mapping_status",
        ] = "candidate_rejected_by_value_comparison"

        logging.info(
            "Resolved ambiguous CWMS TSID %s using USGS time_series_id %s "
            "because it was the only candidate with values_agree status.",
            candidate_group.iloc[0]["timeseries-id"],
            selected_time_series_id,
        )

    return resolved


def resolve_unaliased_mappings_by_comparison(
    crosswalk: pd.DataFrame,
    unaliased_comparison_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Mark records as eligible for alias-id clearing when a direct unaliased
    station/parameter query returns one series and agrees with CWMS.
    """

    result = crosswalk.copy()

    if unaliased_comparison_df.empty:
        return result

    merge_columns = [
        "office-id",
        "timeseries-id",
        "monitoring_location_id",
        "USGS_PARAMETER",
    ]

    result = result.merge(
        unaliased_comparison_df,
        how="left",
        on=merge_columns,
    )

    clear_alias_mask = result["unaliased_comparison_status"].eq(
        "unaliased_values_agree"
    )

    if "metadata_mapping_status" not in result.columns:
        result["metadata_mapping_status"] = result["mapping_status"]

    result.loc[
        clear_alias_mask,
        "mapping_status",
    ] = "matched_without_alias_by_value_comparison"

    result.loc[
        clear_alias_mask,
        "time_series_id",
    ] = result.loc[
        clear_alias_mask,
        "time_series_id",
    ].fillna(
        result.loc[
            clear_alias_mask,
            "unaliased_returned_time_series_ids",
        ]
    )

    return result


def add_station_parameter_fallback_candidates(
    crosswalk: pd.DataFrame,
    new_metadata: pd.DataFrame,
) -> pd.DataFrame:
    """
    For records where the old methodDescription did not match any new USGS
    sublocation/web-description combination, add all candidate new USGS
    time_series_id values for the same station and parameter.

    These fallback candidates are not automatically accepted. They are passed
    to the CWMS/new-USGS value comparison process. A later resolver may select
    a candidate only when exactly one candidate has values_agree status.
    """

    result = crosswalk.copy()

    if "mapping_status" not in result.columns:
        return result

    required_crosswalk_columns = {
        "monitoring_location_id",
        "USGS_PARAMETER",
        "time_series_id",
    }

    required_metadata_columns = {
        "monitoring_location_id",
        "USGS_PARAMETER",
        "time_series_id",
    }

    if not required_crosswalk_columns.issubset(result.columns):
        logging.warning(
            "Cannot add station/parameter fallback candidates because the "
            "crosswalk does not contain expected columns."
        )
        return result

    if not required_metadata_columns.issubset(new_metadata.columns):
        logging.warning(
            "Cannot add station/parameter fallback candidates because new "
            "USGS metadata does not contain expected columns."
        )
        return result

    fallback_mask = (
        result["mapping_status"].eq("no_new_metadata_description_match")
        & result["time_series_id"].isna()
    )

    fallback_source = result.loc[fallback_mask].copy()

    if fallback_source.empty:
        return result

    logging.info(
        "Looking for station/parameter fallback candidates for %s "
        "unmatched legacy method-description record(s).",
        len(fallback_source),
    )

    # Remove candidate metadata fields from the unmatched row before merging
    # the candidate metadata back by monitoring location and parameter.
    metadata_columns_to_drop = [
        column
        for column in new_metadata.columns
        if column
        not in {
            "monitoring_location_id",
            "USGS_PARAMETER",
        }
    ]

    fallback_source = fallback_source.drop(
        columns=metadata_columns_to_drop,
        errors="ignore",
    )

    fallback_candidates = fallback_source.merge(
        new_metadata,
        how="left",
        on=[
            "monitoring_location_id",
            "USGS_PARAMETER",
        ],
    )

    # Preserve the original metadata-only status for audit purposes.
    if "metadata_mapping_status" not in fallback_candidates.columns:
        fallback_candidates["metadata_mapping_status"] = (
            "no_new_metadata_description_match"
        )

    candidate_found_mask = fallback_candidates["time_series_id"].notna()

    fallback_candidates.loc[
        candidate_found_mask,
        "mapping_status",
    ] = "no_new_metadata_description_match_candidate_found"

    fallback_candidates.loc[
        ~candidate_found_mask,
        "mapping_status",
    ] = "no_new_metadata_for_station_parameter"

    # Update candidate count for each configured CWMS TSID/method mapping.
    count_columns = [
        "office-id",
        "timeseries-id",
        "USGS_St_Num",
        "USGS_PARAMETER",
        "legacy_method_id",
    ]

    available_count_columns = [
        column for column in count_columns if column in fallback_candidates.columns
    ]

    if available_count_columns:
        candidate_counts = (
            fallback_candidates.groupby(
                available_count_columns,
                dropna=False,
            )["time_series_id"]
            .nunique()
            .reset_index(name="new_time_series_id_count")
        )

        fallback_candidates = fallback_candidates.drop(
            columns=["new_time_series_id_count"],
            errors="ignore",
        ).merge(
            candidate_counts,
            how="left",
            on=available_count_columns,
        )

    # Remove the original no-description-match records that had no candidate
    # IDs. They are replaced with zero, one, or many fallback candidate rows.
    result = result.loc[~fallback_mask].copy()

    result = pd.concat(
        [
            result,
            fallback_candidates,
        ],
        ignore_index=True,
        sort=False,
    )

    return result


def create_update_plan(
    crosswalk: pd.DataFrame,
    require_comparison: bool = False,
) -> pd.DataFrame:
    """
    Return safe, one-to-one mappings eligible for CWMS alias-id updates.

    When require_comparison=True, a metadata match must also have a
    comparison_status of values_agree.
    """

    update_plan = crosswalk.loc[
        crosswalk["mapping_status"].isin(
            [
                "matched",
                "matched_by_value_comparison",
                "matched_without_alias_by_value_comparison",
            ]
        )
    ].copy()

    if require_comparison:
        uuid_alias_match_mask = update_plan["mapping_status"].isin(
            [
                "matched",
                "matched_by_value_comparison",
            ]
        ) & update_plan["comparison_status"].eq("values_agree")

        blank_alias_match_mask = update_plan["mapping_status"].eq(
            "matched_without_alias_by_value_comparison"
        ) & update_plan["unaliased_comparison_status"].eq("unaliased_values_agree")

        update_plan = update_plan.loc[
            uuid_alias_match_mask | blank_alias_match_mask
        ].copy()

    update_plan = update_plan.drop_duplicates(
        subset=[
            "office-id",
            "timeseries-id",
            "time_series_id",
        ]
    )

    update_plan["new_alias_id"] = update_plan["time_series_id"]

    # A direct unaliased match may apply to several candidate metadata rows
    # for the same CWMS TSID. Prefer the blank-alias update and retain only
    # one update row per CWMS TSID.
    update_plan["_update_priority"] = 1

    update_plan.loc[
        update_plan["mapping_status"].eq("matched_without_alias_by_value_comparison"),
        "_update_priority",
    ] = 0

    update_plan = (
        update_plan.sort_values(
            by=[
                "_update_priority",
                "office-id",
                "timeseries-id",
            ]
        )
        .drop_duplicates(
            subset=[
                "office-id",
                "timeseries-id",
            ],
            keep="first",
        )
        .drop(columns=["_update_priority"])
        .reset_index(drop=True)
    )

    # A direct station/parameter query returned exactly one USGS series and
    # agreed with CWMS. The future ingestion process does not need alias-id.
    update_plan.loc[
        update_plan["mapping_status"].eq("matched_without_alias_by_value_comparison"),
        "new_alias_id",
    ] = None

    return update_plan.reset_index(drop=True)


def build_patch_dataframe(
    current_group: pd.DataFrame,
    update_plan: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build the group records sent to CWMS.

    Existing attribute values are preserved. Only alias-id is changed.
    """

    update_values = update_plan[
        [
            "office-id",
            "timeseries-id",
            "new_alias_id",
        ]
    ].drop_duplicates()

    patch_df = current_group.merge(
        update_values,
        how="inner",
        on=["office-id", "timeseries-id"],
        validate="one_to_one",
    )

    patch_df["alias-id"] = patch_df["new_alias_id"]
    patch_df = patch_df.drop(columns=["new_alias_id"])

    required_columns = [
        "office-id",
        "timeseries-id",
        "alias-id",
        "attribute",
    ]

    for column in required_columns:
        if column not in patch_df.columns:
            if column == "attribute":
                patch_df[column] = 0
            else:
                raise RuntimeError(
                    f"Cannot build CWMS patch; missing required column: {column}"
                )

    keep_columns = [
        "office-id",
        "timeseries-id",
        "alias-id",
        "attribute",
    ]

    if "ts-code" in patch_df.columns:
        keep_columns.append("ts-code")

    return (
        patch_df[keep_columns]
        .sort_values(by=["office-id", "timeseries-id"])
        .reset_index(drop=True)
    )


def normalize_comparison_unit(unit: Any) -> str | None:
    """
    Normalize common CWMS and USGS unit labels for comparison.

    The existing USGS acquisition process generally stores USGS values using
    their returned units, but this normalization supports common equivalent
    spellings and water-temperature conversion.
    """

    unit = normalize_optional_string(unit)

    if unit is None:
        return None

    normalized = unit.casefold().replace(" ", "").replace("^", "").replace("³", "3")

    aliases = {
        "cfs": "ft3/s",
        "ft3/s": "ft3/s",
        "cubicfeetpersecond": "ft3/s",
        "ft": "ft",
        "feet": "ft",
        "foot": "ft",
        "in": "in",
        "inch": "in",
        "inches": "in",
        "degc": "degc",
        "c": "degc",
        "celsius": "degc",
        "degf": "degf",
        "f": "degf",
        "fahrenheit": "degf",
        "m": "m",
        "meter": "m",
        "meters": "m",
        "ft-msl": "ft",
    }

    return aliases.get(normalized, normalized)


def get_cwms_data_unit(cwms_data: Any) -> str | None:
    """
    Read the units property from a cwms-python Data object.
    """

    payload = getattr(cwms_data, "json", None)

    if payload is None:
        payload = getattr(cwms_data, "JSON", None)

    if isinstance(payload, dict):
        return normalize_optional_string(payload.get("units"))

    return None


def convert_usgs_to_cwms_unit(
    usgs_values: pd.Series,
    usgs_unit: str | None,
    cwms_unit: str | None,
) -> tuple[pd.Series, bool]:
    """
    Convert USGS values into CWMS units for supported unit combinations.

    Returns
    -------
    values : pandas.Series
        USGS values expressed in CWMS units.

    conversion_applied : bool
        True when a conversion occurred.
    """

    normalized_usgs_unit = normalize_comparison_unit(usgs_unit)
    normalized_cwms_unit = normalize_comparison_unit(cwms_unit)

    if normalized_usgs_unit == normalized_cwms_unit:
        return usgs_values.copy(), False

    if normalized_usgs_unit == "degc" and normalized_cwms_unit == "degf":
        return (usgs_values * 9.0 / 5.0) + 32.0, True

    if normalized_usgs_unit == "degf" and normalized_cwms_unit == "degc":
        return (usgs_values - 32.0) * 5.0 / 9.0, True

    raise ValueError(
        "Unsupported unit comparison: " f"CWMS={cwms_unit!r}, USGS={usgs_unit!r}"
    )


def get_cwms_comparison_values(
    cwms_tsid: str,
    office_id: str,
    begin: datetime,
    end: datetime,
) -> tuple[pd.DataFrame, str | None]:
    """
    Retrieve and normalize CWMS values for time-series comparison.
    """

    cwms_data = cwms.get_timeseries(
        ts_id=cwms_tsid,
        office_id=office_id,
        begin=begin,
        end=end,
    )

    cwms_df = cwms_data.df.copy()

    if cwms_df is None or cwms_df.empty:
        return pd.DataFrame(columns=["date-time", "cwms_value"]), None

    required_columns = {"date-time", "value"}
    missing_columns = required_columns.difference(cwms_df.columns)

    if missing_columns:
        raise RuntimeError(
            f"CWMS response for {cwms_tsid} is missing columns: "
            f"{sorted(missing_columns)}"
        )

    cwms_unit = get_cwms_data_unit(cwms_data)

    cwms_df = cwms_df[["date-time", "value"]].copy()

    cwms_df["date-time"] = pd.to_datetime(
        cwms_df["date-time"],
        utc=True,
        errors="coerce",
    )

    cwms_df["cwms_value"] = pd.to_numeric(
        cwms_df["value"],
        errors="coerce",
    )

    cwms_df = (
        cwms_df.drop(columns=["value"])
        .dropna(subset=["date-time", "cwms_value"])
        .drop_duplicates(subset=["date-time"])
        .sort_values("date-time")
        .reset_index(drop=True)
    )

    return cwms_df, cwms_unit


def get_usgs_comparison_values(
    usgs_time_series_id: str,
    begin: datetime,
    end: datetime,
) -> tuple[pd.DataFrame, str | None]:
    """
    Retrieve and normalize USGS continuous values for one time_series_id.

    Retains approval_status and qualifier fields for mismatch reporting.
    """

    usgs_df, _ = waterdata.get_continuous(
        time_series_id=usgs_time_series_id,
        time=[
            pd.Timestamp(begin).isoformat(),
            pd.Timestamp(end).isoformat(),
        ],
        properties=[
            "time_series_id",
            "time",
            "value",
            "unit_of_measure",
            "approval_status",
            "qualifier",
        ],
    )

    empty_df = pd.DataFrame(
        columns=[
            "time",
            "usgs_raw_value",
            "usgs_value",
            "approval_status",
            "qualifier",
        ]
    )

    if usgs_df is None or usgs_df.empty:
        return empty_df, None

    required_columns = {"time", "value"}
    missing_columns = required_columns.difference(usgs_df.columns)

    if missing_columns:
        raise RuntimeError(
            f"USGS response for {usgs_time_series_id} is missing columns: "
            f"{sorted(missing_columns)}"
        )

    usgs_unit = None

    if "unit_of_measure" in usgs_df.columns:
        units = usgs_df["unit_of_measure"].dropna().astype(str).unique().tolist()

        if len(units) == 1:
            usgs_unit = units[0]
        elif len(units) > 1:
            usgs_unit = ",".join(units)

    keep_columns = ["time", "value"]

    if "approval_status" in usgs_df.columns:
        keep_columns.append("approval_status")
    else:
        usgs_df["approval_status"] = None
        keep_columns.append("approval_status")

    if "qualifier" in usgs_df.columns:
        keep_columns.append("qualifier")
    else:
        usgs_df["qualifier"] = None
        keep_columns.append("qualifier")

    usgs_df = usgs_df[keep_columns].copy()

    usgs_df["time"] = pd.to_datetime(
        usgs_df["time"],
        utc=True,
        errors="coerce",
    )

    usgs_df["usgs_raw_value"] = pd.to_numeric(
        usgs_df["value"],
        errors="coerce",
    )

    # usgs_value may be converted later to match CWMS units.
    usgs_df["usgs_value"] = usgs_df["usgs_raw_value"]

    usgs_df = (
        usgs_df.drop(columns=["value"])
        .dropna(subset=["time", "usgs_raw_value"])
        .drop_duplicates(subset=["time"])
        .sort_values("time")
        .reset_index(drop=True)
    )

    return usgs_df, usgs_unit


def get_legacy_usgs_method_values(
    usgs_station_number: str,
    usgs_parameter: str,
    legacy_method_id: str,
    begin: datetime,
    end: datetime,
) -> pd.DataFrame:
    """
    Retrieve values from the legacy USGS WaterServices IV endpoint for one
    station, parameter, and methodID.

    The returned values are used only for migration validation reporting.
    They do not affect the new time_series_id mapping decision.
    """

    empty_df = pd.DataFrame(
        columns=[
            "old_usgs_time",
            "old_usgs_value",
            "old_usgs_qualifiers",
            "old_usgs_unit",
        ]
    )

    station_number = normalize_station_number(usgs_station_number)
    parameter_code = normalize_parameter_code(usgs_parameter)
    method_id = normalize_method_id(legacy_method_id)

    if not station_number or not parameter_code or not method_id:
        return empty_df

    params = {
        "format": "json",
        "sites": station_number,
        "parameterCd": parameter_code,
        "startDT": pd.Timestamp(begin).isoformat(),
        "endDT": pd.Timestamp(end).isoformat(),
        "access": "3",
        "siteStatus": "all",
    }

    response = requests.get(
        USGS_LEGACY_IV_URL,
        params=params,
        timeout=90,
    )
    response.raise_for_status()

    payload = response.json()
    rows = []

    for time_series in payload.get("value", {}).get("timeSeries", []):
        try:
            old_usgs_unit = (
                time_series.get("variable", {}).get("unit", {}).get("unitCode")
            )
        except AttributeError:
            old_usgs_unit = None

        for values_entry in time_series.get("values", []):
            methods = values_entry.get("method", [])

            values_entry_method_ids = {
                normalize_method_id(method.get("methodID"))
                for method in methods
                if method.get("methodID") is not None
            }

            # This "values" block does not belong to the requested old
            # methodID, so do not use its observations.
            if method_id not in values_entry_method_ids:
                continue

            for observation in values_entry.get("value", []):
                rows.append(
                    {
                        "old_usgs_time": observation.get("dateTime"),
                        "old_usgs_value": observation.get("value"),
                        "old_usgs_qualifiers": observation.get("qualifiers"),
                        "old_usgs_unit": old_usgs_unit,
                    }
                )

    if not rows:
        return empty_df

    old_df = pd.DataFrame(rows)

    old_df["old_usgs_time"] = pd.to_datetime(
        old_df["old_usgs_time"],
        utc=True,
        errors="coerce",
    )

    old_df["old_usgs_value"] = pd.to_numeric(
        old_df["old_usgs_value"],
        errors="coerce",
    )

    old_df = (
        old_df.dropna(subset=["old_usgs_time", "old_usgs_value"])
        .drop_duplicates(subset=["old_usgs_time"])
        .sort_values("old_usgs_time")
        .reset_index(drop=True)
    )

    return old_df


def get_usgs_unaliased_comparison_values(
    monitoring_location_id: str,
    usgs_parameter: str,
    begin: datetime,
    end: datetime,
) -> tuple[pd.DataFrame, str | None, list[str]]:
    """
    Retrieve new-USGS continuous values without using time_series_id.

    This emulates a future CWMS USGS ingestion request that relies only on:

        monitoring_location_id
        parameter_code

    Returns
    -------
    values_df : pandas.DataFrame
        Continuous values returned by the direct station/parameter query.

    unit : str | None
        USGS unit of measure, if one unit is returned.

    returned_time_series_ids : list[str]
        Distinct USGS time_series_id values returned by the direct query.
        The alias may be cleared only when this list contains exactly one ID.
    """

    empty_df = pd.DataFrame(
        columns=[
            "time",
            "usgs_raw_value",
            "usgs_value",
            "approval_status",
            "qualifier",
        ]
    )

    usgs_df, _ = waterdata.get_continuous(
        monitoring_location_id=monitoring_location_id,
        parameter_code=usgs_parameter,
        time=[
            pd.Timestamp(begin).isoformat(),
            pd.Timestamp(end).isoformat(),
        ],
        properties=[
            "time_series_id",
            "time",
            "value",
            "unit_of_measure",
            "approval_status",
            "qualifier",
        ],
    )

    if usgs_df is None or usgs_df.empty:
        return empty_df, None, []

    required_columns = {
        "time_series_id",
        "time",
        "value",
    }

    missing_columns = required_columns.difference(usgs_df.columns)

    if missing_columns:
        raise RuntimeError(
            "Unaliased USGS response is missing columns: " f"{sorted(missing_columns)}"
        )

    returned_time_series_ids = sorted(
        usgs_df["time_series_id"].dropna().astype(str).unique().tolist()
    )

    usgs_unit = None

    if "unit_of_measure" in usgs_df.columns:
        units = usgs_df["unit_of_measure"].dropna().astype(str).unique().tolist()

        if len(units) == 1:
            usgs_unit = units[0]
        elif len(units) > 1:
            usgs_unit = ",".join(units)

    if "approval_status" not in usgs_df.columns:
        usgs_df["approval_status"] = None

    if "qualifier" not in usgs_df.columns:
        usgs_df["qualifier"] = None

    values_df = usgs_df[
        [
            "time_series_id",
            "time",
            "value",
            "approval_status",
            "qualifier",
        ]
    ].copy()

    values_df["time"] = pd.to_datetime(
        values_df["time"],
        utc=True,
        errors="coerce",
    )

    values_df["usgs_raw_value"] = pd.to_numeric(
        values_df["value"],
        errors="coerce",
    )

    values_df["usgs_value"] = values_df["usgs_raw_value"]

    values_df = (
        values_df.drop(columns=["value"])
        .dropna(subset=["time", "usgs_raw_value"])
        .sort_values("time")
        .reset_index(drop=True)
    )

    return values_df, usgs_unit, returned_time_series_ids


def compare_usgs_candidate_to_cwms(
    cwms_df: pd.DataFrame,
    cwms_unit: str | None,
    usgs_time_series_id: str,
    begin: datetime,
    end: datetime,
    value_tolerance: float,
    min_records: int,
    min_agreement_percent: float,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """
    Compare one candidate USGS time_series_id against existing CWMS data.

    Returns
    -------
    summary : dict
        One summary record for the candidate time-series comparison.

    detail_df : pandas.DataFrame
        One row for every timestamp-aligned CWMS/new-USGS observation.
        This includes both matching and nonmatching values. The caller filters
        rows to failed candidate series before writing the mismatch report.
    """

    empty_detail_df = pd.DataFrame(columns=COMPARISON_BASE_DETAIL_COLUMNS)

    result = {
        "time_series_id": usgs_time_series_id,
        "cwms_record_count": len(cwms_df),
        "usgs_record_count": 0,
        "matched_record_count": 0,
        "agreement_record_count": 0,
        "agreement_percent": None,
        "mean_absolute_difference": None,
        "max_absolute_difference": None,
        "cwms_unit": cwms_unit,
        "usgs_unit": None,
        "unit_conversion_applied": False,
        "comparison_status": "unreviewed",
        "comparison_error": None,
    }

    try:
        if cwms_df.empty:
            result["comparison_status"] = "no_cwms_values"
            return result, empty_detail_df

        usgs_df, usgs_unit = get_usgs_comparison_values(
            usgs_time_series_id=usgs_time_series_id,
            begin=begin,
            end=end,
        )

        result["usgs_record_count"] = len(usgs_df)
        result["usgs_unit"] = usgs_unit

        if usgs_df.empty:
            result["comparison_status"] = "no_usgs_values"
            return result, empty_detail_df

        converted_values, conversion_applied = convert_usgs_to_cwms_unit(
            usgs_values=usgs_df["usgs_value"],
            usgs_unit=usgs_unit,
            cwms_unit=cwms_unit,
        )

        usgs_df["usgs_value"] = converted_values
        result["unit_conversion_applied"] = conversion_applied

        comparison_df = pd.merge_asof(
            cwms_df.sort_values("date-time"),
            usgs_df.sort_values("time"),
            left_on="date-time",
            right_on="time",
            direction="nearest",
            tolerance=pd.Timedelta("2min"),
        )

        comparison_df = comparison_df.dropna(subset=["usgs_value"]).copy()

        result["matched_record_count"] = len(comparison_df)

        if comparison_df.empty:
            result["comparison_status"] = "no_timestamp_matches"
            return result, empty_detail_df

        comparison_df["absolute_difference"] = (
            comparison_df["cwms_value"] - comparison_df["usgs_value"]
        ).abs()

        comparison_df["within_tolerance"] = (
            comparison_df["absolute_difference"] <= value_tolerance
        )

        result["agreement_record_count"] = int(comparison_df["within_tolerance"].sum())

        result["agreement_percent"] = round(
            100.0 * result["agreement_record_count"] / result["matched_record_count"],
            2,
        )

        result["mean_absolute_difference"] = round(
            float(comparison_df["absolute_difference"].mean()),
            6,
        )

        result["max_absolute_difference"] = round(
            float(comparison_df["absolute_difference"].max()),
            6,
        )

        if result["matched_record_count"] < min_records:
            result["comparison_status"] = "insufficient_overlap"

        elif result["agreement_percent"] >= min_agreement_percent:
            result["comparison_status"] = "values_agree"

        else:
            result["comparison_status"] = "values_do_not_agree"

        # Keep all timestamp-aligned values, not only mismatches.
        detail_df = comparison_df.copy()

        detail_df["time_delta_seconds"] = (
            detail_df["date-time"] - detail_df["time"]
        ).dt.total_seconds()

        detail_df["time_series_id"] = usgs_time_series_id
        detail_df["cwms_unit"] = cwms_unit
        detail_df["usgs_unit"] = usgs_unit
        detail_df["unit_conversion_applied"] = conversion_applied
        detail_df["comparison_status"] = result["comparison_status"]

        detail_df["comparison_result"] = detail_df["within_tolerance"].map(
            {
                True: "within_tolerance",
                False: "outside_tolerance",
            }
        )

        detail_df = detail_df.rename(
            columns={
                "date-time": "cwms_time",
                "time": "usgs_time",
                "usgs_value": "usgs_value_comparison",
            }
        )

        # These are only CWMS/new-USGS fields. Station, parameter, method ID,
        # and old-USGS values are added later by
        # add_legacy_usgs_values_to_mismatches().
        detail_df = detail_df.reindex(columns=COMPARISON_BASE_DETAIL_COLUMNS)

        return result, detail_df

    except Exception as error:
        result["comparison_status"] = "comparison_error"
        result["comparison_error"] = str(error)

        return result, empty_detail_df


def compare_unaliased_usgs_query_to_cwms(
    cwms_df: pd.DataFrame,
    cwms_unit: str | None,
    monitoring_location_id: str,
    usgs_parameter: str,
    metadata_time_series_ids: list[str],
    begin: datetime,
    end: datetime,
    value_tolerance: float,
    min_records: int,
    min_agreement_percent: float,
) -> dict[str, Any]:
    """
    Test whether a CWMS TSID can safely use a blank alias-id.

    A blank alias is allowed only when:
        1. The direct station/parameter query returns exactly one USGS
           time_series_id.
        2. The returned values agree with CWMS.
    """

    result = {
        "monitoring_location_id": monitoring_location_id,
        "USGS_PARAMETER": usgs_parameter,
        "unaliased_returned_time_series_ids": None,
        "unaliased_returned_time_series_count": 0,
        "unaliased_metadata_time_series_ids": None,
        "unaliased_metadata_time_series_count": 0,
        "unaliased_metadata_matches_returned_id": False,
        "unaliased_comparison_status": "unreviewed",
        "unaliased_agreement_percent": None,
        "unaliased_matched_record_count": 0,
        "unaliased_mean_absolute_difference": None,
        "unaliased_max_absolute_difference": None,
        "unaliased_usgs_unit": None,
        "unaliased_error": None,
    }

    try:
        metadata_time_series_ids = sorted(
            {
                str(time_series_id)
                for time_series_id in metadata_time_series_ids
                if pd.notna(time_series_id)
            }
        )

        result["unaliased_metadata_time_series_ids"] = ",".join(
            metadata_time_series_ids
        )

        result["unaliased_metadata_time_series_count"] = len(metadata_time_series_ids)

        if cwms_df.empty:
            result["unaliased_comparison_status"] = "no_cwms_values"
            return result

        usgs_df, usgs_unit, returned_ids = get_usgs_unaliased_comparison_values(
            monitoring_location_id=monitoring_location_id,
            usgs_parameter=usgs_parameter,
            begin=begin,
            end=end,
        )

        result["unaliased_usgs_unit"] = usgs_unit
        result["unaliased_returned_time_series_ids"] = ",".join(returned_ids)
        result["unaliased_returned_time_series_count"] = len(returned_ids)

        if usgs_df.empty:
            result["unaliased_comparison_status"] = "unaliased_query_no_values"
            return result

        # More than one returned UUID means the future ingestion routine
        # cannot safely determine which source series to use without alias-id.
        # Metadata is the authoritative inventory of available continuous
        # series. Do not clear alias-id if station + parameter metadata shows
        # multiple candidate source series, even if their current values happen
        # to match during this comparison window.
        if len(metadata_time_series_ids) == 0:
            result["unaliased_comparison_status"] = "unaliased_metadata_no_time_series"
            return result

        if len(metadata_time_series_ids) > 1:
            result["unaliased_comparison_status"] = (
                "unaliased_metadata_multiple_time_series"
            )
            return result

        # The unaliased continuous request itself must return exactly one
        # time_series_id.
        if len(returned_ids) != 1:
            result["unaliased_comparison_status"] = (
                "unaliased_query_multiple_time_series"
            )
            return result

        metadata_time_series_id = metadata_time_series_ids[0]
        returned_time_series_id = returned_ids[0]

        result["unaliased_metadata_matches_returned_id"] = (
            metadata_time_series_id == returned_time_series_id
        )

        # The API response must return the same ID that metadata identifies
        # for this station/parameter request.
        if not result["unaliased_metadata_matches_returned_id"]:
            result["unaliased_comparison_status"] = (
                "unaliased_metadata_returned_id_mismatch"
            )
            return result

        converted_values, _ = convert_usgs_to_cwms_unit(
            usgs_values=usgs_df["usgs_value"],
            usgs_unit=usgs_unit,
            cwms_unit=cwms_unit,
        )

        usgs_df["usgs_value"] = converted_values

        comparison_df = pd.merge_asof(
            cwms_df.sort_values("date-time"),
            usgs_df.sort_values("time"),
            left_on="date-time",
            right_on="time",
            direction="nearest",
            tolerance=pd.Timedelta("2min"),
        )

        comparison_df = comparison_df.dropna(subset=["usgs_value"]).copy()

        result["unaliased_matched_record_count"] = len(comparison_df)

        if len(comparison_df) < min_records:
            result["unaliased_comparison_status"] = "insufficient_overlap"
            return result

        comparison_df["absolute_difference"] = (
            comparison_df["cwms_value"] - comparison_df["usgs_value"]
        ).abs()

        within_tolerance = comparison_df["absolute_difference"] <= value_tolerance

        agreement_percent = round(
            100.0 * float(within_tolerance.sum()) / len(comparison_df),
            2,
        )

        result["unaliased_agreement_percent"] = agreement_percent

        result["unaliased_mean_absolute_difference"] = round(
            float(comparison_df["absolute_difference"].mean()),
            6,
        )

        result["unaliased_max_absolute_difference"] = round(
            float(comparison_df["absolute_difference"].max()),
            6,
        )

        if agreement_percent >= min_agreement_percent:
            result["unaliased_comparison_status"] = "unaliased_values_agree"
        else:
            result["unaliased_comparison_status"] = (
                "unaliased_query_values_do_not_agree"
            )

        return result

    except Exception as error:
        result["unaliased_comparison_status"] = "unaliased_query_error"
        result["unaliased_error"] = str(error)

        return result


def compare_unaliased_crosswalk_to_cwms(
    crosswalk: pd.DataFrame,
    new_metadata: pd.DataFrame,
    begin: datetime,
    end: datetime,
    value_tolerance: float,
    min_records: int,
    min_agreement_percent: float,
) -> pd.DataFrame:
    """
    Test whether each configured CWMS TSID can retrieve the correct USGS data
    using only monitoring_location_id and USGS_PARAMETER.

    A successful result means the CWMS alias-id may be cleared to "" because
    the future USGS retrieval routine does not need a time_series_id.
    """

    output_columns = [
        "office-id",
        "timeseries-id",
        "monitoring_location_id",
        "USGS_PARAMETER",
        "unaliased_returned_time_series_ids",
        "unaliased_returned_time_series_count",
        "unaliased_metadata_time_series_ids",
        "unaliased_metadata_time_series_count",
        "unaliased_metadata_matches_returned_id",
        "unaliased_comparison_status",
        "unaliased_agreement_percent",
        "unaliased_matched_record_count",
        "unaliased_mean_absolute_difference",
        "unaliased_max_absolute_difference",
        "unaliased_usgs_unit",
        "unaliased_error",
    ]

    required_columns = {
        "office-id",
        "timeseries-id",
        "monitoring_location_id",
        "USGS_PARAMETER",
    }

    missing_columns = required_columns.difference(crosswalk.columns)

    if missing_columns:
        raise RuntimeError(
            "Cannot perform unaliased USGS comparison because the crosswalk "
            f"is missing columns: {sorted(missing_columns)}"
        )

    # Multiple candidate time_series_id rows may exist for the same CWMS
    # TSID. The unaliased request is performed only once per TSID/station/param.
    request_df = crosswalk[
        [
            "office-id",
            "timeseries-id",
            "monitoring_location_id",
            "USGS_PARAMETER",
        ]
    ].drop_duplicates()

    request_df = request_df.dropna(
        subset=[
            "office-id",
            "timeseries-id",
            "monitoring_location_id",
            "USGS_PARAMETER",
        ]
    )

    if request_df.empty:
        return pd.DataFrame(columns=output_columns)

    comparison_rows = []
    required_metadata_columns = {
        "monitoring_location_id",
        "USGS_PARAMETER",
        "time_series_id",
    }

    missing_metadata_columns = required_metadata_columns.difference(
        new_metadata.columns
    )

    if missing_metadata_columns:
        raise RuntimeError(
            "Cannot perform unaliased metadata validation because new "
            "metadata is missing columns: "
            f"{sorted(missing_metadata_columns)}"
        )

    for _, request_row in request_df.iterrows():
        office_id = request_row["office-id"]
        cwms_tsid = request_row["timeseries-id"]
        monitoring_location_id = request_row["monitoring_location_id"]
        usgs_parameter = request_row["USGS_PARAMETER"]
        metadata_time_series_ids = (
            new_metadata.loc[
                (new_metadata["monitoring_location_id"] == monitoring_location_id)
                & (new_metadata["USGS_PARAMETER"] == usgs_parameter),
                "time_series_id",
            ]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        logging.info(
            "Testing unaliased USGS retrieval for CWMS TSID %s using %s, "
            "parameter %s.",
            cwms_tsid,
            monitoring_location_id,
            usgs_parameter,
        )

        try:
            cwms_df, cwms_unit = get_cwms_comparison_values(
                cwms_tsid=cwms_tsid,
                office_id=office_id,
                begin=begin,
                end=end,
            )

            comparison = compare_unaliased_usgs_query_to_cwms(
                cwms_df=cwms_df,
                cwms_unit=cwms_unit,
                monitoring_location_id=monitoring_location_id,
                usgs_parameter=usgs_parameter,
                metadata_time_series_ids=metadata_time_series_ids,
                begin=begin,
                end=end,
                value_tolerance=value_tolerance,
                min_records=min_records,
                min_agreement_percent=min_agreement_percent,
            )

        except Exception as error:
            comparison = {
                "monitoring_location_id": monitoring_location_id,
                "USGS_PARAMETER": usgs_parameter,
                "unaliased_returned_time_series_ids": None,
                "unaliased_returned_time_series_count": 0,
                "unaliased_metadata_time_series_ids": None,
                "unaliased_metadata_time_series_count": 0,
                "unaliased_metadata_matches_returned_id": False,
                "unaliased_comparison_status": "cwms_read_error",
                "unaliased_agreement_percent": None,
                "unaliased_matched_record_count": 0,
                "unaliased_mean_absolute_difference": None,
                "unaliased_max_absolute_difference": None,
                "unaliased_usgs_unit": None,
                "unaliased_error": str(error),
            }

        comparison_rows.append(
            {
                "office-id": office_id,
                "timeseries-id": cwms_tsid,
                **comparison,
            }
        )

    unaliased_df = pd.DataFrame(comparison_rows)

    return unaliased_df.reindex(columns=output_columns)


def compare_crosswalk_to_cwms(
    crosswalk: pd.DataFrame,
    begin: datetime,
    end: datetime,
    value_tolerance: float,
    min_records: int,
    min_agreement_percent: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Compare USGS candidate IDs in the crosswalk against existing CWMS values.

    Returns
    -------
    comparison_df : pandas.DataFrame
        One summary row per CWMS TSID / candidate USGS time_series_id pair.

    detail_df : pandas.DataFrame
        All timestamp-aligned CWMS/new-USGS observations. Includes both
        within-tolerance and outside-tolerance rows.
    """

    candidates = crosswalk.loc[crosswalk["time_series_id"].notna()].copy()

    empty_comparison_df = pd.DataFrame(
        columns=[
            "office-id",
            "timeseries-id",
            "time_series_id",
            "cwms_record_count",
            "usgs_record_count",
            "matched_record_count",
            "agreement_record_count",
            "agreement_percent",
            "mean_absolute_difference",
            "max_absolute_difference",
            "cwms_unit",
            "usgs_unit",
            "unit_conversion_applied",
            "comparison_status",
            "comparison_error",
        ]
    )

    empty_detail_df = pd.DataFrame(
        columns=[
            "office-id",
            "timeseries-id",
            *COMPARISON_BASE_DETAIL_COLUMNS,
        ]
    )

    if candidates.empty:
        return empty_comparison_df, empty_detail_df

    comparison_rows = []
    detail_frames = []

    for (office_id, cwms_tsid), candidate_group in candidates.groupby(
        ["office-id", "timeseries-id"],
        dropna=False,
    ):
        logging.info(
            "Comparing CWMS TSID %s against %s USGS candidate(s).",
            cwms_tsid,
            len(candidate_group),
        )

        try:
            cwms_df, cwms_unit = get_cwms_comparison_values(
                cwms_tsid=cwms_tsid,
                office_id=office_id,
                begin=begin,
                end=end,
            )

        except Exception as error:
            cwms_read_error = str(error)

            for usgs_time_series_id in candidate_group["time_series_id"].unique():
                comparison_rows.append(
                    {
                        "office-id": office_id,
                        "timeseries-id": cwms_tsid,
                        "time_series_id": usgs_time_series_id,
                        "cwms_record_count": 0,
                        "usgs_record_count": 0,
                        "matched_record_count": 0,
                        "agreement_record_count": 0,
                        "agreement_percent": None,
                        "mean_absolute_difference": None,
                        "max_absolute_difference": None,
                        "cwms_unit": None,
                        "usgs_unit": None,
                        "unit_conversion_applied": False,
                        "comparison_status": "cwms_read_error",
                        "comparison_error": cwms_read_error,
                    }
                )

            continue

        for usgs_time_series_id in candidate_group["time_series_id"].unique():
            comparison, detail_df = compare_usgs_candidate_to_cwms(
                cwms_df=cwms_df,
                cwms_unit=cwms_unit,
                usgs_time_series_id=usgs_time_series_id,
                begin=begin,
                end=end,
                value_tolerance=value_tolerance,
                min_records=min_records,
                min_agreement_percent=min_agreement_percent,
            )

            comparison_rows.append(
                {
                    "office-id": office_id,
                    "timeseries-id": cwms_tsid,
                    **comparison,
                }
            )

            if not detail_df.empty:
                detail_df = detail_df.copy()

                # Add only fields available at this stage.
                detail_df["office-id"] = office_id
                detail_df["timeseries-id"] = cwms_tsid

                detail_df = detail_df.reindex(
                    columns=[
                        "office-id",
                        "timeseries-id",
                        *COMPARISON_BASE_DETAIL_COLUMNS,
                    ]
                )

                detail_frames.append(detail_df)

    comparison_df = pd.DataFrame(comparison_rows)

    if detail_frames:
        detail_df = pd.concat(
            detail_frames,
            ignore_index=True,
        )
    else:
        detail_df = empty_detail_df

    return comparison_df, detail_df


def add_legacy_usgs_values_to_mismatches(
    mismatch_df: pd.DataFrame,
    crosswalk: pd.DataFrame,
    begin: datetime,
    end: datetime,
) -> pd.DataFrame:
    """
    Add old-USGS WaterServices values to CWMS/new-USGS mismatch records.

    The old API request uses:
        USGS station number
        USGS parameter code
        legacy methodID

    from the migration crosswalk.
    """

    if mismatch_df.empty:
        return pd.DataFrame(columns=COMPARISON_DETAIL_COLUMNS)

    mapping_columns = [
        "office-id",
        "timeseries-id",
        "time_series_id",
        "USGS_St_Num",
        "USGS_PARAMETER",
        "legacy_method_id",
    ]

    available_mapping_columns = [
        column for column in mapping_columns if column in crosswalk.columns
    ]

    mapping_df = crosswalk[available_mapping_columns].drop_duplicates()

    output_df = mismatch_df.merge(
        mapping_df,
        how="left",
        on=[
            "office-id",
            "timeseries-id",
            "time_series_id",
        ],
    )

    for column in [
        "old_usgs_time",
        "old_usgs_value",
        "old_usgs_qualifiers",
        "old_usgs_unit",
    ]:
        if column not in output_df.columns:
            output_df[column] = None

    output_df["old_usgs_status"] = "not_requested"

    result_frames = []

    lookup_columns = [
        "USGS_St_Num",
        "USGS_PARAMETER",
        "legacy_method_id",
    ]

    # Records without a usable legacy method mapping cannot be queried.
    missing_mapping_df = output_df.loc[
        output_df["USGS_St_Num"].isna()
        | output_df["USGS_PARAMETER"].isna()
        | output_df["legacy_method_id"].isna()
    ].copy()

    if not missing_mapping_df.empty:
        missing_mapping_df["old_usgs_status"] = "legacy_mapping_missing"
        result_frames.append(missing_mapping_df)

    queryable_df = output_df.loc[
        output_df["USGS_St_Num"].notna()
        & output_df["USGS_PARAMETER"].notna()
        & output_df["legacy_method_id"].notna()
    ].copy()

    for lookup_values, detail_group in queryable_df.groupby(
        lookup_columns,
        dropna=False,
    ):
        station_number, parameter_code, method_id = lookup_values
        detail_group = detail_group.copy()

        logging.info(
            "Retrieving old USGS values for station %s, parameter %s, methodID %s.",
            station_number,
            parameter_code,
            method_id,
        )

        try:
            old_df = get_legacy_usgs_method_values(
                usgs_station_number=station_number,
                usgs_parameter=parameter_code,
                legacy_method_id=method_id,
                begin=begin,
                end=end,
            )

        except Exception as error:
            detail_group["old_usgs_status"] = "old_usgs_request_error"
            detail_group["old_usgs_status_detail"] = str(error)
            result_frames.append(detail_group)
            continue

        if old_df.empty:
            detail_group["old_usgs_status"] = "no_old_usgs_values"
            result_frames.append(detail_group)
            continue

        # Remove placeholder old-USGS columns before merge_asof.
        detail_group = detail_group.drop(
            columns=[
                "old_usgs_time",
                "old_usgs_value",
                "old_usgs_qualifiers",
                "old_usgs_unit",
            ],
            errors="ignore",
        )

        detail_group = detail_group.sort_values("cwms_time")
        old_df = old_df.sort_values("old_usgs_time")

        merged_df = pd.merge_asof(
            detail_group,
            old_df,
            left_on="cwms_time",
            right_on="old_usgs_time",
            direction="nearest",
            tolerance=pd.Timedelta("2min"),
        )

        merged_df["old_usgs_status"] = "old_usgs_value_returned"

        merged_df.loc[
            merged_df["old_usgs_value"].isna(),
            "old_usgs_status",
        ] = "no_old_usgs_timestamp_match"

        result_frames.append(merged_df)

    if not result_frames:
        return pd.DataFrame(columns=COMPARISON_DETAIL_COLUMNS)

    result_df = pd.concat(
        result_frames,
        ignore_index=True,
    )

    for column in COMPARISON_DETAIL_COLUMNS:
        if column not in result_df.columns:
            result_df[column] = None

    # reindex creates missing columns as null instead of raising KeyError.
    # For example, old-USGS fields may be null when the old endpoint has no
    # data or no timestamp within the two-minute matching tolerance.
    result_df = result_df.reindex(columns=COMPARISON_DETAIL_COLUMNS)

    return result_df.sort_values(
        [
            "office-id",
            "timeseries-id",
            "time_series_id",
            "cwms_time",
        ]
    ).reset_index(drop=True)


def apply_cwms_alias_updates(
    patch_df: pd.DataFrame,
    apply: bool,
) -> None:
    """
    Patch the matching CWMS group assignments.

    replace_assigned_ts=False preserves the rest of the group assignments.
    """

    if patch_df.empty:
        logging.warning("No matched group assignments are available to update.")
        return

    logging.info("Prepared %s CWMS alias-id update(s).", len(patch_df))

    for _, row in patch_df.iterrows():
        logging.info(
            "CWMS TSID: %s | new alias-id: %s",
            row["timeseries-id"],
            row["alias-id"],
        )

    if not apply:
        logging.warning(
            colors.c(
                "DRY RUN: No CWMS group assignments were changed.",
                "yellow",
                bright=True,
            )
        )
        return

    payload = cwms.timeseries_group_df_to_json(
        data=patch_df,
        group_id=GROUP_ID,
        group_office_id=GROUP_OFFICE_ID,
        category_office_id=CATEGORY_OFFICE_ID,
        category_id=CATEGORY_ID,
    )

    cwms.update_timeseries_groups(
        data=payload,
        group_id=GROUP_ID,
        office_id=GROUP_OFFICE_ID,
        replace_assigned_ts=False,
    )

    logging.info(
        colors.c(
            f"SUCCESS: Updated {len(patch_df)} CWMS alias-id value(s).",
            "green",
            bright=True,
        )
    )


def run_migration(args: SimpleNamespace) -> None:
    """Execute the USGS methodID-to-time_series_id migration."""

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    init_cwms_session(
        cwms,
        api_root=args.api_root,
        api_key="apikey " + args.api_key,
    )

    logging.info("CDA connection: %s", args.api_root)
    logging.info("Target office: %s", args.office)

    configured_ts = get_CMWS_TS_Loc_Data(args.office).copy()

    if configured_ts.empty:
        raise RuntimeError(
            f"No configured USGS time series were found for office {args.office}."
        )

    # Optional test subset.
    if args.timeseries_ids:
        requested_tsids = set(args.timeseries_ids)

        configured_ts = configured_ts.loc[
            configured_ts["timeseries-id"].isin(requested_tsids)
        ].copy()

        found_tsids = set(configured_ts["timeseries-id"].dropna().unique())
        missing_tsids = sorted(requested_tsids.difference(found_tsids))

        if missing_tsids:
            logging.warning(
                "Requested TSID(s) not found for office %s: %s",
                args.office,
                ", ".join(missing_tsids),
            )

        if configured_ts.empty:
            raise RuntimeError(
                "None of the requested time-series IDs were found in the "
                f"USGS TS Data Acquisition group for office {args.office}."
            )

        logging.info(
            "Restricted migration to %s configured time series.",
            len(configured_ts),
        )

    configured_ts["legacy_method_id"] = configured_ts["USGS_Method_TS"].map(
        normalize_method_id
    )

    legacy_configured_ts = configured_ts.loc[
        configured_ts["legacy_method_id"].notna()
    ].copy()

    if legacy_configured_ts.empty:
        logging.warning(
            "No numeric legacy method IDs were found in alias-id values. "
            "No migration is required."
        )
        return

    logging.info(
        "Found %s time series with numeric legacy method IDs.",
        len(legacy_configured_ts),
    )

    current_group = get_current_group_assignments(args.office)

    if args.legacy_methods_csv:
        legacy_methods = load_legacy_methods_csv(Path(args.legacy_methods_csv))

        logging.info(
            "Loaded %s legacy method record(s) from %s.",
            len(legacy_methods),
            args.legacy_methods_csv,
        )
    else:
        legacy_methods = fetch_legacy_method_descriptions(
            legacy_configured_ts[
                [
                    "USGS_St_Num",
                    "USGS_PARAMETER",
                ]
            ].drop_duplicates(),
            chunk_size=args.legacy_chunk_size,
        )

        logging.info(
            "Retrieved %s legacy method record(s).",
            len(legacy_methods),
        )

    write_csv(
        legacy_methods,
        output_dir / f"legacy_methods_{args.office}_{timestamp}.csv",
    )

    new_metadata = get_new_usgs_timeseries_metadata(
        legacy_configured_ts[
            [
                "USGS_St_Num",
                "USGS_PARAMETER",
            ]
        ].drop_duplicates()
    )

    write_csv(
        new_metadata,
        output_dir / f"new_usgs_metadata_{args.office}_{timestamp}.csv",
    )

    if new_metadata.empty:
        raise RuntimeError(
            "No new USGS time-series metadata was returned. "
            "No CWMS aliases were changed."
        )

    crosswalk = build_crosswalk(
        configured_ts=legacy_configured_ts,
        legacy_methods=legacy_methods,
        new_metadata=new_metadata,
    )

    crosswalk["metadata_mapping_status"] = crosswalk["mapping_status"]
    # For records where the legacy methodDescription did not match new USGS
    # metadata, add all continuous USGS candidate IDs for the same station
    # and parameter. The candidates can then be evaluated by value comparison.
    crosswalk = add_station_parameter_fallback_candidates(
        crosswalk=crosswalk,
        new_metadata=new_metadata,
    )

    if args.compare_timeseries:
        comparison_end = datetime.now(timezone.utc)
        comparison_begin = comparison_end - timedelta(days=args.compare_days)

        logging.info(
            "Comparing CWMS and USGS values from %s through %s.",
            comparison_begin.isoformat(),
            comparison_end.isoformat(),
        )

        # The revised comparison routine returns two DataFrames:
        #
        #   comparison_df:
        #       One summary row per CWMS TSID / USGS candidate pair.
        #
        #   mismatch_df:
        #       One row per timestamp where CWMS and USGS values differ by
        #       more than --comparison-tolerance.
        comparison_df, detail_df = compare_crosswalk_to_cwms(
            crosswalk=crosswalk,
            begin=comparison_begin,
            end=comparison_end,
            value_tolerance=args.comparison_tolerance,
            min_records=args.comparison_min_records,
            min_agreement_percent=args.comparison_min_agreement,
        )

        # Existing summary report.
        write_csv(
            comparison_df,
            output_dir / f"cwms_usgs_value_comparison_{args.office}_{timestamp}.csv",
        )

        # New observation-level mismatch report.
        # Create the exception report: only observation rows whose CWMS and
        # new-USGS values exceeded --comparison-tolerance.
        # Include every aligned comparison row for candidate series that
        # failed the overall CWMS/new-USGS comparison. This includes both
        # within-tolerance and outside-tolerance observations.
        mismatch_df = detail_df.loc[
            detail_df["comparison_status"].eq("values_do_not_agree")
        ].copy()

        # Add old-USGS WaterServices values using the configured legacy
        # methodID. This is reporting only; it does not alter the mapping.
        if not mismatch_df.empty:
            mismatch_df = add_legacy_usgs_values_to_mismatches(
                mismatch_df=mismatch_df,
                crosswalk=crosswalk,
                begin=comparison_begin,
                end=comparison_end,
            )

        write_csv(
            mismatch_df,
            output_dir / f"cwms_usgs_value_mismatches_{args.office}_{timestamp}.csv",
        )

        logging.info(
            "Recorded %s aligned CWMS/new-USGS comparison row(s) for "
            "candidate series with values_do_not_agree status.",
            len(mismatch_df),
        )

        # Add comparison summary columns back onto the crosswalk so they
        # appear in the main migration report and can gate --apply updates.
        crosswalk = crosswalk.merge(
            comparison_df,
            how="left",
            on=[
                "office-id",
                "timeseries-id",
                "time_series_id",
            ],
        )

        # First resolve cases where metadata returned multiple USGS candidate
        # IDs but exactly one candidate's values agrees with CWMS.
        crosswalk = resolve_ambiguous_mappings_by_comparison(crosswalk)

        # Then test whether the future USGS retrieval process can obtain the
        # correct data with only station number and parameter code, without
        # using any time_series_id at all.
        unaliased_comparison_df = compare_unaliased_crosswalk_to_cwms(
            crosswalk=crosswalk,
            new_metadata=new_metadata,
            begin=comparison_begin,
            end=comparison_end,
            value_tolerance=args.comparison_tolerance,
            min_records=args.comparison_min_records,
            min_agreement_percent=args.comparison_min_agreement,
        )

        write_csv(
            unaliased_comparison_df,
            output_dir
            / f"cwms_usgs_unaliased_comparison_{args.office}_{timestamp}.csv",
        )

        # If the direct station/parameter query returned exactly one USGS
        # series and agreed with CWMS, mark the record for a blank alias-id.
        # This is deliberately performed after UUID comparison resolution so
        # an unaliased success takes precedence over a UUID alias assignment.
        crosswalk = resolve_unaliased_mappings_by_comparison(
            crosswalk=crosswalk,
            unaliased_comparison_df=unaliased_comparison_df,
        )

    else:
        crosswalk["comparison_status"] = "not_requested"
        crosswalk["comparison_error"] = None

    for column in REPORT_COLUMNS:
        if column not in crosswalk.columns:
            crosswalk[column] = None

    crosswalk = crosswalk[REPORT_COLUMNS].copy()

    write_csv(
        crosswalk,
        output_dir
        / f"methodid_to_timeseriesid_crosswalk_{args.office}_{timestamp}.csv",
    )

    update_plan = create_update_plan(
        crosswalk=crosswalk,
        require_comparison=args.compare_timeseries,
    )

    write_csv(
        update_plan,
        output_dir / f"cwms_alias_update_plan_{args.office}_{timestamp}.csv",
    )

    summary = (
        crosswalk["mapping_status"]
        .value_counts(dropna=False)
        .rename_axis("mapping_status")
        .reset_index(name="count")
    )

    write_csv(
        summary,
        output_dir / f"migration_summary_{args.office}_{timestamp}.csv",
    )

    logging.info("Migration summary:")

    for _, row in summary.iterrows():
        logging.info(
            "  %-45s %s",
            row["mapping_status"],
            row["count"],
        )

    if update_plan.empty:
        logging.warning(
            "No unambiguous mappings were found. No CWMS aliases were changed."
        )
        return

    patch_df = build_patch_dataframe(
        current_group=current_group,
        update_plan=update_plan,
    )

    write_csv(
        patch_df,
        output_dir / f"cwms_alias_patch_{args.office}_{timestamp}.csv",
    )

    apply_cwms_alias_updates(
        patch_df=patch_df,
        apply=args.apply,
    )


def migrate_usgs_timeseries_ids(
    api_root: str,
    office_id: str,
    api_key: str,
    output_dir: str,
    legacy_methods_csv: str | None = None,
    apply: bool = False,
    timeseries_ids: list[str] | None = None,
    legacy_chunk_size: int = 100,
    compare_timeseries: bool = False,
    compare_days: int = 7,
    comparison_tolerance: float = 0.001,
    comparison_min_records: int = 20,
    comparison_min_agreement: float = 95.0,
) -> None:
    """
    Click-command entry function for the USGS time-series-ID migration.
    """

    if legacy_chunk_size < 1:
        raise ValueError("legacy_chunk_size must be at least 1.")

    if apply:
        logging.warning(
            colors.c(
                "APPLY MODE ENABLED: Eligible CWMS alias-id values will be updated.",
                "yellow",
                bright=True,
            )
        )
    else:
        logging.warning(
            colors.c(
                "DRY-RUN MODE: No CWMS group assignments will be changed.",
                "yellow",
                bright=True,
            )
        )
    if compare_days < 1:
        raise ValueError("compare_days must be at least 1.")

    if comparison_tolerance < 0:
        raise ValueError("comparison_tolerance cannot be negative.")

    if comparison_min_records < 1:
        raise ValueError("comparison_min_records must be at least 1.")

    if not 0 <= comparison_min_agreement <= 100:
        raise ValueError("comparison_min_agreement must be between 0 and 100.")

    options = SimpleNamespace(
        api_root=api_root,
        office=office_id,
        api_key=api_key,
        output_dir=output_dir,
        legacy_methods_csv=legacy_methods_csv,
        apply=apply,
        timeseries_ids=timeseries_ids,
        legacy_chunk_size=legacy_chunk_size,
        compare_timeseries=compare_timeseries,
        compare_days=compare_days,
        comparison_tolerance=comparison_tolerance,
        comparison_min_records=comparison_min_records,
        comparison_min_agreement=comparison_min_agreement,
    )

    run_migration(options)
