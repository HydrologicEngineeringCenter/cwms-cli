#!/usr/bin/env python3
"""
import_infile.py
========================
Convert an exportShef .in configuration file into a CWMS timeseries group
(category = "SHEF Export") using the cwms-python library.

Each timeseries entry in the .in file becomes a member of the group, with
the SHEF encoding stored in the alias-id field:

    alias-id = <SHEF_LOC>.<PE_CODE>.<SEND_CODE>.<DURATION_VALUE>[:Units=<UNITS>]
    e.g.       ALMW3.QT.RZ.0

Supported .in file formats
--------------------------
The parser auto-detects the following data-line layouts (any section name,
whitespace / pipe / comma delimited):

  1. Whitespace columns   (most common CWMS exportShef style)
         LockDam_04.Flow-Out.Inst.15Minutes.0.rev   ALMW3   QT   ZZZ   1001

  2. Pipe delimited
         LockDam_04.Flow-Out.Inst.15Minutes.0.rev|ALMW3|QT|ZZZ|1001

  3. Comma delimited
         LockDam_04.Flow-Out.Inst.15Minutes.0.rev,ALMW3,QT,ZZZ,1001

  4. TSID = shef_loc.pe_code.duration.send_code  (dot-joined alias on RHS)
         LockDam_04.Flow-Out.Inst.15Minutes.0.rev = ALMW3.QT.ZZZ.1001

  5. Flat-file (no [section] headers), using any token format above.

Header parameters ([parms] / [config] section or bare key=value lines
before data rows) are read for informational purposes but not required.

Prerequisites
-------------
    pip install cwms-python pandas

"""

from __future__ import annotations

import configparser
import logging
import re
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

try:
    import cwms
    import cwms.api as cwms_api
except ImportError:
    sys.exit(
        "ERROR: cwms-python is not installed.\n" "       Run:  pip install cwms-python"
    )

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_CATEGORY = "SHEF Export"
DEFAULT_CSV_PATH = Path(__file__).parent / "shef_parameters.csv"

# A CWMS TSID always has exactly 6 dot-separated parts:
#   Location . Parameter . ParameterType . Interval . Duration . Version
# Allow optional leading ~ in any part after the location
# (e.g., ~15Minutes, ~1Day)
TSID_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_\-]*"  # location (no ~)
    r"(?:\.~?[A-Za-z0-9][A-Za-z0-9_\-]*){5}$"  # 5 more parts, ~ optional
)

# Map CWMS duration unit suffixes to SHEF numeric duration base values
_CWMS_DUR_BASES = {
    "Minute": 0,
    "Minutes": 0,
    "Hour": 1000,
    "Hours": 1000,
    "Day": 2000,
    "Days": 2000,
    "Month": 3000,
    "Months": 3000,
    "Year": 4000,
    "Years": 4000,
}


def _cwms_duration_to_shef_value(cwms_duration: str) -> int:
    """Convert a CWMS TSID duration string (e.g. '0', '1Day') to a SHEF
    numeric duration value (e.g. 0, 2001)."""
    cwms_duration = cwms_duration.lstrip("~")
    if cwms_duration == "0":
        return 0
    m = re.match(r"(\d+)(\w+)", cwms_duration)
    if not m:
        return 0
    quantity = int(m.group(1))
    unit = m.group(2)
    base = _CWMS_DUR_BASES.get(unit)
    if base is not None:
        return base + quantity
    return 0


def _parse_shef_parameters_csv(
    path: Path,
) -> tuple[list[tuple[str, str]], dict[str, str]]:
    """Parse shef_parameters.csv and return:
    - mappings: (c_part, pe_code) tuples for PE resolution
    - pe_units: {pe_code: unit} for default units (skips 'n/a')
    """
    mappings: list[tuple[str, str]] = []
    pe_units: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("*"):
            continue
        parts = line.split(",")
        if len(parts) < 3:
            continue
        pe_code = parts[0].strip()
        c_part = parts[1].strip()
        unit = parts[2].strip() if len(parts) > 2 else ""
        if not pe_code or not c_part:
            continue
        mappings.append((c_part, pe_code))
        if unit and unit.lower() != "n/a":
            pe_units[pe_code] = unit
    return mappings, pe_units


# ---------------------------------------------------------------------------
# .in file parser
# ---------------------------------------------------------------------------


