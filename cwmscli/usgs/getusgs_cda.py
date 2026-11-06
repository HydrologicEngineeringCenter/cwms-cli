import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

import cwms
import numpy as np
import pandas as pd
from dataretrieval import waterdata

from cwmscli.utils import colors, init_cwms_session
from cwmscli.utils.friendly_errors import is_fatal_service_error

def _log_error_and_exit(
    message: str, hint: Optional[str] = None, *, exit_code: int = 1
):
    logging.error(colors.c(message, "red", bright=True))
    if hint:
        logging.error(colors.c(f"Hint: {hint}", "yellow", bright=True))
    raise SystemExit(exit_code)


def _require_group_dataframe(response, *, resource_name: str, office: str):
    payload = getattr(response, "json", None)

    try:
        df = response.df
    except AttributeError as exc:
        if isinstance(payload, str):
            _log_error_and_exit(
                f"CWMS returned an unexpected response while reading {resource_name} for office {office}.",
                "Check that --api-root points to the CDA API endpoint ending in /cwms-data.",
            )
        raise

    if df is None:
        _log_error_and_exit(
            f"CWMS did not return any {resource_name} data for office {office}."
        )

    return df

def getusgs_cda(
    api_root: str,
    office_id: str,
    days_back: float,
    api_key: str,
    revision_lookback_days: float | None = None,
    backfill_tsids: list = None,
    backfill_version: str = None,
):
    """
    Retrieve USGS continuous values through the new USGS Water Data API and
    store them in CWMS.

    CWMS Data Acquisition / USGS TS Data Acquisition alias-id behavior:

        alias-id is null:
            Query USGS by monitoring location and parameter code.

        alias-id contains a new USGS time_series_id:
            Query USGS directly by time_series_id.

    Numeric legacy method IDs are no longer supported by this workflow.
    """

    init_cwms_session(
        cwms,
        api_root=api_root,
        api_key="apikey " + api_key,
    )

    logging.info("CDA connection: %s", api_root)
    logging.info(
        "USGS continuous values will be retrieved for the previous %s day(s) "
        "for office %s.",
        days_back,
        office_id,
    )

    execution_date = datetime.now(timezone.utc)

    # Preserve the original --days-back behavior unless the caller
    # specifically asks to include older observations that were revised
    # during the modification window.
    if revision_lookback_days is None:
        revision_lookback_days = days_back

    if revision_lookback_days < 0:
        raise ValueError(
            "revision_lookback_days cannot be negative."
        )

    usgs_ts = get_CMWS_TS_Loc_Data(office_id)

    if backfill_tsids:
        usgs_ts = usgs_ts.loc[
            usgs_ts["timeseries-id"].isin(backfill_tsids)
        ].copy()

    usgs_ts = _validate_backfill_version_timeseries(
        usgs_ts,
        backfill_version,
        office_id,
    )

    if usgs_ts.empty:
        if backfill_tsids:
            _log_error_and_exit(
                "The requested backfill time-series IDs were not present in "
                "the USGS time-series or location-alias groups: "
                f"{backfill_tsids}"
            )

        _log_error_and_exit(
            f"No eligible USGS time series were found for office {office_id}.",
            "Confirm that time series exist in Data Acquisition / "
            "USGS TS Data Acquisition and that matching entries exist in "
            "Agency Aliases / USGS Station Number.",
        )

    # Do not silently interpret old numeric method IDs as new UUIDs.
    legacy_alias_mask = (
        usgs_ts["USGS_Time_Series_ID"].notna()
        & usgs_ts["USGS_Time_Series_ID"]
        .astype("string")
        .str.fullmatch(r"\d+")
    )

    if legacy_alias_mask.any():
        legacy_tsids = usgs_ts.loc[
            legacy_alias_mask,
            "timeseries-id",
        ].tolist()

        logging.warning(
            "The following CWMS TSIDs still have numeric legacy USGS method "
            "IDs in alias-id and cannot be retrieved by the new API until "
            "they are migrated: %s",
            legacy_tsids,
        )

        usgs_ts = usgs_ts.loc[~legacy_alias_mask].copy()

    if usgs_ts.empty:
        _log_error_and_exit(
            "No eligible USGS time series remain after excluding legacy "
            "numeric method-ID aliases.",
            "Run 'usgs migrate-timeseries-ids' and review the migration "
            "reports before running USGS acquisition.",
        )

    # --days-back controls the last-modified window.
    modified_start_dt = execution_date - timedelta(days=days_back)
    modified_end_dt = execution_date

    # When omitted, preserve the previous behavior: only retrieve
    # observations that occurred during the --days-back window.
    if revision_lookback_days is None:
        revision_lookback_days = days_back

    if revision_lookback_days < 0:
        raise ValueError(
            "revision_lookback_days cannot be negative."
        )

    # Observations can be older than the last-modified window. This allows
    # USGS revisions to older values to be detected and stored in CWMS.
    observation_start_dt = execution_date - timedelta(
        days=revision_lookback_days
    )

    # Preserve the existing two-hour future buffer.
    observation_end_dt = execution_date + timedelta(hours=2)

    logging.info(
        "Retrieving USGS observations with observation time between %s and %s "
        "that were modified between %s and %s.",
        observation_start_dt.isoformat(),
        observation_end_dt.isoformat(),
        modified_start_dt.isoformat(),
        modified_end_dt.isoformat(),
    )

    # This assignment must occur before CWMS_writeData().
    usgs_data = getUSGS_ts(
        usgs_ts=usgs_ts,
        observation_start_dt=observation_start_dt,
        observation_end_dt=observation_end_dt,
        modified_start_dt=modified_start_dt,
        modified_end_dt=modified_end_dt,
    )

    CWMS_writeData(
        usgs_ts=usgs_ts,
        usgs_data=usgs_data,
        days_back=days_back,
        backfill_version=backfill_version,
    )


