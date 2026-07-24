"""Load an NWS/RFC Delft-FEWS PI-XML forecast product into a CWMS database.

This is the single implementation module behind ``cwms-cli nws pixml``. It unifies
the two office-specific loaders (MVP ``loadNWSChips.py`` and MVM ``getLMRFC_NAEFS``)
into one config-driven pipeline:

    fetch (file or URL, gz/zip) -> parse PI-XML -> resolve each series to a CWMS
    timeseries id -> store (optionally versioned) -> record the product issued time
    as a blob.

Everything office-specific lives in a JSON config (see ``docs/nws/*.example.json``).
"""

import ast
import gzip
import io
import json
import logging
import os
import re
import zipfile
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import cwms
import pandas as pd
import requests

from cwmscli.utils import init_cwms_session
from cwmscli.utils.intervals import ALL_INTERVAL_PARAMETERS

logger = logging.getLogger(__name__)

# CWMS sentinel for a missing value and its quality code.
CWMS_MISSING_VALUE = -340282346638528859811704183484516925440
CWMS_MISSING_QUALITY = 5
CWMS_GOOD_QUALITY = 0

DEFAULT_PI_NAMESPACE = "http://www.wldelft.nl/fews/PI"

# Regular CWMS interval names keyed by their length in seconds. Used to derive the
# interval segment of a built timeseries id from a PI-XML <timeStep> multiplier.
_SECONDS_TO_INTERVAL = {
    60: "1Minute",
    120: "2Minutes",
    180: "3Minutes",
    240: "4Minutes",
    300: "5Minutes",
    360: "6Minutes",
    480: "8Minutes",
    600: "10Minutes",
    720: "12Minutes",
    900: "15Minutes",
    1200: "20Minutes",
    1800: "30Minutes",
    3600: "1Hour",
    7200: "2Hours",
    10800: "3Hours",
    14400: "4Hours",
    21600: "6Hours",
    28800: "8Hours",
    43200: "12Hours",
    86400: "1Day",
    172800: "2Days",
    259200: "3Days",
    345600: "4Days",
    432000: "5Days",
    518400: "6Days",
    604800: "1Week",
}


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
def load_config(
    config_file: Optional[str], config_blob: Optional[str], office: str
) -> dict:
    """Load the JSON config from a local file or a CWMS blob."""
    if config_file:
        with open(config_file, "r") as f:
            return json.load(f)
    # config_blob: a session must already be initialized by the caller.
    raw = cwms.get_blob(blob_id=config_blob, office_id=office)
    if isinstance(raw, dict):
        return raw
    # cwms.get_blob wraps response with str(), which produces Python repr
    # (single quotes) when the API already deserialized JSON. Fall back to
    # ast.literal_eval for that case.
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return ast.literal_eval(raw)


# --------------------------------------------------------------------------- #
# Fetch
# --------------------------------------------------------------------------- #
def _basename(input_: str) -> str:
    """Return the filename portion of a path or URL (query/fragment stripped)."""
    if "://" in input_:
        input_ = urlparse(input_).path
    return os.path.basename(input_)


def fetch_xml(input_: str) -> bytes:
    """Return raw XML bytes from a local path or URL, unzipping .gz/.zip."""
    name = _basename(input_).lower()
    if "://" in input_:
        resp = requests.get(input_)
        resp.raise_for_status()
        data = resp.content
    else:
        with open(input_, "rb") as f:
            data = f.read()

    if name.endswith(".gz"):
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as gz:
            return gz.read()
    if name.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            inner = zf.namelist()[0]
            return zf.read(inner)
    return data


