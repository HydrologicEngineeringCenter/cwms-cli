import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import click

from cwmscli.reporting.models import (
    ColumnSpec,
    DatasetSpec,
    EngineSpec,
    HeaderCellSpec,
    ProjectSpec,
    ReportSpec,
    TableHeaderSpec,
    TemplateSpec,
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
    engine: EngineSpec = field(default_factory=EngineSpec)
    dataset: DatasetSpec = field(default_factory=DatasetSpec)
    template: TemplateSpec = field(default_factory=TemplateSpec)
    report: ReportSpec | Dict[str, Any] | None = None
    projects: List[ProjectSpec] = field(default_factory=list)
    columns: List[ColumnSpec] = field(default_factory=list)
    header: Optional[TableHeaderSpec] = None
    begin: Optional[str] = None
    end: Optional[str] = None
    time_epsilon_minutes: int = 5
    default_unit: str = "EN"
    missing: str = "----"
    undefined: str = "--NA--"
    time_zone: Optional[str] = None  # i.e. "America/Chicago"

    @staticmethod
    def from_yaml(path: str) -> "Config":
        import yaml

        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        office = (
            raw.get("office")
            or os.getenv("OFFICE")
            or os.getenv("CWMS_OFFICE")
            or "SWT"
        )

        engine_block = raw.get("engine") or {}
        if isinstance(engine_block, str):
            engine = EngineSpec(name=engine_block)
        elif isinstance(engine_block, dict):
            default_engine_name = (
                "jinja2"
                if engine_block.get("template") or engine_block.get("template_dir")
                else "text"
            )
            engine = EngineSpec(
                name=engine_block.get("name") or default_engine_name,
                template=engine_block.get("template"),
                template_dir=engine_block.get("template_dir"),
                options=dict(engine_block.get("options") or {}),
            )
        else:
            raise click.BadParameter("Invalid engine configuration.")

        dataset_block = raw.get("dataset") or {}
        if isinstance(dataset_block, str):
            dataset = DatasetSpec(kind=dataset_block)
        elif isinstance(dataset_block, dict):
            dataset = DatasetSpec(
                kind=dataset_block.get("kind") or "table",
                options={k: v for k, v in dataset_block.items() if k != "kind"},
            )
        else:
            raise click.BadParameter("Invalid dataset configuration.")

        template_block = raw.get("template") or {}
        if isinstance(template_block, str):
            template = TemplateSpec(kind=template_block)
        elif isinstance(template_block, dict):
            template = TemplateSpec(
                kind=template_block.get("kind") or "default",
                options={k: v for k, v in template_block.items() if k != "kind"},
            )
        else:
            raise click.BadParameter("Invalid template configuration.")

        report_block = raw.get("report") or {}
        report = ReportSpec(
            district=report_block.get("district", office),
            name=report_block.get("name", "Daily Report"),
            logo_left=report_block.get("logo_left"),
            logo_right=report_block.get("logo_right"),
            title_lines=list(report_block.get("title_lines") or []),
            footer_lines=list(report_block.get("footer_lines") or []),
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
                    begin=c.get("begin"),
                    end=c.get("end"),
                    align=c.get("align"),
                    width=int(c["width"]) if c.get("width") is not None else None,
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
            engine=engine,
            dataset=dataset,
            template=template,
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
