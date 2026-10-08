import logging
import sys
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from json import loads
from typing import Any, Iterator

import cwms
import numpy as np
import pandas as pd
from dataretrieval import configure, waterdata
from dataretrieval.configuration import Configuration

from cwmscli.utils import init_cwms_session
from cwmscli.utils.friendly_errors import is_fatal_service_error

RATING_TYPES = ("EXSA", "CORR", "BASE")
RATING_UNITS = {
    "EXSA": "ft;cfs",
    "BASE": "ft;cfs",
    "CORR": "ft;ft",
}


def getusgs_rating_cda(
    api_root: str,
    office_id: str,
    api_key: str,
    days_back: float = 1,
    rating_subset: list | None = None,
    usgs_api_key: str | None = None,
    dry_run: bool = False,
) -> None:
    """
    Retrieve updated USGS ratings and store them in CWMS.

    Existing CWMS ratings are selected only when their corresponding USGS STAC
    asset was updated in the requested lookback period.

    New CWMS rating specifications are included in the lookback scan and are
    retrieved only when their USGS rating asset was updated in that period.
    A rating subset explicitly retrieves the current rating regardless of the
    lookback period.

    Parameters
    ----------
    api_root
        CWMS Data API root URL.
    office_id
        CWMS office identifier.
    api_key
        CWMS Data API key.
    days_back
        Number of days to look back for USGS rating asset updates.
    rating_subset
        Optional list of CWMS rating specification IDs. When supplied, the
        current USGS rating is retrieved for each selected rating spec,
        regardless of STAC update time.
    usgs_api_key
        Optional USGS Water Data API key. If omitted, dataretrieval will use
        API_USGS_PAT from the environment if it is set.
    dry_run
        Retrieve and validate ratings without storing them in CWMS.
    """
    if dry_run:
        logging.info("DRY RUN MODE - no ratings will be stored in CWMS")

    init_cwms_session(cwms, api_root=api_root, api_key="apikey " + api_key)

    logging.info("CDA connection: %s", api_root)
    logging.info(
        "Updated ratings will be obtained from USGS for the past %s day(s).",
        days_back,
    )
    logging.info("Execution date: %s", datetime.now())

    logging.info("Getting rating specification information from CWMS database.")
    rating_specs = get_rating_ids_from_specs(office_id)

    usgs_ratings = get_location_aliases(
        rating_specs,
        loc_group_id="USGS Station Number",
        category_id="Agency Aliases",
        office_id="CWMS",
        category_office_id=None,
        group_office_id=None,
    )

    if usgs_ratings.empty:
        logging.warning("No qualifying CWMS USGS rating specifications were found.")
        return

    usgs_context = (
        configure(Configuration(api_key=usgs_api_key))
        if usgs_api_key
        else nullcontext()
    )

    progress_enabled = logging.getLogger().isEnabledFor(logging.DEBUG)

    with usgs_context, configure(Configuration(progress=progress_enabled)):
        if rating_subset is None:
            logging.info(
                "Getting USGS ratings updated in the past %s day(s).",
                days_back,
            )

            recently_updated = get_usgs_updated_ratings(
                ratings=usgs_ratings,
                days_back=days_back,
            )

            updated_ratings = usgs_ratings.merge(
                recently_updated,
                how="inner",
                on=["USGS_St_Num", "rating-type"],
            )
        else:
            logging.info(
                "A rating subset was specified. Retrieving the current USGS "
                "rating for each selected specification."
            )
            updated_ratings = usgs_ratings.copy()

        if rating_subset is not None:
            updated_ratings = updated_ratings[
                updated_ratings["rating-id"].isin(rating_subset)
            ].copy()

        updated_existing = updated_ratings[
            updated_ratings["effective-dates"].notna()
        ].copy()
        updated_empty = updated_ratings[
            updated_ratings["effective-dates"].isna()
        ].copy()

        if not updated_existing.empty:
            updated_existing.loc[:, "effective-dates"] = updated_existing[
                "effective-dates"
            ].apply(parse_effective_dates)

            updated_existing.loc[:, "cwms_max_effective_date"] = updated_existing[
                "effective-dates"
            ].apply(max)
        else:
            updated_existing["cwms_max_effective_date"] = pd.Series(
                dtype="datetime64[ns, UTC]"
            )

        updated_ratings = pd.concat(
            [updated_existing, updated_empty],
            ignore_index=True,
            sort=False,
        )

        if updated_ratings.empty:
            logging.info("No USGS rating updates require processing.")
            return

        cwms_write_ratings(updated_ratings, dry_run=dry_run)