def get_USGS_params():
    # defines USGS standard parameters.
    columns = [
        "USGS_PARAMETER",
        "USGS_Alias",
        "CWMS_PARAMETER",
        "CWMS_FACTOR",
        "CWMS_UNIT",
        "CWMS_TYPE",
    ]
    data = [
        ["00010", "Water Temp", "Temp-Water", 1, "C", "Inst"],
        ["00021", "Air Temp", "Temp-Air", 1, "F", "Inst"],
        ["00035", "Wind Speed", "Speed-Wind", 1, "mph", "Inst"],
        ["00036", "Wind Dir", "Dir-Wind", 1, "deg", "Inst"],
        ["00045", "Precip", "Precip-Inc", 1, "in", "Total"],
        ["00045", "Precip", "Precip", 1, "in", "Total"],
        ["00052", "RelHumidity", "%-Humidity", 1, "%", "Inst"],
        ["00060", "Flow", "Flow", 1, "cfs", "Inst"],
        # ['00061','Flow',1,'cfs','Inst'],
        ["00065", "Stage", "Stage", 1, "ft", "Inst"],
        ["00095", "Sp Cond", "Cond", 1, "umho/cm", "Inst"],
        ["00096", "Salinity", "Conc-Salinity", 0.001, "mg/l", "Inst"],
        # ['00062','Elevation','Elev',1,'ft','Inst'],
        ["72036", "Res Storage", "Stor", 1000, "ac-ft", "Inst"],
        ["62608", "Sol Rad", "Irrad-Solar", 1, "W/m2", "Inst"],
        # ['62614','Elev-Lake','Elev',1,'ft','Inst'],
        ["63160", "Elev-NAVD88", "Elev", 1, "ft", "Inst"],
    ]
    USGS_Params = pd.DataFrame(data, columns=columns).set_index("CWMS_PARAMETER")
    return USGS_Params


_USGS_PARAMS = get_USGS_params()