def parse_in_file(
    path: Path,
    csv_path: Optional[Path] = None,
) -> tuple[dict, list[dict]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    log.debug("Raw file (first 400 chars):\n%s", text[:400])

    # Try the directive/contextual format first (LOCATION / PE / TS blocks)
    header, entries = _contextual_parse(text, csv_path=csv_path)
    if entries:
        return header, entries

    # Fallback: INI / section-based parsing
    header, entries = _try_ini_parse(text)
    if entries:
        return header, entries

    # Final fallback: raw line scan
    return _raw_scan(text)


# ---- INI parser -----------------------------------------------------------


def _try_ini_parse(text: str) -> tuple[dict, list[dict]]:
    """Try parsing with configparser after light normalisation."""
    normalised: list[str] = []
    current_section: Optional[str] = None

    for line in text.splitlines():
        stripped = line.strip()

        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped[1:-1].lower()
            normalised.append(line)

        elif stripped.startswith(("#", ";")):
            normalised.append(line)

        elif not stripped:
            normalised.append(line)

        elif (
            current_section in (None, "parms", "config", "settings", "header")
            and "=" not in stripped
            and "|" not in stripped
            and "," not in stripped
        ):
            # Normalise "key  value" parm lines -> "key = value"
            parts = stripped.split(None, 1)
            if len(parts) == 2 and "." not in parts[0]:
                normalised.append(f"{parts[0]} = {parts[1]}")
                continue
            normalised.append(line)

        else:
            normalised.append(line)

    cp = configparser.RawConfigParser()
    cp.optionxform = str  # preserve case

    try:
        cp.read_string("\n".join(normalised))
    except configparser.Error as exc:
        log.debug("configparser failed (%s) — falling back to raw scan.", exc)
        return {}, []

    # Extract header parameters
    header: dict = {}
    for sec in ("parms", "config", "settings", "header"):
        if cp.has_section(sec):
            header = dict(cp.items(sec))
            break

    # Extract timeseries entries from all non-header sections
    entries: list[dict] = []
    HEADER_SECS = {"parms", "config", "settings", "header"}

    for sec in cp.sections():
        if sec.lower() in HEADER_SECS:
            continue
        for key, value in cp.items(sec):
            # configparser stores "TSID = alias" as key=tsid, value=alias
            entry = _parse_entry_line(f"{key} {value}".strip())
            if entry:
                entries.append(entry)

    return header, entries


# ---- Raw line scanner -----------------------------------------------------


def _raw_scan(text: str) -> tuple[dict, list[dict]]:
    """Line-by-line fallback when there are no INI section headers."""
    header: dict = {}
    entries: list[dict] = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";")):
            continue
        if stripped.startswith("["):
            continue

        # Simple key=value header lines (fewer than 5 dots → not a TSID)
        if "=" in stripped and stripped.count(".") < 5:
            k, _, v = stripped.partition("=")
            if not TSID_RE.match(k.strip()):
                header[k.strip().lower()] = v.strip()
                continue

        entry = _parse_entry_line(stripped)
        if entry:
            entries.append(entry)

    return header, entries


# ---- Single-line entry parser ---------------------------------------------


def _parse_entry_line(line: str) -> Optional[dict]:
    """
    Parse one timeseries entry from a single text line.

    Accepted patterns
    -----------------
    a)  Whitespace tokens:   TSID  SHEF_LOC  PE  DUR  SEND
    b)  Pipe-delimited:      TSID|SHEF_LOC|PE|DUR|SEND
    c)  Comma-delimited:     TSID,SHEF_LOC,PE,DUR,SEND
    d)  Dot-joined alias:    TSID = SHEF_LOC.PE.DUR.SEND
    """
    stripped = line.strip()
    if not stripped or stripped.startswith(("#", ";")):
        return None

    # Pattern d: TSID [=:] shef_loc.pe.dur.send
    m = re.match(
        r"^(?P<tsid>[A-Za-z0-9_\-]+(?:\.[A-Za-z0-9_\-]+){5})"
        r"\s*[=:]\s*"
        r"(?P<loc>[A-Za-z0-9]+)\.(?P<pe>[A-Za-z0-9]+)\."
        r"(?P<dur>[A-Za-z0-9]+)\.(?P<send>[A-Za-z0-9]+)$",
        stripped,
    )
    if m:
        return {
            "tsid": m.group("tsid"),
            "shef_loc": m.group("loc"),
            "pe_code": m.group("pe"),
            "duration": m.group("dur"),
            "send_code": m.group("send"),
        }

    # Patterns a / b / c: split then locate the 6-part TSID
    for delim in ("|", ",", None):
        parts = (
            [p.strip() for p in stripped.split(delim)]
            if delim is not None
            else stripped.split()
        )
        entry = _parts_to_entry(parts)
        if entry:
            return entry

    return None