def get_rating_ids_from_specs(office_id: str) -> pd.DataFrame:
    """
    Get active CWMS rating specifications configured for USGS updates.
    """
    rating_specs = cwms.get_rating_specs(office_id=office_id).df

    if rating_specs.empty:
        logging.warning("No rating specifications found for office %s.", office_id)
        sys.exit()

    if "effective-dates" not in rating_specs.columns:
        rating_specs["effective-dates"] = np.nan

    rating_specs = rating_specs.dropna(subset=["description"]).copy()

    for rating_type in RATING_TYPES:
        rating_specs.loc[
            rating_specs["description"].str.contains(
                f"USGS-{rating_type}",
                case=False,
                na=False,
            ),
            "rating-type",
        ] = rating_type

    rating_specs = rating_specs[
        rating_specs["rating-type"].isin(RATING_TYPES)
        & rating_specs["active"]
        & rating_specs["auto-update"]
    ].copy()

    return rating_specs


def get_location_aliases(
    df: pd.DataFrame,
    loc_group_id: str,
    category_id: str,
    office_id: str,
    category_office_id: str | None,
    group_office_id: str | None,
) -> pd.DataFrame:
    """
    Join CWMS rating specifications to their USGS Station Number aliases.
    """
    location_df = cwms.get_location_group(
        loc_group_id=loc_group_id,
        category_id=category_id,
        office_id=office_id,
        category_office_id=category_office_id,
        group_office_id=group_office_id,
    ).df

    usgs_aliases = location_df[location_df["alias-id"].notna()].copy()

    usgs_aliases = usgs_aliases.rename(
        columns={
            "alias-id": "USGS_St_Num",
            "attribute": "Loc_attribute",
        }
    )

    usgs_aliases["USGS_St_Num"] = (
        usgs_aliases["USGS_St_Num"]
        .astype(str)
        .str.strip()
        .str.replace("USGS-", "", regex=False)
        .str.zfill(8)
    )

    return pd.merge(
        df,
        usgs_aliases,
        how="inner",
        on=["location-id", "office-id"],
    )


def chunked(values: list[str], chunk_size: int) -> Iterator[list[str]]:
    """
    Yield fixed-size list chunks.
    """
    for index in range(0, len(values), chunk_size):
        yield values[index : index + chunk_size]