def get_CMWS_TS_Loc_Data(office):
    """
    get time series group and location alias information and combine into singe dataframe

    """

    def find_usgsparam(attribute, param):
        if attribute > 0:
            usgs_param = str(attribute).split(".")[0]
        elif param in _USGS_PARAMS.index:
            usgs_param = _USGS_PARAMS.at[param, "USGS_PARAMETER"]
        else:
            usgs_param = "Not Found"
        return usgs_param

    df = _require_group_dataframe(
        cwms.get_timeseries_group(
            group_id="USGS TS Data Acquisition",
            category_id="Data Acquisition",
            office_id=office,
            category_office_id="CWMS",
            group_office_id="CWMS",
        ),
        resource_name="USGS TS Data Acquisition group",
        office=office,
    )
    if df is None or df.empty:
        _log_error_and_exit(
            f"No time series are defined in Data Acquisition / USGS TS Data Acquisition for office {office}.",
            "Add one or more time series to that group, then rerun the command.",
        )
    if "timeseries-id" not in df.columns:
        _log_error_and_exit(
            "The USGS TS Data Acquisition group response did not include a 'timeseries-id' column."
        )
    df[["location-id", "param", "type", "int", "dur", "ver"]] = df[
        "timeseries-id"
    ].str.split(".", expand=True)

    df = df[df["office-id"] == office]
    if df.empty:
        _log_error_and_exit(
            f"No time series are defined in Data Acquisition / USGS TS Data Acquisition for office {office}.",
            "Add one or more office-specific time series to that group, then rerun the command.",
        )
    df["base-loc"] = df["location-id"].str.split("-", expand=True)[0]
    if "alias-id" not in df.columns:
        df["alias-id"] = np.nan
    if "attribute" not in df.columns:
        df["attribute"] = np.nan
    # New API behavior:
    #
    #   null alias-id  -> retrieve by station number + parameter code
    #   UUID alias-id  -> retrieve by USGS time_series_id
    #
    # Normalize blank aliases to null before renaming.
    df["alias-id"] = (
        df["alias-id"]
        .astype("string")
        .str.strip()
        .replace("", pd.NA)
    )

    df = df.rename(
        columns={
            "alias-id": "USGS_Time_Series_ID",
        }
    )

    # error in CDA with category_office_id and group_office_id. need to fix once CDA is updated
    Locdf = _require_group_dataframe(
        cwms.get_location_group(
            loc_group_id="USGS Station Number",
            category_id="Agency Aliases",
            office_id="CWMS",
        ),
        resource_name="USGS Station Number alias group",
        office=office,
    ).set_index("location-id")

    Locdf = Locdf[Locdf["office-id"] == office]
    if Locdf.empty:
        _log_error_and_exit(
            f"No USGS location aliases are defined in Agency Aliases / USGS Station Number for office {office}.",
            "Add one or more location aliases to that group, then rerun the command.",
        )
    if "attribute" not in Locdf.columns:
        Locdf["attribute"] = np.nan
    # Grab all of the locations that have a USGS station number assigned to them
    USGS_alias = Locdf[Locdf["alias-id"].notnull()]
    if USGS_alias.empty:
        _log_error_and_exit(
            f"No USGS location aliases are defined in Agency Aliases / USGS Station Number for office {office}.",
            "Add one or more alias-id values for that office, then rerun the command.",
        )
    # rename the columns
    USGS_alias = USGS_alias.rename(
        columns={"alias-id": "USGS_St_Num", "attribute": "Loc_attribute"}
    )
    # pad the USGS id with 0s if they are not 8 digits long
    USGS_alias.USGS_St_Num = USGS_alias.USGS_St_Num.str.rjust(8, "0")

    # do an inner join with the time series that are in the USGS time series group and the location group.  Join based on the Location ID and office if
    USGS_ts = pd.merge(df, USGS_alias, how="left", on=["location-id", "office-id"])
    # grab time series with missing USGS_St_Num and check to see if the base location has an assigned USGS station.
    if USGS_ts.USGS_St_Num.isnull().any():
        USGS_ts_base = pd.merge(
            USGS_ts[USGS_ts.USGS_St_Num.isnull()].drop(
                ["USGS_St_Num", "Loc_attribute"], axis=1
            ),
            USGS_alias,
            left_on=["base-loc", "office-id"],
            right_on=["location-id", "office-id"],
        )
        # merge with existing dataframe
        USGS_ts = pd.concat(
            [USGS_ts[USGS_ts["USGS_St_Num"].notnull()], USGS_ts_base], axis=0
        )

    # this code fills in the USGS_Params field with values in the Time Series Group Attribute if it exists.  If it does not exist it
    # grabs the default USGS paramter for the coresponding CWMS parameter
    USGS_ts.attribute = USGS_ts.apply(
        lambda x: find_usgsparam(x.attribute, x.param), axis=1
    ).astype("string")
    USGS_ts.attribute = USGS_ts.attribute.str.rjust(5, "0")
    # renames the attribute column to USGS_PARAMETER
    USGS_ts = USGS_ts.rename(columns={"attribute": "USGS_PARAMETER"})

    logging.info("CWMS TS Groups and Location Data Obtained")
    return USGS_ts

