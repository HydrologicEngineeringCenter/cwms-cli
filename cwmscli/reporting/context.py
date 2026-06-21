import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import click

from cwmscli.reporting.config import Config
from cwmscli.reporting.sources import (
    fetch_level_values,
    fetch_timeseries_df,
    location_metadata,
)
from cwmscli.reporting.utils.date import parse_when
from cwmscli.reporting.values import format_report_value, latest_timeseries_values
from cwmscli.utils import colors

LOGGER = logging.getLogger(__name__)


def _status(label: str, detail: str, color: str = "cyan") -> None:
    LOGGER.info("%s %s", colors.c(label, color, bright=True), detail)


def _expand_template(value: Optional[str], **kwargs) -> Optional[str]:
    if not value:
        return None
    try:
        return value.format(**kwargs)
    except Exception:
        return value


def build_report_table(
    config: Config, begin: Optional[datetime], end: Optional[datetime]
) -> Dict[str, Any]:
    if config.dataset.kind != "table":
        raise click.BadParameter("MVP supports dataset.kind='table' only.")

    rows: List[str] = [project.location_id for project in config.projects]
    if not rows:
        raise click.UsageError("No 'projects' configured in YAML.")
    if not config.columns:
        raise click.UsageError("No 'columns' configured in YAML.")

    project_by_id = {project.location_id: project for project in config.projects}
    tz = config.time_zone or "UTC"
    timeout_seconds = float(config.dataset.options.get("request_timeout_seconds") or 12)

    column_defs: List[Dict[str, Any]] = []
    for column in config.columns:
        if not (column.tsid or column.level):
            raise click.BadParameter(
                f"Column '{column.title}' must have 'tsid' or 'level'."
            )
        column_defs.append(
            {
                "title": column.title,
                "key": column.key,
                "precision": column.precision,
                "unit": column.unit or config.default_unit,
                "office": column.office or config.office,
                "tsid_template": column.tsid,
                "level_template": column.level,
                "href_template": column.href,
                "missing": column.missing or config.missing,
                "undefined": column.undefined or config.undefined,
                "begin_expr": column.begin,
                "end_expr": column.end,
                "align": column.align,
                "width": column.width,
            }
        )

    def effective_range(
        begin_expr: Optional[str], end_expr: Optional[str]
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        begin_eff = parse_when(begin_expr, tz) if begin_expr else begin
        end_eff = parse_when(end_expr, tz) if end_expr else end
        return begin_eff, end_eff

    ts_groups: Dict[tuple, List[str]] = {}
    ts_backrefs: Dict[tuple, List[tuple[str, str]]] = {}
    level_groups: Dict[tuple, List[str]] = {}
    level_backrefs: Dict[tuple, List[tuple[str, str]]] = {}
    candidate_ends: List[datetime] = [dt for dt in [end] if dt is not None]

    for project_id in rows:
        for column in column_defs:
            begin_eff, end_eff = effective_range(
                column.get("begin_expr"), column.get("end_expr")
            )
            if end_eff:
                candidate_ends.append(end_eff)
            group_key = (column["office"], column["unit"], begin_eff, end_eff)
            if column["tsid_template"]:
                tsid = _expand_template(column["tsid_template"], project=project_id)
                if not tsid:
                    continue
                ts_groups.setdefault(group_key, [])
                if tsid not in ts_groups[group_key]:
                    ts_groups[group_key].append(tsid)
                ts_backrefs.setdefault((*group_key, tsid), []).append(
                    (project_id, column["key"])
                )
            elif column["level_template"]:
                level_id = _expand_template(
                    column["level_template"], project=project_id
                )
                if not level_id:
                    continue
                level_groups.setdefault(group_key, [])
                if level_id not in level_groups[group_key]:
                    level_groups[group_key].append(level_id)
                level_backrefs.setdefault((*group_key, level_id), []).append(
                    (project_id, column["key"])
                )

    _status(
        "[report]",
        f"Prepared CWMS requests: {sum(len(v) for v in ts_groups.values())} "
        f"time series across {len(ts_groups)} group(s); "
        f"{sum(len(v) for v in level_groups.values())} level series across "
        f"{len(level_groups)} group(s)",
        "cyan",
    )
    LOGGER.debug("[report] timeseries groups=%s", ts_groups)
    LOGGER.debug("[report] level groups=%s", level_groups)

    latest_ts_values: Dict[tuple, Any] = {}
    for group_index, ((office, unit, begin_eff, end_eff), tsids) in enumerate(
        ts_groups.items(), start=1
    ):
        _status(
            "[report]",
            f"Fetching time series group {group_index}/{len(ts_groups)}",
            "cyan",
        )
        df = fetch_timeseries_df(
            tsids,
            office,
            unit,
            begin_eff,
            end_eff,
            timeout_seconds,
        )
        latest_group_values = latest_timeseries_values(df)
        if latest_group_values:
            for tsid, (value, timestamp) in latest_group_values.items():
                latest_ts_values[(office, unit, begin_eff, end_eff, tsid)] = value
                LOGGER.debug(
                    "[report] selected latest time series value tsid=%s time=%s "
                    "value=%s",
                    tsid,
                    timestamp,
                    value,
                )
            _status(
                "[report]",
                f"Matched latest values for {len(latest_group_values)}/{len(tsids)} "
                f"requested time series in group {group_index}",
                "green" if len(latest_group_values) == len(tsids) else "yellow",
            )
        else:
            LOGGER.warning(
                "%s %s",
                colors.c("[report]", "yellow", bright=True),
                f"No usable rows returned for time series group {group_index}.",
            )

    latest_level_values: Dict[tuple, Any] = {}
    for group_index, ((office, unit, begin_eff, end_eff), levels) in enumerate(
        level_groups.items(), start=1
    ):
        _status(
            "[report]",
            f"Fetching level group {group_index}/{len(level_groups)}",
            "cyan",
        )
        values = fetch_level_values(levels, begin_eff, end_eff, office, unit)
        for level_id in levels:
            latest_level_values[(office, unit, begin_eff, end_eff, level_id)] = (
                values.get(level_id)
            )

    table: Dict[str, Dict[str, Any]] = {project_id: {} for project_id in rows}
    by_key = {column["key"]: column for column in column_defs}

    for (office, unit, begin_eff, end_eff, tsid), pairs in ts_backrefs.items():
        raw = latest_ts_values.get((office, unit, begin_eff, end_eff, tsid))
        if raw is None:
            LOGGER.debug("[report] no matched value for time series %s", tsid)
        for project_id, column_key in pairs:
            column = by_key[column_key]
            text = format_report_value(
                raw,
                column.get("precision"),
                column.get("missing") or config.missing,
                column.get("undefined") or config.undefined,
            )
            href = _expand_template(
                column.get("href_template"),
                project=project_id,
                office=office,
                tsid=tsid,
                level=None,
            )
            table[project_id][column_key] = {
                "text": text,
                **({"href": href} if href else {}),
            }

    for (office, unit, begin_eff, end_eff, level_id), pairs in level_backrefs.items():
        raw = latest_level_values.get((office, unit, begin_eff, end_eff, level_id))
        for project_id, column_key in pairs:
            column = by_key[column_key]
            text = format_report_value(
                raw,
                column.get("precision"),
                column.get("missing") or config.missing,
                column.get("undefined") or config.undefined,
            )
            href = _expand_template(
                column.get("href_template"),
                project=project_id,
                office=office,
                tsid=None,
                level=level_id,
            )
            table[project_id][column_key] = {
                "text": text,
                **({"href": href} if href else {}),
            }

    for project_id in rows:
        project = project_by_id[project_id]
        _status(
            "[report]",
            f"Fetching location metadata for {project_id}",
            "cyan",
        )
        table[project_id]["location"] = location_metadata(
            project, project.office or config.office
        )

    return {
        "columns": column_defs,
        "rows": rows,
        "data": table,
        "base_end": (
            max(candidate_ends) if candidate_ends else datetime.now(timezone.utc)
        ),
    }