def get_usgs_updated_ratings(
    ratings: pd.DataFrame,
    days_back: float,
    chunk_size: int = 25,
) -> pd.DataFrame:
    """
    Return USGS rating assets updated during the requested lookback interval.

    The STAC feature property `datetime` is the catalog publication/update
    timestamp used for the update scan. This is distinct from the rating's
    CWMS effective date, which is determined later from the RDB header.

    The search is constrained to station/type combinations configured in CWMS.
    Small batches are used because very large CQL GET query strings can receive
    a gateway HTML 403 response before reaching the USGS application.
    """
    output_columns = [
        "USGS_St_Num",
        "rating-type",
        "date_updated",
        "url",
    ]

    if ratings.empty:
        return pd.DataFrame(columns=output_columns)

    start = datetime.now(timezone.utc) - timedelta(days=days_back)
    time_filter = [
        start.isoformat().replace("+00:00", "Z"),
        None,
    ]

    records: list[dict[str, Any]] = []

    # Query each rating type separately. This permits server-side file_type
    # filtering and prevents a returned BASE or CORR feature from matching an
    # EXSA-only CWMS rating specification.
    for rating_type in RATING_TYPES:
        type_ratings = ratings[ratings["rating-type"] == rating_type]

        site_numbers = (
            type_ratings["USGS_St_Num"]
            .dropna()
            .astype(str)
            .str.zfill(8)
            .drop_duplicates()
            .tolist()
        )

        for site_batch in chunked(site_numbers, chunk_size):
            monitoring_location_ids = [
                f"USGS-{site_number}" for site_number in site_batch
            ]

            features = waterdata.get_ratings(
                monitoring_location_id=monitoring_location_ids,
                file_type=rating_type.lower(),
                time=time_filter,
                limit=100,
                download_and_parse=False,
            )

            for feature in features:
                properties = feature.get("properties", {})
                monitoring_location_id = properties.get(
                    "monitoring_location_id",
                    "",
                )
                feature_type = str(properties.get("file_type", "")).upper()

                if not monitoring_location_id or feature_type not in RATING_TYPES:
                    continue

                asset = feature.get("assets", {}).get("data", {})

                records.append(
                    {
                        "USGS_St_Num": monitoring_location_id.removeprefix("USGS-"),
                        "rating-type": feature_type,
                        "date_updated": pd.to_datetime(
                            properties.get("datetime"),
                            utc=True,
                        ),
                        "url": asset.get("href"),
                    }
                )

    return pd.DataFrame.from_records(records, columns=output_columns)


def parse_effective_dates(value: Any) -> list[pd.Timestamp]:
    """
    Convert CWMS effective-date values to timezone-aware pandas timestamps.
    """
    if isinstance(value, str):
        try:
            value = loads(value)
        except ValueError:
            value = [value]

    if not isinstance(value, (list, tuple, pd.Series, np.ndarray)):
        value = [value]

    parsed_dates = [pd.to_datetime(date, utc=True) for date in value if pd.notna(date)]

    if not parsed_dates:
        raise ValueError("CWMS rating specification contained no valid effective date.")

    return parsed_dates


def convert_tz(tz: str) -> str:
    """
    Convert USGS abbreviated time zones to IANA time-zone IDs.
    """
    tz_map = {
        "AST": "America/Halifax",
        "ADT": "America/Halifax",
        "EST": "US/Eastern",
        "EDT": "US/Eastern",
        "CST": "US/Central",
        "CDT": "US/Central",
        "MST": "US/Mountain",
        "MDT": "US/Mountain",
        "PST": "US/Pacific",
        "PDT": "US/Pacific",
        "AKST": "America/Anchorage",
        "AKDT": "America/Anchorage",
        "UTC": "UTC",
        "GMT": "UTC",
    }

    return tz_map.get(tz, tz)


def rating_comment_lines(comment: str | list[str] | None) -> list[str]:
    """
    Split a waterdata rating DataFrame's RDB comment attribute into lines.
    """
    lines = comment.splitlines() if isinstance(comment, str) else comment or []
    return [line.strip() for line in lines if line.strip()]


def get_usgs_rating_description(
    comment: str | list[str] | None,
    rating_type: str,
    source_url: str,
) -> str:
    """Use USGS rating remarks as the description, with an asset URL fallback."""
    for line in rating_comment_lines(comment):
        if line.startswith("# //RATING REMARKS="):
            remarks = line.split("=", 1)[1].strip()
            if len(remarks) >= 2 and remarks[0] == remarks[-1] == '"':
                remarks = remarks[1:-1].strip()
            if remarks:
                return remarks

    return f"USGS {rating_type.upper()} rating downloaded from {source_url}"


def get_usgs_tz(comment: str | list[str] | None) -> str:
    """
    Extract the station time zone from a USGS rating RDB header.
    """
    for line in rating_comment_lines(comment):
        if line.startswith("# //STATION AGENCY=") and "TIME_ZONE=" in line:
            tz = line.split("TIME_ZONE=", 1)[1].split()[0].replace('"', "")
            return convert_tz(tz)

    raise ValueError("USGS rating header did not contain TIME_ZONE metadata.")