def _parts_to_entry(parts: list[str]) -> Optional[dict]:
    """Return an entry dict from a token list that contains a TSID."""
    if len(parts) < 5:
        return None
    for i, part in enumerate(parts):
        if TSID_RE.match(part):
            rest = parts[i + 1 :]
            if len(rest) >= 4:
                return {
                    "tsid": part,
                    "shef_loc": rest[0],
                    "pe_code": rest[1],
                    "duration": rest[2],
                    "send_code": rest[3],
                }
            break
    return None


def _resolve_pe_code(
    parameter: str,
    pe_mappings: list[tuple[str, str]],
) -> Optional[str]:
    """
    Match a CWMS parameter name against ordered PE rules.
    Pattern 'Flow-Out.*' matches 'Flow-Out' or anything starting with 'Flow-Out'.
    First match wins — list more-specific rules first in the .in file.
    """
    for pattern, code in pe_mappings:
        base = re.sub(r"\.\*$|\*$", "", pattern)  # strip trailing .* or *
        if parameter == base or parameter.startswith(base):
            return code
    return None


def _contextual_parse(
    text: str,
    csv_path: Optional[Path] = None,
) -> tuple[dict, list[dict]]:
    """
    Parse the directive-based exportShef .in format in a single pass.

    PE mappings are **positional** — a ``PE`` directive applies to every
    TSID that follows it.  The optional *csv_path* provides base defaults
    (from ``shef_parameters.csv``); ``PE`` directives in the ``.in`` file
    override or extend those defaults from their position onward.
    """
    # ---- Quick pre-scan: is this a contextual-format file? ---------------
    has_location = bool(re.search(r"^LOCATION\s+", text, re.IGNORECASE | re.MULTILINE))
    has_pe = bool(re.search(r"^PE\s+", text, re.IGNORECASE | re.MULTILINE))
    if not has_location and not has_pe:
        return {}, []

    # ---- Load CSV defaults as initial PE mappings ------------------------
    pe_mappings: list[tuple[str, str]] = []
    pe_units: dict[str, str] = {}
    if csv_path and csv_path.exists():
        pe_mappings, pe_units = _parse_shef_parameters_csv(csv_path)
        log.debug("Loaded %d default PE mappings from %s", len(pe_mappings), csv_path)
    elif csv_path:
        log.warning("SHEF parameters CSV not found: %s", csv_path)

    # ---- Single-pass contextual scan -------------------------------------
    HEADER_KEYWORDS = {
        "debug",
        "type",
        "delimiter",
        "timewindow",
        "revised",
        "system",
        "tzone",
        "db",
    }

    header: dict = {}
    entries: list[dict] = []

    current_send_code = "ZZZ"
    current_shef_loc: Optional[str] = None
    location_map: dict[str, str] = {}  # cwms_location_name -> shef_id

    for raw in text.splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue

        # TS * = SEND_CODE
        m = re.match(r"^TS\s+\*\s*=\s*(\S+)\s*$", s, re.IGNORECASE)
        if m:
            current_send_code = m.group(1)
            log.debug("Send code → %s", current_send_code)
            continue

        # PE pattern = CODE[;units=UNIT]  (positional — update mappings in place)
        m = re.match(
            r"^PE\s+(\S+)\s*=\s*([A-Za-z0-9]+)(?:[;:]units=(\S+))?\s*$",
            s,
            re.IGNORECASE,
        )
        if m:
            pat, code, pe_unit = m.group(1), m.group(2), m.group(3)
            # Replace if same pattern already exists, otherwise prepend
            replaced = False
            for i, (existing_pat, _) in enumerate(pe_mappings):
                if existing_pat == pat:
                    pe_mappings[i] = (pat, code)
                    replaced = True
                    break
            if not replaced:
                pe_mappings.insert(0, (pat, code))
            if pe_unit:
                pe_units[code] = pe_unit
            log.debug(
                "PE mapping: %s → %s%s",
                pat,
                code,
                f" (units={pe_unit})" if pe_unit else "",
            )
            continue

        # LOCATION cwms_loc = shef_id
        m = re.match(r"^LOCATION\s+(\S+)\s*=\s*(\S+)\s*$", s, re.IGNORECASE)
        if m:
            cwms_loc, shef_id = m.group(1), m.group(2)
            location_map[cwms_loc] = shef_id
            current_shef_loc = shef_id
            log.debug("Location map: %s → %s", cwms_loc, shef_id)
            continue

        # Header key-value lines  (e.g. "DEBUG 3", "TZONE Z")
        first_tok = s.split()[0].lower()
        if first_tok in HEADER_KEYWORDS:
            parts = s.split(None, 1)
            header[parts[0].lower()] = parts[1].strip() if len(parts) > 1 else ""
            continue

        # ---- Potential TSID line ----------------------------------------
        # Capture optional ;units=... annotation before stripping it
        units = None
        units_match = re.search(r";units=(\S+)", s, re.IGNORECASE)
        if units_match:
            units = units_match.group(1)
        tsid_str = re.sub(r"\s*[;:].*$", "", s).strip()
        if not TSID_RE.match(tsid_str):
            continue

        cwms_parts = tsid_str.split(".")
        cwms_location = cwms_parts[0]
        cwms_parameter = cwms_parts[1]
        cwms_duration = cwms_parts[4]

        # Resolve SHEF location
        #   1. Exact match in location_map
        #   2. Longest-prefix match (handles sub-locations like
        #      LockDam_04-Tailwater, LockDam_02-Powerhouse, etc.)
        #      Preserves sublocation suffix: if LOCATION LockDam_02=HSTM5
        #      is set and cwms_location=LockDam_02-Powerhouse, then
        #      shef_loc becomes HSTM5-Powerhouse
        #   3. Handle wildcard * at end of key (e.g., LockDam_08*=GENW3 matches LockDam_08-Tailwater)
        #   4. Fall back to most-recently-set current_shef_loc
        shef_loc = location_map.get(cwms_location)
        if not shef_loc:
            best = max(
                (
                    k
                    for k in location_map
                    if cwms_location == k
                    or cwms_location.startswith(k + "-")
                    or (k.endswith("*") and cwms_location.startswith(k[:-1]))
                ),
                key=len,
                default=None,
            )
            if best:
                mapped_value = location_map[best]
                # If this was a prefix match (not exact), preserve the sublocation suffix
                if cwms_location != best and cwms_location.startswith(best + "-"):
                    sublocation = cwms_location[len(best) :]
                    shef_loc = mapped_value + sublocation
                else:
                    shef_loc = mapped_value
        if not shef_loc:
            shef_loc = current_shef_loc

        if not shef_loc:
            log.warning("No SHEF location found for TSID: %s — skipping.", tsid_str)
            continue

        # Resolve PE code (first matching rule wins)
        pe_code = _resolve_pe_code(cwms_parameter, pe_mappings)
        if not pe_code:
            log.warning(
                "No PE mapping for parameter '%s' (TSID: %s) — skipping.",
                cwms_parameter,
                tsid_str,
            )
            continue

        duration_value = _cwms_duration_to_shef_value(cwms_duration)
        # Use CSV default unit as fallback when .in file doesn't specify
        if not units and pe_code in pe_units:
            units = pe_units[pe_code]

        entry = {
            "tsid": tsid_str,
            "shef_loc": shef_loc,
            "pe_code": pe_code,
            "duration": str(duration_value),
            "send_code": current_send_code,
        }
        if units:
            entry["units"] = units
        entries.append(entry)

    return header, entries


