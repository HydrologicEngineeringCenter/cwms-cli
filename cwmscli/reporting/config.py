import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import click
import yaml

from cwmscli.reporting.models import (
    ColumnSpec,
    HeaderCellSpec,
    ProjectSpec,
    ReportSpec,
    TableHeaderSpec,
)


def _parse_header_spec(raw: Optional[Dict[str, Any]]) -> Optional["TableHeaderSpec"]:
    if not raw:
        return None

    def to_cell(d: Dict[str, Any]) -> HeaderCellSpec:
        return HeaderCellSpec(
            text=str(d.get("text", "")),
            colspan=int(d.get("colspan", 1) or 1),
            rowspan=int(d.get("rowspan", 1) or 1),
            align=d.get("align"),
            classes=d.get("classes"),
        )

    proj_raw = raw.get("project", {}) or {}
    project = to_cell(
        {
            "text": proj_raw.get("text", "Project"),
            "rowspan": proj_raw.get("rowspan", 1),
            "align": proj_raw.get("align"),
            "classes": proj_raw.get("classes"),
        }
    )
    rows_raw = raw.get("rows", []) or []
    rows = []
    for r in rows_raw:
        row_cells = [to_cell(c) for c in (r or [])]
        rows.append(row_cells)
    return TableHeaderSpec(project=project, rows=rows)


@dataclass
class Config:
    office: str
    cda_api_root: Optional[str] = None
    report: ReportSpec | Dict[str, Any] | None = None
    projects: List[ProjectSpec] = field(default_factory=list)
    columns: List[ColumnSpec] = field(default_factory=list)
    header: Optional[TableHeaderSpec] = None

    # REQUIRED in YAML now
    begin: Optional[str] = None
    end: Optional[str] = None

    # target_time removed (global)
    time_epsilon_minutes: int = 5  # kept, in case you want windowing later

    default_unit: str = "EN"
    missing: str = "----"
    undefined: str = "--NA--"
    time_zone: Optional[str] = None  # e.g., "America/Chicago"

    @staticmethod
    def from_yaml(path: str) -> "Config":
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        office = (
            raw.get("office")
            or os.getenv("OFFICE")
            or os.getenv("CWMS_OFFICE")
            or "SWT"
        )

        report_block = raw.get("report") or {}
        report = ReportSpec(
            district=report_block.get("district", office),
            name=report_block.get("name", "Daily Report"),
            logo_left=report_block.get("logo_left"),
            logo_right=report_block.get("logo_right"),
        )

        cols: List[ColumnSpec] = []
        for i, c in enumerate(raw.get("columns", [])):
            cols.append(
                ColumnSpec(
                    title=c.get("title") or c.get("name") or f"Col{i+1}",
                    key=c.get("key") or c.get("title") or f"c{i+1}",
                    tsid=c.get("tsid"),
                    level=c.get("level"),
                    unit=c.get("unit"),
                    precision=c.get("precision"),
                    office=c.get("office"),
                    location_id=c.get("location_id"),
                    href=c.get("href"),
                    missing=c.get("missing"),
                    undefined=c.get("undefined"),
                )
            )

        projects_raw = raw.get("projects", [])
        projects: List[ProjectSpec] = []
        for p in projects_raw:
            if isinstance(p, str):
                projects.append(ProjectSpec(location_id=p))
            elif isinstance(p, dict):
                projects.append(
                    ProjectSpec(
                        location_id=p.get("location_id")
                        or p.get("name")
                        or p.get("id"),
                        href=p.get("href"),
                        office=p.get("office"),
                    )
                )
            else:
                raise click.BadParameter(f"Invalid project entry: {p!r}")

        header = _parse_header_spec(raw.get("header"))
        if header and header.rows:
            # compute leaf-count in the final header row
            leaf_count = sum(max(1, c.colspan) for c in header.rows[-1])
            if leaf_count != len(cols):
                click.echo(
                    f"[reporting] Warning: header leaf-count ({leaf_count}) != number of data columns ({len(cols)}).",
                    err=True,
                )

        return Config(
            office=office,
            cda_api_root=raw.get("cda_api_root") or os.getenv("CDA_API_ROOT"),
            report=report,
            projects=projects,
            columns=cols,
            begin=raw.get("begin"),
            end=raw.get("end"),
            time_epsilon_minutes=int(raw.get("time_epsilon_minutes") or 5),
            default_unit=raw.get("default_unit") or "EN",
            missing=raw.get("missing") or "----",
            undefined=raw.get("undefined") or "--NA--",
            time_zone=raw.get("time_zone"),
            header=header,
        )