# --------------------------------------------------------------------------- #
# Parse
# --------------------------------------------------------------------------- #
def parse_series(xml_bytes: bytes, namespace: str) -> list:
    """Parse a PI-XML document into a list of series dicts."""
    ns = {"pi": namespace}
    root = ET.fromstring(xml_bytes)
    series_list = []
    for series in root.findall("pi:series", ns):
        header = series.find("pi:header", ns)
        if header is None:
            continue

        def _text(tag):
            el = header.find(f"pi:{tag}", ns)
            return el.text.strip() if el is not None and el.text else None

        time_step = header.find("pi:timeStep", ns)
        ts_unit = time_step.get("unit") if time_step is not None else None
        ts_mult = time_step.get("multiplier") if time_step is not None else None

        events = []
        miss_val = _text("missVal")
        for event in series.findall("pi:event", ns):
            events.append(
                (
                    f"{event.get('date')} {event.get('time')}",
                    event.get("value"),
                )
            )

        series_list.append(
            {
                "locationId": _text("locationId"),
                "parameterId": _text("parameterId"),
                "units": _text("units"),
                "missVal": miss_val,
                "ensembleId": _text("ensembleId"),
                "timeStep_unit": ts_unit,
                "timeStep_multiplier": ts_mult.strip() if ts_mult else None,
                "creationDate": _text("creationDate"),
                "creationTime": _text("creationTime"),
                "forecastDate": _forecast_datetime(header, ns),
                "events": events,
            }
        )
    return series_list


def _forecast_datetime(header, ns) -> Optional[str]:
    el = header.find("pi:forecastDate", ns)
    if el is None:
        return None
    return f"{el.get('date')} {el.get('time')}"


# --------------------------------------------------------------------------- #
# Alias table (NWS station id <-> CWMS location)
# --------------------------------------------------------------------------- #
def build_alias_table(config: dict, office: str) -> tuple:
    """Merge the configured location alias groups.

    Returns ``(nws_to_loc, loc_to_nws)`` dicts. Later groups override earlier
    ones (matching MVP's HB5 + RFC CHPS override behavior).
    """
    nws_to_loc: dict = {}
    loc_to_nws: dict = {}
    for group in config.get("location_alias_groups", []):
        data = cwms.get_location_group(
            loc_group_id=group["group_id"],
            category_id=group["category_id"],
            office_id=office,
            group_office_id=group.get("group_office_id"),
            category_office_id=group.get("category_office_id"),
        )
        df = data.df
        if df is None or df.empty or "alias-id" not in df.columns:
            continue
        df = df[df["alias-id"].notnull()]
        strip = group.get("alias_strip_suffix")
        for _, row in df.iterrows():
            loc = row["location-id"]
            nws = str(row["alias-id"])
            if strip and nws.endswith(strip):
                nws = nws[: -len(strip)]
            # Skip sub-location duplicates (e.g. "LOC-Sub") when the base already maps.
            if "-" in loc and nws in nws_to_loc:
                continue
            nws_to_loc[nws] = loc
            loc_to_nws[loc] = nws
    return nws_to_loc, loc_to_nws


def _lookup_location(location_id: str, nws_to_loc: dict) -> Optional[str]:
    """Resolve a PI-XML locationId to a CWMS location via the alias table."""
    if location_id in nws_to_loc:
        return nws_to_loc[location_id]
    # Fall back to the 5-char NWS Handbook-5 prefix (MVP convention).
    return nws_to_loc.get(location_id[:5])


# --------------------------------------------------------------------------- #
# Timeseries-group override map
# --------------------------------------------------------------------------- #
def build_tsgroup_map(config: dict, office: str, loc_to_nws: dict) -> dict:
    """Build a ``record_key -> timeseries-id`` override map from a TS group.

    Two kinds of key are registered, both matched against the record key
    ``alias_key_template.format(locationId, parameterId)``:

    * explicit ``alias-id`` values (MVP after the one-off migration), and
    * derived ``"{nws_alias}.{PARAM}"`` keys computed from each assigned TSID's
      location + parameter segment (reproduces MVM's Default-group matching).
    """
    tg = config.get("timeseries_group")
    if not tg:
        return {}

    data = cwms.get_timeseries_group(
        group_id=tg["group_id"],
        category_id=tg["category_id"],
        office_id=office,
        category_office_id=tg.get("category_office_id"),
        group_office_id=tg.get("group_office_id"),
    )
    df = data.df
    if df is None or df.empty:
        return {}

    derived = tg.get("derived", True)
    mapping: dict = {}
    for _, row in df.iterrows():
        tsid = row.get("timeseries-id")
        if not tsid:
            continue
        alias = row.get("alias-id")
        if alias is not None and pd.notna(alias):
            mapping[str(alias)] = tsid
        if derived:
            parts = str(tsid).split(".")
            if len(parts) >= 2:
                loc, param = parts[0], parts[1]
                nws = loc_to_nws.get(loc) or loc_to_nws.get(loc.split("-")[0])
                if nws:
                    mapping[f"{nws}.{param.upper()}"] = tsid
    return mapping