# ---------------------------------------------------------------------------
# Alias builder
# ---------------------------------------------------------------------------


def build_alias(entry: dict) -> str:
    """Return SHEF alias string: SHEF_LOC.PE_CODE.SEND_CODE.DURATION[:Units=U]."""
    alias = (
        f"{entry['shef_loc']}.{entry['pe_code']}."
        f"{entry['send_code']}.{entry['duration']}"
    )
    if "units" in entry:
        alias += f":Units={entry['units']}"
    return alias


# ---------------------------------------------------------------------------
# CWMS group JSON builder
# ---------------------------------------------------------------------------


def build_group_json(
    entries: list[dict],
    group_id: str,
    office_id: str,
    category_id: str,
) -> dict:
    """Build the cwms-python JSON payload for a timeseries group."""
    df = pd.DataFrame(
        [
            {
                "office-id": office_id,
                "timeseries-id": e["tsid"],
                "alias-id": build_alias(e),
                "attribute": i,
            }
            for i, e in enumerate(entries)
        ]
    )
    return cwms.timeseries_group_df_to_json(
        data=df,
        group_id=group_id,
        group_office_id=office_id,
        category_office_id="CWMS",
        category_id=category_id,
    )


# ---------------------------------------------------------------------------
# Store / update via cwms-python
# ---------------------------------------------------------------------------


