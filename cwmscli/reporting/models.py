from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ProjectSpec:
    location_id: str
    href: Optional[str] = None
    office: Optional[str] = None


@dataclass
class ReportSpec:
    district: str
    name: str
    logo_left: Optional[str] = None
    logo_right: Optional[str] = None


@dataclass
class HeaderCellSpec:
    text: str
    colspan: int = 1
    rowspan: int = 1
    align: Optional[str] = None
    classes: Optional[str] = None


@dataclass
class TableHeaderSpec:
    project: HeaderCellSpec = field(
        default_factory=lambda: HeaderCellSpec(text="Project", rowspan=1)
    )
    rows: List[List[HeaderCellSpec]] = field(default_factory=list)


@dataclass
class ColumnSpec:
    title: str
    key: str
    tsid: Optional[str] = None
    level: Optional[str] = None
    unit: Optional[str] = None
    precision: Optional[int] = None
    office: Optional[str] = None
    location_id: Optional[str] = None
    href: Optional[str] = None
    missing: Optional[str] = None
    undefined: Optional[str] = None
