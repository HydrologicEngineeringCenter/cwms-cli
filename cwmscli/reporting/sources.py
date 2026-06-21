import logging
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from cwmscli.reporting.models import ProjectSpec
from cwmscli.reporting.values import coerce_cda_datetimes
from cwmscli.utils import colors

LOGGER = logging.getLogger(__name__)


def _status(label: str, detail: str, color: str = "cyan") -> None:
    LOGGER.info("%s %s", colors.c(label, color, bright=True), detail)


def fetch_timeseries_df(
    tsids: List[str],
    office: str,
    unit: str,
    begin: Optional[datetime],
    end: Optional[datetime],
    timeout_seconds: float,
    retry_count: int = 3,
):
    import pandas as pd

    _status(
        "[report]",
        f"Requesting {len(tsids)} time series from CWMS "
        f"(office={office}, unit={unit}, timeout={timeout_seconds:g}s)",
        "cyan",
    )
    LOGGER.debug(
        "[report] timeseries request begin=%s end=%s tsids=%s",
        begin.isoformat() if begin else None,
        end.isoformat() if end else None,
        tsids,
    )
    value_rows: List[Dict[str, Any]] = []
    max_workers = max(1, min(len(tsids), 8))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(
                fetch_timeseries_values,
                tsid=tsid,
                office=office,
                unit=unit,
                begin=begin,
                end=end,
                timeout_seconds=timeout_seconds,
                retry_count=retry_count,
            ): tsid
            for tsid in tsids
        }
        for index, future in enumerate(as_completed(future_map), start=1):
            tsid = future_map[future]
            try:
                rows = future.result()
            except Exception as err:
                LOGGER.warning(
                    "%s %s",
                    colors.c("[report]", "yellow", bright=True),
                    f"Skipping {tsid}: {err}",
                )
                continue
            value_rows.extend(rows)
            _status(
                "[report]",
                f"Completed {index}/{len(tsids)} time series: {tsid} "
                f"({len(rows)} value row(s))",
                "green",
            )

    df = pd.DataFrame(value_rows)
    if not df.empty and "date-time" in df.columns:
        df["date-time"] = coerce_cda_datetimes(df["date-time"])
    _status(
        "[report]",
        f"Received {len(df)} time series value rows from CWMS",
        "green",
    )
    return df


def fetch_timeseries_values(
    *,
    tsid: str,
    office: str,
    unit: str,
    begin: Optional[datetime],
    end: Optional[datetime],
    timeout_seconds: float,
    retry_count: int = 3,
) -> List[Dict[str, Any]]:
    from cwms import api

    params = {
        "office": office,
        "name": tsid,
        "unit": unit,
        "begin": begin.isoformat() if begin else None,
        "end": end.isoformat() if end else None,
        "page-size": 300000,
        "trim": True,
    }
    params = {key: value for key, value in params.items() if value is not None}
    url = f"{api.SESSION.base_url.rstrip('/')}/timeseries"
    headers = dict(api.SESSION.headers)
    headers["Accept"] = "application/json;version=2"
    LOGGER.debug("[report] direct CDA request url=%s params=%s", url, params)

    response = None
    with requests.Session() as session:
        for attempt in range(1, max(1, retry_count) + 1):
            try:
                response = session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=timeout_seconds,
                )
                if response.status_code == 404:
                    LOGGER.warning(
                        "%s %s",
                        colors.c("[report]", "yellow", bright=True),
                        f"CDA returned 404 for {tsid}; report will show missing value.",
                    )
                    return []
                response.raise_for_status()
                break
            except requests.RequestException:
                if attempt >= max(1, retry_count):
                    raise
                _status(
                    "[report]",
                    f"Retrying {tsid} after request failure "
                    f"({attempt}/{max(1, retry_count)})",
                    "yellow",
                )
                time.sleep(0.5 * attempt)
    if response is None:
        return []
    payload = response.json()
    rows = []
    for value in payload.get("values", []):
        if len(value) < 2:
            continue
        rows.append(
            {
                "ts_id": tsid,
                "date-time": value[0],
                "value": value[1],
                "units": payload.get("units"),
            }
        )
    return rows


def fetch_level_values(
    level_ids: List[str],
    begin: Optional[datetime],
    end: Optional[datetime],
    office: str,
    unit: str,
) -> Dict[str, Optional[float]]:
    import cwms

    out: Dict[str, Optional[float]] = {}
    for level_id in level_ids:
        try:
            _status(
                "[report]",
                f"Requesting level as time series from CWMS: {level_id}",
                "cyan",
            )
            LOGGER.debug(
                "[report] level request office=%s unit=%s begin=%s end=%s level=%s",
                office,
                unit,
                begin.isoformat() if begin else None,
                end.isoformat() if end else None,
                level_id,
            )
            result = cwms.get_level_as_timeseries(
                begin=begin,
                end=end,
                location_level_id=level_id,
                office_id=office,
                unit=unit,
            )
            payload = getattr(result, "json", None) or {}
            if callable(payload):
                payload = result.json()
            values = (payload or {}).get("values", [])
            out[level_id] = values[-1][1] if values else None
            _status("[report]", f"Received level value for {level_id}", "green")
        except Exception as err:
            LOGGER.warning(
                "%s %s",
                colors.c("[report]", "yellow", bright=True),
                f"Could not fetch level {level_id}: {err}",
            )
            LOGGER.debug("[report] level fetch traceback:\n%s", traceback.format_exc())
            out[level_id] = None
    return out


def location_metadata(project: ProjectSpec, office: str) -> Dict[str, Any]:
    import cwms

    try:
        LOGGER.debug(
            "[report] location metadata request office=%s location=%s",
            office,
            project.location_id,
        )
        location = cwms.get_location(office_id=office, location_id=project.location_id)
        payload = getattr(location, "json", None) or location
        if callable(payload):
            payload = location.json()
        if isinstance(payload, dict):
            data = {**payload}
            if project.href:
                data["href"] = project.href
            return data
    except Exception:
        pass

    return {
        "name": project.location_id,
        "public-name": project.location_id,
        **({"href": project.href} if project.href else {}),
    }