def store_group(
    group_json: dict,
    group_id: str,
    office_id: str,
    fail_if_exists: bool,
) -> None:
    """POST (create) or PATCH (update) the timeseries group in CWMS."""
    try:
        cwms.store_timeseries_groups(group_json, fail_if_exists=fail_if_exists)
        log.info("SUCCESS — group stored via store_timeseries_groups.")
        return
    except Exception as exc:
        log.warning(
            "store_timeseries_groups raised %s: %s — retrying with update ...",
            type(exc).__name__,
            exc,
        )

    # Fallback: update, replacing all assigned timeseries
    cwms.update_timeseries_groups(
        data=group_json,
        group_id=group_id,
        office_id=office_id,
        replace_assigned_ts=True,
    )
    log.info("SUCCESS — group updated via update_timeseries_groups.")


# ---------------------------------------------------------------------------
# Importable function for CLI integration
# ---------------------------------------------------------------------------


def import_shef_infile(
    in_file: str,
    group_name: str,
    office_id: str,
    api_root: Optional[str] = None,
    api_key: Optional[str] = None,
    token: Optional[str] = None,
    category_id: str = DEFAULT_CATEGORY,
    fail_if_exists: bool = False,
    shef_params: Optional[Path] = None,
    dry_run: bool = False,
) -> None:
    """
    Import a SHEF .in file and create/update a CWMS timeseries group.

    Parameters
    ----------
    in_file : str
        Path to the exportShef .in configuration file.
    group_name : str
        CWMS timeseries group name.
    office_id : str
        CWMS office ID.
    api_root : str, optional
        CWMS Data API root URL. Required unless dry_run is True.
    api_key : str, optional
        API key for authentication.
    token : str, optional
        Keycloak bearer token (takes precedence over api_key).
    category_id : str, optional
        Timeseries category ID. Default: "SHEF Export".
    fail_if_exists : bool, optional
        Fail if the group already exists. Default: False.
    shef_params : Path, optional
        Path to shef_parameters.csv. Default: bundled CSV in utils.
    dry_run : bool, optional
        Parse the .in file and print the JSON payload without posting to the API.

    Returns
    -------
    None
    """
    in_path = Path(in_file)
    if not in_path.exists():
        log.error("File not found: %s", in_path)
        return

    if not dry_run and not api_root:
        log.error("api_root is required unless dry_run is True.")
        return

    if shef_params is None:
        shef_params = DEFAULT_CSV_PATH

    # Parse .in file
    log.info("Parsing: %s", in_path)
    header, entries = parse_in_file(in_path, csv_path=shef_params)

    if header:
        log.info("Header / config parameters found:")
        for k, v in header.items():
            log.info("  %-20s = %s", k, v)

    if not entries:
        log.error("No timeseries entries found in %s", in_path)
        return

    log.info("Found %d timeseries entries:", len(entries))
    for e in entries:
        log.info("  %-60s  alias=%s", e["tsid"], build_alias(e))

    # Build JSON payload
    group_json = build_group_json(entries, group_name, office_id, category_id)

    if dry_run:
        import json

        print("\n--- DRY RUN: CWMS JSON payload ---")
        print(json.dumps(group_json, indent=2))
        print("\n--- Dry run complete. Nothing was posted to the API. ---")
        return

    # Connect to CWMS Data API
    log.info("Connecting to API: %s", api_root)
    cwms_api.init_session(api_root=api_root, api_key=api_key, token=token)

    # Store / update the group
    store_group(
        group_json=group_json,
        group_id=group_name,
        office_id=office_id,
        fail_if_exists=fail_if_exists,
    )

    log.info(
        "Done.\n  Group    : %s\n  Category : %s\n  Office   : %s\n  Entries  : %d",
        group_name,
        category_id,
        office_id,
        len(entries),
    )