def get_begin_with_date(
    comment: str | list[str] | None,
    starts_with: tuple[str, ...],
) -> str | None:
    """
    Return the last numeric BEGIN timestamp found for matching RDB header lines.
    """
    date_string = None

    for line in rating_comment_lines(comment):
        if line.startswith(starts_with) and "BEGIN=" in line:
            value = line.split("BEGIN=", 1)[1].split()[0].strip().replace('"', "")

            if value.isdigit():
                date_string = value

    return date_string


def parse_usgs_header_datetime(
    date_string: str,
    timezone_name: str,
) -> pd.Timestamp:
    """
    Parse an RDB header date using the source station's local time zone.
    """
    if date_string.isdigit() and len(date_string) == 14:
        timestamp = pd.to_datetime(
            date_string,
            format="%Y%m%d%H%M%S",
        )
    else:
        timestamp = pd.to_datetime(date_string)

    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(timezone_name)

    return timestamp.floor("min")


def get_usgs_effective_date(
    comment: str | list[str] | None,
    rating_type: str,
) -> pd.Timestamp:
    """
    Determine the CWMS effective date from the USGS rating RDB header.

    EXSA uses RATING SHIFTED.
    BASE uses the last numeric RATING_DATETIME BEGIN.
    CORR uses the last numeric CORR*_PREV BEGIN.
    All types fall back to the RDB RETRIEVED timestamp if needed.
    """
    rating_type = rating_type.upper()
    lines = rating_comment_lines(comment)
    date_string = None

    if rating_type == "EXSA":
        for line in lines:
            if line.startswith("# //RATING SHIFTED="):
                date_string = line.split("=", 1)[1].replace('"', "").split()[0]
                break

    elif rating_type == "BASE":
        date_string = get_begin_with_date(
            comment,
            ("# //RATING_DATETIME BEGIN=",),
        )

    elif rating_type == "CORR":
        date_string = get_begin_with_date(
            comment,
            (
                "# //CORR1_PREV BEGIN=",
                "# //CORR2_PREV BEGIN=",
                "# //CORR3_PREV BEGIN=",
            ),
        )

    else:
        raise ValueError(f"Unsupported USGS rating type: {rating_type}")

    if date_string is None:
        for line in lines:
            if line.startswith("# //RETRIEVED:"):
                date_string = line.split("RETRIEVED:", 1)[1].strip()
                break

    if date_string is None:
        raise ValueError(
            f"Unable to determine an effective date for {rating_type} rating."
        )

    return parse_usgs_header_datetime(
        date_string,
        get_usgs_tz(comment),
    )


def convert_usgs_rating_df(
    df: pd.DataFrame,
    rating_type: str,
) -> pd.DataFrame:
    """
    Convert a USGS rating DataFrame to CWMS simple-rating point columns.

    CWMS expects `ind` and `dep`.

    EXSA and BASE use INDEP -> DEP.
    CORR uses INDEP -> CORRINDEP. Duplicate correction values are reduced to
    the first and last row, preserving the original script's behavior.
    """
    rating_type = rating_type.upper()
    rating_df = df.copy()

    if rating_type == "CORR":
        rating_df = rating_df.groupby("CORR", dropna=False)
        rating_df = pd.concat(
            [rating_df.first(), rating_df.last()],
            ignore_index=True,
            join="inner",
        )
        rating_df = rating_df.sort_values(
            by=["INDEP"],
            ignore_index=True,
        )

        rating_df = rating_df.rename(
            columns={
                "INDEP": "ind",
                "CORRINDEP": "dep",
            }
        )
    else:
        rating_df = rating_df.rename(
            columns={
                "INDEP": "ind",
                "DEP": "dep",
            }
        )

    if not {"ind", "dep"}.issubset(rating_df.columns):
        raise ValueError(
            f"USGS {rating_type} rating did not contain the required "
            f"columns. Available columns: {rating_df.columns.tolist()}"
        )

    return rating_df[["ind", "dep"]].copy()


