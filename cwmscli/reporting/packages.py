from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import click

PACKAGE_MANIFEST_NAMES = (
    "report-package.yaml",
    "report-package.yml",
    "package.yaml",
    "package.yml",
)


@dataclass
class ReportPackage:
    root: Path
    manifest_path: Path
    manifest: Dict[str, Any] = field(default_factory=dict)
    selected_report: Optional[str] = None

    @property
    def entrypoint(self) -> Dict[str, Any]:
        reports = self.manifest.get("reports") or {}
        if reports:
            selected = (
                self.selected_report
                or self.manifest.get("default_report")
                or self.manifest.get("default-report")
            )
            if not selected:
                if len(reports) == 1:
                    selected = next(iter(reports))
                else:
                    available = ", ".join(sorted(reports))
                    raise click.BadParameter(
                        "Report package contains multiple reports. Select one with "
                        f"--report. Available: {available}"
                    )
            if selected not in reports:
                available = ", ".join(sorted(reports))
                raise click.BadParameter(
                    f"Unknown package report '{selected}'. Available: {available}"
                )
            entrypoint = reports[selected] or {}
            if not isinstance(entrypoint, dict):
                raise click.BadParameter(
                    f"Package report '{selected}' must be a mapping."
                )
            return entrypoint
        return self.manifest.get("entrypoint") or {}

    @property
    def config_path(self) -> Path:
        entrypoint = self.entrypoint
        configured = entrypoint.get("config") or self.manifest.get("config")
        if not configured:
            configured = "report.yaml"
        return self.resolve_path(configured)

    def template_path(self, output_format: str) -> Optional[Path]:
        entrypoint = self.entrypoint
        templates = entrypoint.get("templates") or self.manifest.get("templates") or {}
        configured = templates.get(output_format.lower())
        if not configured and output_format.lower() == "text":
            configured = templates.get("txt")
        return self.resolve_path(configured) if configured else None

    def resolve_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return self.root / path


def load_report_package(
    package_path: str, *, report_name: Optional[str] = None
) -> ReportPackage:
    import yaml

    root = Path(package_path).resolve()
    if not root.exists() or not root.is_dir():
        raise click.BadParameter(f"Report package must be a directory: {package_path}")

    manifest_path = next(
        (root / name for name in PACKAGE_MANIFEST_NAMES if (root / name).exists()),
        None,
    )
    if manifest_path is None:
        names = ", ".join(PACKAGE_MANIFEST_NAMES)
        raise click.BadParameter(
            f"Report package {root} is missing a manifest. Expected one of: {names}"
        )

    with open(manifest_path, "r", encoding="utf-8") as file:
        manifest = yaml.safe_load(file) or {}

    package = ReportPackage(
        root=root,
        manifest_path=manifest_path,
        manifest=manifest,
        selected_report=report_name,
    )
    if not package.config_path.exists():
        raise click.BadParameter(
            f"Report package config does not exist: {package.config_path}"
        )
    return package