# --------------------------------------------------------------------------- #
# Interval + TSID building
# --------------------------------------------------------------------------- #
def derive_interval(
    ts_unit: Optional[str], ts_multiplier: Optional[str]
) -> Optional[str]:
    """Derive a CWMS interval string from a PI-XML <timeStep>."""
    if ts_unit == "nonequidistant" or ts_unit is None:
        return "0"  # irregular / instantaneous
    if ts_unit == "second" and ts_multiplier:
        seconds = int(float(ts_multiplier))
        interval = _SECONDS_TO_INTERVAL.get(seconds)
        if interval and interval in ALL_INTERVAL_PARAMETERS:
            return interval
    return None


def _param_type_and_duration(config: dict, param: str) -> tuple:
    d_type = config.get("default_type", "Inst")
    duration = config.get("default_duration", "0")
    for rule in config.get("param_type_rules", []):
        if rule.get("param_contains") and rule["param_contains"] in param:
            d_type = rule.get("type", d_type)
            duration = rule.get("duration", duration)
    return d_type, duration


def resolve_tsid(
    record: dict,
    config: dict,
    nws_to_loc: dict,
    tsgroup_map: dict,
    version_part: str,
) -> Optional[str]:
    """Resolve a series to a CWMS timeseries id, or None (with a warning) to skip."""
    location_id = record["locationId"]
    parameter_id = record["parameterId"]

    # (1) Timeseries-group override (handles odd/aliased cases). When the run
    # defines a version part, swap it into the resolved id so one alias entry
    # serves every run (base/auto/CRF); otherwise (e.g. MVM) use it verbatim.
    if tsgroup_map:
        template = config.get("timeseries_group", {}).get(
            "alias_key_template", "{locationId}.{parameterId}"
        )
        key = template.format(locationId=location_id, parameterId=parameter_id)
        if key in tsgroup_map:
            tsid = tsgroup_map[key]
            if version_part:
                parts = tsid.split(".")
                if len(parts) == 6:
                    parts[5] = version_part
                    tsid = ".".join(parts)
            return tsid

    # (2) Built fallback.
    param = config.get("parameter_map", {}).get(parameter_id)
    if param is None:
        logger.warning(
            "Unknown parameter %s at %s - skipping", parameter_id, location_id
        )
        return None

    cwms_loc = _lookup_location(location_id, nws_to_loc)
    if cwms_loc is None:
        logger.warning("No CWMS location for %s - skipping", location_id)
        return None

    interval = derive_interval(record["timeStep_unit"], record["timeStep_multiplier"])
    if interval is None:
        logger.warning(
            "Could not derive interval for %s (%s) - skipping",
            location_id,
            record["timeStep_multiplier"],
        )
        return None

    d_type, duration = _param_type_and_duration(config, param)
    return f"{cwms_loc}.{param}.{d_type}.{interval}.{duration}.{version_part}"


# --------------------------------------------------------------------------- #
# Run selection + versioning
# --------------------------------------------------------------------------- #
def select_run(config: dict, filename: str) -> dict:
    """Pick the matching run rule (top-to-bottom; the default matches last)."""
    for run in config.get("runs", []):
        match = run.get("match", {})
        if match.get("default"):
            return run
        contains = match.get("filename_contains")
        if contains and contains in filename:
            return run
    # No run rules: single unversioned run with an empty version part override.
    return {"version_part": config.get("default_version_part", ""), "versioned": False}


def _filename_timestamp(filename: str) -> Optional[datetime]:
    """Parse the trailing .YYYYMMDDHHMMSS timestamp from a product filename."""
    stamp = filename.split(".")[-1]
    try:
        return datetime.strptime(stamp, "%Y%m%d%H%M%S")
    except ValueError:
        return None