def get_current_usgs_rating(
    usgs_station_number: str,
    rating_type: str,
) -> pd.DataFrame | None:
    """
    Download the current published USGS rating asset.

    No `time` parameter is used here intentionally. This supports newly
    created CWMS rating specs, which need the current rating even when the
    rating has not been modified recently.
    """
    station_number = str(usgs_station_number).strip().replace("USGS-", "").zfill(8)
    monitoring_location_id = f"USGS-{station_number}"
    file_type = rating_type.lower()
    rating_file_id = f"{monitoring_location_id}.{file_type}.rdb"

    ratings = waterdata.get_ratings(
        monitoring_location_id=monitoring_location_id,
        file_type=file_type,
    )

    return ratings.get(rating_file_id)


def migrate_extension(
    rating_id: str,
    office_id: str,
    cwms_effective_date: pd.Timestamp,
    cwms_rating: pd.DataFrame,
    usgs_effective_date: pd.Timestamp,
    active: bool,
    description: str,
) -> dict[str, Any]:
    """Fetch and update a prior rating while retaining its extension data."""
    current_rating = cwms.get_ratings(
        rating_id=rating_id,
        office_id=office_id,
        begin=cwms_effective_date,
        end=cwms_effective_date,
        method="EAGER",
        single_rating_df=True,
    )
    rating_json = current_rating.json
    simple_rating = rating_json["simple-rating"]
    points_json = loads(cwms_rating.to_json(orient="records"))
    simple_rating["rating-points"] = {"point": points_json}
    simple_rating["effective-date"] = usgs_effective_date.isoformat()
    simple_rating.pop("create-date", None)
    simple_rating["active"] = active
    simple_rating["description"] = description
    return rating_json