USGS_CONTINUOUS_PROPERTIES = [
    "time_series_id",
    "monitoring_location_id",
    "parameter_code",
    "statistic_id",
    "time",
    "value",
    "unit_of_measure",
    "approval_status",
    "qualifier",
    "last_modified",
]


def _chunks(values: list, chunk_size: int):
    """Yield values in manageable API-request chunks."""

    for index in range(0, len(values), chunk_size):
        yield values[index : index + chunk_size]


def _normalize_usgs_unit(unit: str | None) -> str | None:
    """
    Normalize common USGS unit labels for CWMS storage.

    CWMS unit conversion is still performed by the CDA/cwms-python stack.
    """

    if unit is None or pd.isna(unit):
        return None

    unit = str(unit).strip()

    return (
        unit.replace("ft^3/s", "ft3/s")
        .replace("ft³/s", "ft3/s")
    )


def _get_continuous_data(**kwargs) -> pd.DataFrame:
    """
    Retrieve continuous data from the USGS Water Data API and validate the
    minimum response columns required by CWMS ingestion.
    """

    data, _ = waterdata.get_continuous(
        properties=USGS_CONTINUOUS_PROPERTIES,
        **kwargs,
    )

    if data is None or data.empty:
        return pd.DataFrame(columns=USGS_CONTINUOUS_PROPERTIES)

    required_columns = {
        "time_series_id",
        "monitoring_location_id",
        "parameter_code",
        "time",
        "value",
        "unit_of_measure",
    }

    missing_columns = required_columns.difference(data.columns)

    if missing_columns:
        raise RuntimeError(
            "USGS continuous response is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    data = data.copy()

    data["time"] = pd.to_datetime(
        data["time"],
        utc=True,
        errors="coerce",
    )

    data["value"] = pd.to_numeric(
        data["value"],
        errors="coerce",
    )

    data = data.dropna(
        subset=[
            "time_series_id",
            "time",
            "value",
        ]
    )

    return data.reset_index(drop=True)


def getUSGS_ts(
    usgs_ts: pd.DataFrame,
    observation_start_dt: datetime,
    observation_end_dt: datetime,
    modified_start_dt: datetime,
    modified_end_dt: datetime,
) -> pd.DataFrame:
    """
    Retrieve all required continuous USGS values using the new Water Data API.

    Requests are grouped as follows:

        alias-id is null:
            Query monitoring_location_id + parameter_code.

        alias-id contains USGS UUID:
            Query time_series_id directly.

    The returned DataFrame remains long-format and is filtered per CWMS TSID
    later in CWMS_writeData().
    """

    if usgs_ts.empty:
        return pd.DataFrame(columns=USGS_CONTINUOUS_PROPERTIES)

    observation_time_window = [
        pd.Timestamp(observation_start_dt).isoformat(),
        pd.Timestamp(observation_end_dt).isoformat(),
    ]

    last_modified_window = (
        f"{pd.Timestamp(modified_start_dt).isoformat()}/"
        f"{pd.Timestamp(modified_end_dt).isoformat()}"
    )

    frames = []

    # ------------------------------------------------------------------
    # Records without alias-id: station number + parameter code query.
    # ------------------------------------------------------------------
    unaliased_ts = usgs_ts.loc[
        usgs_ts["USGS_Time_Series_ID"].isna()
    ].copy()

    if not unaliased_ts.empty:
        unaliased_ts["monitoring_location_id"] = (
            "USGS-" + unaliased_ts["USGS_St_Num"].astype(str)
        )

        for parameter_code, parameter_group in unaliased_ts.groupby(
            "USGS_PARAMETER"
        ):
            monitoring_locations = sorted(
                parameter_group["monitoring_location_id"]
                .dropna()
                .unique()
                .tolist()
            )

            for location_chunk in _chunks(monitoring_locations, 100):
                logging.info(
                    "Requesting unaliased USGS continuous data for parameter "
                    "%s at %s monitoring location(s).",
                    parameter_code,
                    len(location_chunk),
                )

                try:
                    frame = _get_continuous_data(
                        monitoring_location_id=location_chunk,
                        parameter_code=parameter_code,
                        time=observation_time_window,
                        last_modified=last_modified_window,
                    )

                    if not frame.empty:
                        frames.append(frame)

                except Exception as error:
                    if is_fatal_service_error(error):
                        raise

                    logging.error(
                        "Failed retrieving unaliased USGS continuous data for "
                        "parameter %s at locations %s: %s",
                        parameter_code,
                        location_chunk,
                        error,
                    )

    # ------------------------------------------------------------------
    # Records with UUID alias-id: explicit time_series_id query.
    # ------------------------------------------------------------------
    aliased_ts = usgs_ts.loc[
        usgs_ts["USGS_Time_Series_ID"].notna()
    ].copy()

    if not aliased_ts.empty:
        time_series_ids = sorted(
            aliased_ts["USGS_Time_Series_ID"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        for tsid_chunk in _chunks(time_series_ids, 100):
            logging.info(
                "Requesting USGS continuous data for %s explicit "
                "time_series_id value(s).",
                len(tsid_chunk),
            )

            try:
                frame = _get_continuous_data(
                    time_series_id=tsid_chunk,
                    time=observation_time_window,
                    last_modified=last_modified_window,
                )

                if not frame.empty:
                    frames.append(frame)

            except Exception as error:
                if is_fatal_service_error(error):
                    raise

                logging.error(
                    "Failed retrieving USGS continuous data for "
                    "time_series_id values %s: %s",
                    tsid_chunk,
                    error,
                )

    if not frames:
        logging.warning("No USGS continuous values were returned.")
        return pd.DataFrame(columns=USGS_CONTINUOUS_PROPERTIES)

    usgs_data = pd.concat(
        frames,
        ignore_index=True,
    )

    usgs_data = usgs_data.drop_duplicates(
        subset=[
            "time_series_id",
            "time",
        ]
    )

    logging.info(
        "Retrieved %s USGS continuous observation(s).",
        len(usgs_data),
    )

    return usgs_data.reset_index(drop=True)


def _replace_ts_version(ts_id: str, backfill_version: str) -> str:
    """Replace the version component of a timeseries ID.

    The last dot-separated component is the version (e.g., Raw-USGS, Rev-USGS).
    This function replaces it with the provided backfill_version.
    """
    parts = ts_id.rsplit(".", 1)
    if len(parts) == 2:
        return f"{parts[0]}.{backfill_version}"
    return ts_id


def _validate_backfill_version_timeseries(
    usgs_ts: pd.DataFrame, backfill_version: str, office_id: str
) -> pd.DataFrame:
    """Validate that all timeseries with backfill_version exist in CWMS.

    Returns dataframe with missing backfill_version timeseries removed.
    """
    if backfill_version is None:
        return usgs_ts

    try:
        pattern = f".*\\.{backfill_version}$"
        response = cwms.get_timeseries_identifiers(
            office_id=office_id, timeseries_id_regex=pattern
        )

        existing_ts = set()
        if response.df is not None and not response.df.empty:
            existing_ts = set(response.df["timeseries-id"].values)

        missing_ts = []
        missing_original_ts = []
        for ts_id in usgs_ts["timeseries-id"].unique():
            new_ts_id = _replace_ts_version(ts_id, backfill_version)
            if new_ts_id not in existing_ts:
                missing_ts.append(new_ts_id)
                missing_original_ts.append(ts_id)

        if missing_ts:
            logging.warning(
                f"The following timeseries with backfill_version '{backfill_version}' do not exist in CWMS and will be skipped: {missing_ts}"
            )
            usgs_ts = usgs_ts[~usgs_ts["timeseries-id"].isin(missing_original_ts)]

    except Exception as e:
        logging.warning(
            f"Could not verify timeseries with backfill_version for office {office_id}: {e}"
        )

    return usgs_ts

def CWMS_writeData(
    usgs_ts: pd.DataFrame,
    usgs_data: pd.DataFrame,
    days_back: float,
    backfill_version: str = None,
):
    """
    Filter new-USGS long-format observations for each configured CWMS TSID,
    resample as necessary, and store values through CDA.
    """

    no_data = []
    not_in_api = []
    storage_errors = []
    multiple_series = []

    total_recs = len(usgs_ts.index)
    saved = 0

    if usgs_data is None or usgs_data.empty:
        logging.warning("USGS returned no continuous observations.")

    for _, row in usgs_ts.iterrows():
        ts_id = row["timeseries-id"]
        office_id = row["office-id"]

        station_number = str(row["USGS_St_Num"]).zfill(8)
        parameter_code = str(row["USGS_PARAMETER"]).zfill(5)

        monitoring_location_id = f"USGS-{station_number}"

        configured_usgs_tsid = row.get("USGS_Time_Series_ID")

        logging.info(
            "Attempting USGS write for CWMS TSID %s using station %s, "
            "parameter %s, alias %s.",
            ts_id,
            station_number,
            parameter_code,
            configured_usgs_tsid,
        )

        if usgs_data is None or usgs_data.empty:
            not_in_api.append(
                [
                    ts_id,
                    monitoring_location_id,
                    parameter_code,
                    configured_usgs_tsid,
                ]
            )
            continue

        # --------------------------------------------------------------
        # Explicit UUID alias-id: select that one new USGS time series.
        # --------------------------------------------------------------
        if pd.notna(configured_usgs_tsid):
            values = usgs_data.loc[
                usgs_data["time_series_id"].astype(str).eq(
                    str(configured_usgs_tsid)
                )
            ].copy()

        # --------------------------------------------------------------
        # Null alias-id: station + parameter must produce one series.
        # --------------------------------------------------------------
        else:
            values = usgs_data.loc[
                usgs_data["monitoring_location_id"].eq(
                    monitoring_location_id
                )
                & usgs_data["parameter_code"].astype(str).eq(
                    parameter_code
                )
            ].copy()

            returned_ids = sorted(
                values["time_series_id"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )

            if len(returned_ids) > 1:
                multiple_series.append(
                    [
                        ts_id,
                        monitoring_location_id,
                        parameter_code,
                        returned_ids,
                    ]
                )

                logging.error(
                    "FAIL: Null alias-id for CWMS TSID %s returned multiple "
                    "USGS time_series_id values for %s / %s: %s. "
                    "A UUID alias-id is required.",
                    ts_id,
                    monitoring_location_id,
                    parameter_code,
                    returned_ids,
                )
                continue

        if values.empty:
            not_in_api.append(
                [
                    ts_id,
                    monitoring_location_id,
                    parameter_code,
                    configured_usgs_tsid,
                ]
            )

            logging.warning(
                "FAIL: No USGS values returned for CWMS TSID %s.",
                ts_id,
            )
            continue

        values = values.dropna(
            subset=[
                "time",
                "value",
            ]
        ).copy()

        if values.empty:
            no_data.append(
                [
                    ts_id,
                    monitoring_location_id,
                    parameter_code,
                    configured_usgs_tsid,
                ]
            )
            continue

        units = (
            values["unit_of_measure"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        if len(units) != 1:
            storage_errors.append(
                [
                    ts_id,
                    monitoring_location_id,
                    parameter_code,
                    (
                        "Expected one USGS unit_of_measure; received "
                        f"{units}"
                    ),
                ]
            )

            logging.error(
                "FAIL: Multiple or missing units returned for CWMS TSID %s: %s",
                ts_id,
                units,
            )
            continue

        cwms_unit = _normalize_usgs_unit(units[0])

        values = values[
            [
                "time",
                "value",
            ]
        ].copy()

        values = values.rename(
            columns={
                "time": "date-time",
            }
        )

        values["quality-code"] = 0

        values = resample_to_tsid_interval(
            values=values,
            ts_id=ts_id,
        )

        values = values.dropna(subset=["value"]).copy()

        if values.empty:
            no_data.append(
                [
                    ts_id,
                    monitoring_location_id,
                    parameter_code,
                    configured_usgs_tsid,
                ]
            )
            continue

        try:
            values["quality-code"] = (
                values["quality-code"]
                .fillna(0)
                .astype(int)
            )
        except Exception:
            values["quality-code"] = values["quality-code"].fillna(0)

        store_ts_id = (
            _replace_ts_version(ts_id, backfill_version)
            if backfill_version
            else ts_id
        )

        try:
            data = cwms.timeseries_df_to_json(
                data=values,
                ts_id=store_ts_id,
                units=cwms_unit,
                office_id=office_id,
            )

            if days_back < 365:
                cwms.store_timeseries(data)
            else:
                cwms.store_timeseries(
                    data,
                    max_workers=30,
                    chunk_size=30 * 24 * 4,
                )

            logging.info(
                "SUCCESS: Stored %s USGS observation(s) in CWMS TSID %s.",
                len(values),
                store_ts_id,
            )

            saved += 1

        except Exception as error:
            if is_fatal_service_error(error):
                raise

            storage_errors.append(
                [
                    ts_id,
                    monitoring_location_id,
                    parameter_code,
                    str(error),
                ]
            )

            logging.error(
                "FAIL: Could not store USGS values for CWMS TSID %s: %s",
                store_ts_id,
                error,
            )

    logging.info(
        "USGS acquisition completed: %s of %s CWMS time series stored.",
        saved,
        total_recs,
    )

    logging.info(
        "No-data records: %s",
        no_data,
    )

    logging.info(
        "No-USGS-data records: %s",
        not_in_api,
    )

    logging.info(
        "Multiple-series records: %s",
        multiple_series,
    )

    logging.info(
        "CWMS storage-error records: %s",
        storage_errors,
    )

def resample_to_tsid_interval(values: pd.DataFrame, ts_id: str) -> pd.DataFrame:
    """Resample the incoming values DataFrame to the interval encoded in ``ts_id``.

    The DataFrame is expected to have columns ``date-time`` and ``value``. The
    function returns a new DataFrame with the same columns. If the TSID encodes
    an irregular interval (contains '~' or '0') the original DataFrame is
    returned unchanged. Otherwise the function infers the incoming data
    frequency and resamples only when it differs from the TSID interval.
    """
    if values is None or values.empty:
        return values

    try:
        interval_segment = ts_id.split(".")[3]
    except Exception:
        return values

    if "~" in interval_segment or interval_segment == "0":
        return values

    m = re.match(r"^(\d+)(.*)", interval_segment)
    if m:
        interval_number = int(m.group(1))
        interval_type = m.group(2)
    else:
        return values

    if interval_type == "Minutes":
        target_str = f"{interval_number}min"
    else:
        # use lower-case single-letter codes (pandas prefers lower-case symbols)
        target_str = f"{interval_number}{interval_type[0].lower()}"

    df = values.copy()
    # Coerce date-time to datetimes; drop rows without a valid timestamp because
    # they cannot be resampled. Sort and deduplicate the index to ensure
    # deterministic resampling behavior.
    df["date-time"] = pd.to_datetime(df["date-time"], errors="coerce")
    df = df.dropna(subset=["date-time"]).copy()
    if df.empty:
        return df
    df = df.set_index("date-time")
    df = df.sort_index()
    # If duplicate timestamps exist, keep the first occurrence (matching prior
    # behavior of using .first() during resample).
    df = df[~df.index.duplicated(keep="first")]

    current_delta = None
    try:
        inferred = pd.infer_freq(df.index)
        if inferred:
            current_delta = pd.to_timedelta(inferred)
    except Exception:
        current_delta = None

    if current_delta is None:
        diffs = df.index.to_series().diff().dropna()
        if not diffs.empty:
            current_delta = diffs.median()

    try:
        target_delta = pd.to_timedelta(target_str)
    except Exception:
        target_delta = None

    if target_delta is not None and (
        current_delta is None or current_delta != target_delta
    ):
        logging.info(
            f"Resampling {ts_id}: from {current_delta} to {target_delta} (target={target_str})"
        )
        df_resampled = df.resample(target_str).first()
        return df_resampled.reset_index()

    return df.reset_index()