def compute_version_date(
    run: dict, series: list, filename_dt: Optional[datetime]
) -> Optional[datetime]:
    """Compute the version date for a run, or None if unversioned."""
    if not run.get("versioned"):
        return None

    source = run.get("version_source", "filename_timestamp")
    base: Optional[datetime] = None
    if source == "filename_timestamp":
        base = filename_dt
    elif source == "creation_date":
        base = _first_creation_datetime(series)
    elif source == "forecast_date":
        for rec in series:
            if rec.get("forecastDate"):
                base = _parse_dt(rec["forecastDate"])
                break

    if base is None:
        logger.warning("Could not determine version date (source=%s)", source)
        return None

    snap = run.get("version_snap_time")
    if snap:
        h, m, s = (int(x) for x in snap.split(":"))
        base = base.replace(hour=h, minute=m, second=s, microsecond=0)
    return base.replace(tzinfo=timezone.utc)


def _first_creation_datetime(series: list) -> Optional[datetime]:
    for rec in series:
        if rec.get("creationDate") and rec.get("creationTime"):
            return _parse_dt(f"{rec['creationDate']} {rec['creationTime']}")
    return None


def _parse_dt(value: str) -> Optional[datetime]:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


# --------------------------------------------------------------------------- #
# Issued-time blob (single consolidated JSON document for the dashboard)
# --------------------------------------------------------------------------- #
def _run_slots(config: dict) -> list:
    """The distinct issued-time slots defined across the config's run rules."""
    slots = []
    for run in config.get("runs", []):
        slot = run.get("issued_slot")
        if slot and slot not in slots:
            slots.append(slot)
    return slots


