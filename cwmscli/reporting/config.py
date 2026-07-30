import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

import click

from cwmscli.reporting.models import (
    ColumnSpec,
    DatasetSpec,
    HeaderCellSpec,
    LayoutSpec,
    ProjectSpec,
    ReportSpec,
    TableHeaderSpec,
    TemplateSpec,
)


def _parse_header_spec(raw: Optional[Dict[str, Any]]) -> Optional[TableHeaderSpec]:
    if not raw:
        return None

    def to_cell(value: Dict[str, Any]) -> HeaderCellSpec:
        return HeaderCellSpec(
            text=str(value.get("text", "")),
            colspan=int(value.get("colspan", 1) or 1),
            rowspan=int(value.get("rowspan", 1) or 1),
            align=value.get("align"),
            classes=value.get("classes"),
        )

    project_raw = raw.get("project", {}) or {}
    project = to_cell(
        {
            "text": project_raw.get("text", "Project"),
            "rowspan": project_raw.get("rowspan", 1),
            "align": project_raw.get("align"),
            "classes": project_raw.get("classes"),
        }
    )
    rows = [[to_cell(cell) for cell in (row or [])] for row in raw.get("rows", [])]
    return TableHeaderSpec(project=project, rows=rows)


@dataclass
class Config:
    office: str
    cda_api_root: Optional[str] = None
    dataset: DatasetSpec = field(default_factory=DatasetSpec)
    template: TemplateSpec = field(default_factory=TemplateSpec)
    report: Optional[Union[ReportSpec, Dict[str, Any]]] = None
    layout: LayoutSpec = field(default_factory=LayoutSpec)
    projects: List[ProjectSpec] = field(default_factory=list)
    columns: List[ColumnSpec] = field(default_factory=list)
    header: Optional[TableHeaderSpec] = None
    begin: Optional[str] = None
    end: Optional[str] = None
    default_unit: str = "EN"
    missing: str = "----"
    undefined: str = "--NA--"
    time_zone: Optional[str] = None

    @staticmethod
    def from_yaml(path: str) -> "Config":
        import yaml

        with open(path, "r", encoding="utf-8") as file:
            raw = yaml.safe_load(file) or {}

        office = raw.get("office") or os.getenv("OFFICE") or os.getenv("CWMS_OFFICE")
        if not office:
            raise click.BadParameter(
                "Report config must set 'office' or CWMS_OFFICE/OFFICE."
            )

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
            template = TemplateSpec(name=template_block)
        elif isinstance(template_block, dict):
            template = TemplateSpec(
                name=template_block.get("name") or "WM-Daily",
                source=template_block.get("source") or "builtin",
                path=template_block.get("path") or template_block.get("file"),
                options=dict(template_block.get("options") or {}),
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

        layout_block = raw.get("layout") or {}
        if not isinstance(layout_block, dict):
            raise click.BadParameter("Invalid layout configuration.")
        page_block = dict(layout_block.get("page") or {})
        columns_value = layout_block.get("columns") or page_block.get("columns") or 12
        rows_value = layout_block.get("rows") or page_block.get("rows") or 16
        page_block.setdefault("columns", int(columns_value))
        page_block.setdefault("rows", int(rows_value))
        layout = LayoutSpec(
            mode=layout_block.get("mode") or page_block.get("mode") or "flow",
            columns=int(columns_value),
            rows=int(rows_value),
            page=page_block,
            blocks=list(layout_block.get("blocks") or []),
            groups=list(layout_block.get("groups") or []),
            presentation=layout_block.get("presentation"),
            options={
                key: value
                for key, value in layout_block.items()
                if key
                not in {
                    "mode",
                    "columns",
                    "rows",
                    "page",
                    "blocks",
                    "groups",
                    "presentation",
                }
            },
        )

        columns: List[ColumnSpec] = []
        for index, column in enumerate(raw.get("columns", [])):
            columns.append(
                ColumnSpec(
                    title=column.get("title") or column.get("name") or f"Col{index+1}",
                    key=column.get("key") or column.get("title") or f"c{index+1}",
                    tsid=column.get("tsid"),
                    level=column.get("level"),
                    unit=column.get("unit"),
                    precision=column.get("precision"),
                    office=column.get("office"),
                    href=column.get("href"),
                    missing=column.get("missing"),
                    undefined=column.get("undefined"),
                    begin=column.get("begin"),
                    end=column.get("end"),
                    align=column.get("align"),
                    width=(
                        int(column["width"])
                        if column.get("width") is not None
                        else None
                    ),
                )
            )

        projects: List[ProjectSpec] = []
        for project in raw.get("projects", []):
            if isinstance(project, str):
                projects.append(ProjectSpec(location_id=project))
            elif isinstance(project, dict):
                location_id = (
                    project.get("location_id")
                    or project.get("name")
                    or project.get("id")
                )
                if not location_id:
                    raise click.BadParameter(
                        f"Project missing location id: {project!r}"
                    )
                projects.append(
                    ProjectSpec(
                        location_id=location_id,
                        href=project.get("href"),
                        office=project.get("office"),
                    )
                )
            else:
                raise click.BadParameter(f"Invalid project entry: {project!r}")

        header = _parse_header_spec(raw.get("header"))
        if header and header.rows:
            leaf_count = sum(max(1, cell.colspan) for cell in header.rows[-1])
            if leaf_count != len(columns):
                click.echo(
                    f"[reporting] Warning: header leaf-count ({leaf_count}) "
                    f"!= number of data columns ({len(columns)}).",
                    err=True,
                )

        return Config(
            office=office,
            cda_api_root=raw.get("cda_api_root") or os.getenv("CDA_API_ROOT"),
            dataset=dataset,
            template=template,
            report=report,
            layout=layout,
            projects=projects,
            columns=columns,
            header=header,
            begin=raw.get("begin"),
            end=raw.get("end"),
            default_unit=raw.get("default_unit") or "EN",
            missing=raw.get("missing") or "----",
            undefined=raw.get("undefined") or "--NA--",
            time_zone=raw.get("time_zone"),
        )