def cwms_write_ratings(
    updated_ratings: pd.DataFrame,
    dry_run: bool = False,
) -> None:
    """
    Download selected USGS ratings and write new effective dates to CWMS.
    """
    storage_errors = []
    usgs_api_errors = []
    usgs_empty_errors = []
    usgs_effective_date_errors = []

    total_records = len(updated_ratings.index)
    saved = 0
    saved_ratings = []
    would_store = 0
    would_store_ratings = []
    same_effective = 0

    for _, row in updated_ratings.iterrows():
        rating_id = row["rating-id"]
        station_number = str(row["USGS_St_Num"]).zfill(8)
        rating_type = str(row["rating-type"]).upper()

        logging.info("Getting data for rating ID = %s", rating_id)
        logging.info(
            "Getting USGS %s rating for USGS station %s.",
            rating_type,
            station_number,
        )

        try:
            usgs_rating = get_current_usgs_rating(
                usgs_station_number=station_number,
                rating_type=rating_type,
            )
        except Exception as error:
            if is_fatal_service_error(error):
                raise

            usgs_api_errors.append([rating_id, station_number, rating_type, error])

            logging.error(
                "FAIL: Error collecting USGS rating for %s, station %s, "
                "type %s. USGS error: %s",
                rating_id,
                station_number,
                rating_type,
                error,
            )
            continue

        if usgs_rating is None or usgs_rating.empty:
            logging.warning(
                "No current USGS %s rating is available for station %s.",
                rating_type,
                station_number,
            )
            usgs_empty_errors.append([rating_id, station_number, rating_type])
            continue

        try:
            usgs_effective_date = get_usgs_effective_date(
                comment=usgs_rating.attrs.get("comment", ""),
                rating_type=rating_type,
            )
        except Exception as error:
            if is_fatal_service_error(error):
                raise

            usgs_effective_date_errors.append(
                [rating_id, station_number, rating_type, error]
            )

            logging.error(
                "FAIL: Error determining USGS effective date for %s, "
                "station %s, type %s. Error: %s",
                rating_id,
                station_number,
                rating_type,
                error,
            )
            continue

        cwms_effective_date = row.get("cwms_max_effective_date")
        is_new_cwms_spec = pd.isna(cwms_effective_date)

        if not is_new_cwms_spec:
            cwms_effective_date = pd.to_datetime(
                cwms_effective_date,
                utc=True,
            )

            usgs_effective_date_utc = usgs_effective_date.tz_convert("UTC")

            if usgs_effective_date_utc == cwms_effective_date:
                same_effective += 1

                logging.info(
                    "USGS effective date %s matches the latest CWMS "
                    "effective date for %s. No rating stored.",
                    usgs_effective_date,
                    rating_id,
                )
                continue

        try:
            cwms_rating = convert_usgs_rating_df(
                usgs_rating,
                rating_type,
            )
            source_url = usgs_rating.attrs.get("url", "")
            rating_description = get_usgs_rating_description(
                comment=usgs_rating.attrs.get("comment", ""),
                rating_type=rating_type,
                source_url=source_url,
            )
            if bool(row["auto-migrate-extension"]) and not is_new_cwms_spec:
                rating_json = migrate_extension(
                    rating_id=rating_id,
                    office_id=row["office-id"],
                    cwms_effective_date=cwms_effective_date,
                    cwms_rating=cwms_rating,
                    usgs_effective_date=usgs_effective_date,
                    active=bool(row["auto-activate"]),
                    description=rating_description,
                )
            else:

                rating_json = cwms.rating_simple_df_to_json(
                    data=cwms_rating,
                    rating_id=rating_id,
                    office_id=row["office-id"],
                    units=RATING_UNITS[rating_type],
                    effective_date=usgs_effective_date.to_pydatetime(),
                    description=rating_description,
                    active=bool(row["auto-activate"]),
                )

            rating_summary = [
                rating_id,
                station_number,
                rating_type,
                usgs_effective_date,
            ]

            if dry_run:
                would_store += 1
                would_store_ratings.append(rating_summary)
                logging.info(
                    "DRY RUN: Would store USGS %s rating for %s with "
                    "effective date %s.",
                    rating_type,
                    rating_id,
                    usgs_effective_date,
                )
            else:
                cwms.update_ratings(
                    data=rating_json,
                    rating_id=rating_id,
                )

                saved += 1
                saved_ratings.append(rating_summary)

                if is_new_cwms_spec:
                    logging.info(
                        "Stored current USGS %s rating for new CWMS rating "
                        "specification %s with effective date %s.",
                        rating_type,
                        rating_id,
                        usgs_effective_date,
                    )
                else:
                    logging.info(
                        "Stored USGS %s rating for %s with effective date %s.",
                        rating_type,
                        rating_id,
                        usgs_effective_date,
                    )

        except Exception as error:
            if is_fatal_service_error(error):
                raise

            storage_errors.append(
                [
                    rating_id,
                    station_number,
                    rating_type,
                    usgs_effective_date,
                    error,
                ]
            )

            logging.error(
                "FAIL: Error storing CWMS rating %s, USGS station %s, "
                "type %s. Error: %s",
                rating_id,
                station_number,
                rating_type,
                error,
            )

    logging.info("Completed USGS rating update process.")
    logging.info("Rating specifications considered: %s", total_records)
    if dry_run:
        logging.info("Ratings that would be stored: %s", would_store)
    else:
        logging.info("Ratings stored: %s", saved)
    logging.info("Ratings with matching effective dates: %s", same_effective)

    if dry_run and would_store_ratings:
        logging.info("Ratings that would be stored: %s", would_store_ratings)
    elif saved_ratings:
        logging.info("Stored ratings: %s", saved_ratings)

    if usgs_api_errors:
        logging.error("USGS API errors: %s", usgs_api_errors)

    if usgs_empty_errors:
        logging.warning(
            "No published USGS ratings found: %s",
            usgs_empty_errors,
        )

    if usgs_effective_date_errors:
        logging.error(
            "USGS effective-date parsing errors: %s",
            usgs_effective_date_errors,
        )

    if storage_errors:
        logging.error("CWMS rating storage errors: %s", storage_errors)