def build_issued_update(
    config: dict, run: dict, filename: str, issued_dt: Optional[datetime]
) -> Optional[dict]:
    """Describe the single-watershed update to apply to the issued-time blob.

    Returns None when issued-time tracking is not configured, the run has no
    slot, or no issued datetime is available.
    """
    cfg = config.get("issued_time")
    if not cfg or issued_dt is None:
        return None
    slot = run.get("issued_slot")
    if not slot:
        return None

    match = re.search(cfg["watershed_from_filename"], filename)
    if not match:
        logger.warning("Could not extract watershed from %s", filename)
        return None
    watershed = match.group(1)

    return {
        "blob_id": cfg["blob_id"],
        "watershed": watershed,
        "slot": slot,
        "mapping": config.get("watersheds", {}).get(watershed, {}),
        "value": issued_dt.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _build_blob_document(config: dict, existing: dict, update: dict) -> dict:
    """Merge one watershed's issued time into the consolidated blob document.

    Every watershed in the config is seeded with its NCRFC->CWMS mapping and a
    null for each slot, so the dashboard can render all rows from the blob alone.
    """
    slots = _run_slots(config)
    doc = dict(existing)
    # Seed / refresh mapping for every configured watershed.
    for key, meta in config.get("watersheds", {}).items():
        entry = dict(doc.get(key, {}))
        entry["label"] = meta.get("label", entry.get("label"))
        entry["cwms_watershed"] = meta.get(
            "cwms_watershed", entry.get("cwms_watershed")
        )
        for slot in slots:
            entry.setdefault(slot, None)
        doc[key] = entry
    # Apply this run's issued time (create the entry if the watershed is unknown).
    entry = dict(doc.get(update["watershed"], {}))
    for field, value in update["mapping"].items():
        entry.setdefault(field, value)
    for slot in slots:
        entry.setdefault(slot, None)
    entry[update["slot"]] = update["value"]
    doc[update["watershed"]] = entry
    return doc


def _merge_issued_blob(config: dict, office: str, update: dict) -> None:
    """Read the consolidated issued-time blob, merge this update, and write it back."""
    blob_id = update["blob_id"]
    existing: dict = {}
    exists = False
    try:
        cwms_logger = logging.getLogger("cwms")
        prev_level = cwms_logger.level
        cwms_logger.setLevel(logging.CRITICAL)
        try:
            raw = cwms.get_blob(blob_id=blob_id, office_id=office)
            exists = True
        finally:
            cwms_logger.setLevel(prev_level)
        if isinstance(raw, dict):
            existing = raw
        else:
            try:
                existing = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                import ast

                existing = ast.literal_eval(raw)
    except Exception:
        logger.debug("Blob %s not found, will create", blob_id)
        existing = {}

    doc = _build_blob_document(config, existing, update)
    payload = {
        "office-id": office,
        "id": blob_id,
        "description": "NCRFC forecast issued times and watershed mapping",
        "media-type-id": config.get("issued_time", {}).get(
            "media_type", "application/json"
        ),
        "value": json.dumps(doc, indent=2, sort_keys=True),
    }
    if exists:
        cwms.update_blob(payload)
    else:
        cwms.store_blobs(payload, fail_if_exists=False)


# --------------------------------------------------------------------------- #
# Series -> CWMS store
# --------------------------------------------------------------------------- #
def _series_dataframe(record: dict) -> pd.DataFrame:
    miss = record["missVal"]
    rows = []
    for dt_str, value in record["events"]:
        if value == miss:
            rows.append((dt_str, CWMS_MISSING_VALUE, CWMS_MISSING_QUALITY))
        else:
            rows.append((dt_str, float(value), CWMS_GOOD_QUALITY))
    df = pd.DataFrame(rows, columns=["date-time", "value", "quality-code"])
    df["date-time"] = pd.to_datetime(df["date-time"]).dt.tz_localize("UTC")
    return df


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def load_pixml(
    *,
    input_: str,
    config_file: Optional[str],
    config_blob: Optional[str],
    office: str,
    api_key: Optional[str],
    api_root: str,
    dry_run: bool,
) -> None:
    filename = _basename(input_)
    logger.info("Processing %s (office=%s)", filename, office)

    # A session is always needed: resolving timeseries ids reads the location and
    # timeseries groups from CDA (and a config blob, if used). Only the *writes*
    # are skipped in a dry run.
    prefixed = f"apikey {api_key}" if api_key else None
    init_cwms_session(cwms, api_root=api_root, api_key=prefixed)
    logger.info("CDA connection: %s", api_root)

    config = load_config(config_file, config_blob, office)
    namespace = config.get("pi_namespace", DEFAULT_PI_NAMESPACE)

    series = parse_series(fetch_xml(input_), namespace)
    logger.info("Parsed %d series", len(series))

    run = select_run(config, filename)
    version_part = run.get("version_part", "")
    filename_dt = _filename_timestamp(filename)
    version_date = compute_version_date(run, series, filename_dt)
    logger.info(
        "Run version part=%r versioned=%s version_date=%s",
        version_part,
        run.get("versioned", False),
        version_date,
    )

    nws_to_loc, loc_to_nws = build_alias_table(config, office)
    tsgroup_map = build_tsgroup_map(config, office, loc_to_nws)

    stored = 0
    skipped = 0
    errors = []
    planned = []
    for record in series:
        tsid = resolve_tsid(record, config, nws_to_loc, tsgroup_map, version_part)
        if tsid is None:
            skipped += 1
            continue
        planned.append((tsid, record["units"]))
        if dry_run:
            continue
        try:
            df = _series_dataframe(record)
            data_json = cwms.timeseries_df_to_json(
                data=df,
                ts_id=tsid,
                units=record["units"],
                office_id=office,
                version_date=version_date,
            )
            cwms.store_timeseries(data=data_json)
            stored += 1
        except Exception as error:  # noqa: BLE001 - collected and reported below
            errors.append((tsid, str(error)))
            logger.error("Failed to store %s: %s", tsid, error)

    issued_update = build_issued_update(config, run, filename, filename_dt)

    if dry_run:
        logger.info("--- DRY RUN --- no data was written")
        print(
            json.dumps(
                {
                    "filename": filename,
                    "version_part": version_part,
                    "versioned": run.get("versioned", False),
                    "version_date": version_date.isoformat() if version_date else None,
                    "resolved_timeseries": [t for t, _ in planned],
                    "skipped": skipped,
                    "issued_update": issued_update,
                },
                indent=2,
            )
        )
        return

    if issued_update:
        _merge_issued_blob(config, office, issued_update)
        logger.info(
            "Updated issued time for %s [%s] in blob %s",
            issued_update["watershed"],
            issued_update["slot"],
            issued_update["blob_id"],
        )

    total = stored + len(errors) + skipped
    if errors:
        logger.error(
            "Summary: %d/%d stored, %d FAILED, %d skipped",
            stored,
            total,
            len(errors),
            skipped,
        )
        for tsid, err in errors:
            logger.error("  FAILED: %s — %s", tsid, err)
    else:
        logger.info(
            "Summary: %d/%d stored, 0 failed, %d skipped",
            stored,
            total,
            skipped,
        )
