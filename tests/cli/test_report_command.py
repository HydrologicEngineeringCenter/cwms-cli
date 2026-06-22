import importlib.metadata
import math
import shutil
import sys
import types
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional
from zoneinfo import ZoneInfo

import pytest
from click.testing import CliRunner

from cwmscli.__main__ import cli
from cwmscli.reporting.config import Config
from cwmscli.reporting.timeseries import _format_float, _format_int
from cwmscli.utils import colors

EXAMPLES_DIR = Path("cwmscli") / "reporting" / "examples"


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def workspace_tmpdir():
    path = Path.cwd() / ".tmp_pytest_report" / str(uuid.uuid4())
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def fake_cwms(monkeypatch):
    module = types.SimpleNamespace()
    api_module = types.SimpleNamespace()
    api_module.SESSION = types.SimpleNamespace(
        base_url="https://cwms-data.usace.army.mil/cwms-data/",
        headers={},
    )

    def init_session(api_root=None):
        return None

    def get_multi_timeseries_df(ts_ids, office_id, unit, begin, end, melted):
        import pandas as pd

        rows = []
        tzinfo = ZoneInfo("UTC")
        begin = begin or datetime(2026, 1, 1, tzinfo=tzinfo)
        end = end or begin
        if begin.tzinfo is None:
            begin = begin.replace(tzinfo=tzinfo)
        if end.tzinfo is None:
            end = end.replace(tzinfo=tzinfo)

        for ts_id in ts_ids:
            current = begin
            index = 0
            while current <= end:
                value = 722.34 if ts_id.startswith("KEYS.") else 700.0 + index
                rows.append(
                    {
                        "ts_id": ts_id,
                        "date-time": current.astimezone(tzinfo).isoformat(),
                        "value": value,
                    }
                )
                current += timedelta(hours=1)
                index += 1

        return pd.DataFrame(rows)

    def get_level_as_timeseries(begin, end, location_level_id, office_id, unit):
        class LevelResult:
            def json(self):
                return {"values": [[0, 725.0]]}

        return LevelResult()

    def get_location(office_id, location_id):
        return {
            "public-name": f"{location_id} Lake",
            "href": f"https://www.swt-wc.usace.army.mil/{location_id}.lakepage.html",
        }

    module.init_session = init_session
    module.get_multi_timeseries_df = get_multi_timeseries_df
    module.get_level_as_timeseries = get_level_as_timeseries
    module.get_location = get_location
    module.api = api_module
    monkeypatch.setitem(sys.modules, "cwms", module)
    monkeypatch.setitem(sys.modules, "cwms.api", api_module)

    class FakeResponse:
        status_code = 200

        def __init__(self, tsid):
            self.tsid = tsid

        def raise_for_status(self):
            return None

        def json(self):
            value = 722.34 if self.tsid.startswith("KEYS.") else 700.0
            start_ms = int(
                datetime(2026, 1, 1, 0, tzinfo=timezone.utc).timestamp() * 1000
            )
            return {
                "units": "ft",
                "values": [
                    [start_ms, value - 1, 0],
                    [start_ms + 3600000, value, 0],
                ],
            }

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, params, headers, timeout):
            return FakeResponse(params["name"])

    monkeypatch.setattr("cwmscli.reporting.sources.requests.Session", FakeSession)
    versions = {
        "cwms-python": "1.0.7",
        "PyYAML": "6.0.2",
        "pandas": "2.1.3",
        "Jinja2": "3.1.6",
    }
    monkeypatch.setattr(
        importlib.metadata,
        "version",
        lambda package: versions.get(package, "99.0.0"),
    )
    return module


def _write_minimal_config(
    path: Path, template_block: Optional[List[str]] = None
) -> None:
    lines = [
        "office: MVD",
        "cda_api_root: https://cwms-data.usace.army.mil/cwms-data",
        'begin: "2026-01-01T00:00:00Z"',
        'end: "2026-01-01T01:00:00Z"',
        "report:",
        '  district: "Example District"',
        '  name: "Daily Reservoir Report"',
        "projects:",
        '  - "KEYS"',
        "columns:",
        "  - title: Pool Elev",
        "    key: elev",
        '    tsid: "{project}.Elev.Inst.1Hour.0.Ccp-Rev"',
        "    precision: 2",
    ]
    if template_block:
        insert_at = lines.index("report:")
        lines[insert_at:insert_at] = template_block
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_time_series_config(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "office: MVD",
                "cda_api_root: https://cwms-data.usace.army.mil/cwms-data",
                "time_zone: America/Chicago",
                "dataset:",
                "  kind: time_series",
                "  project: KEYS",
                "  title: Example Lake",
                '  month: "2026-05"',
                "  series:",
                "    stage:",
                '      tsid: "{project}.Stage.Inst.1Hour.0.Raw"',
                "      unit: ft",
                "report:",
                '  district: "Example District"',
                '  name: "Monthly Series Report"',
            ]
        ),
        encoding="utf-8",
    )


def test_report_config_parses_template_and_columns(workspace_tmpdir):
    config_path = workspace_tmpdir / "report.yaml"
    _write_minimal_config(
        config_path,
        [
            "template:",
            "  name: WM-Daily",
            "  source: builtin",
        ],
    )

    config = Config.from_yaml(str(config_path))

    assert config.office == "MVD"
    assert config.template.name == "WM-Daily"
    assert config.dataset.kind == "table"
    assert config.columns[0].begin is None
    assert config.columns[0].tsid == "{project}.Elev.Inst.1Hour.0.Ccp-Rev"


def test_report_generate_html_uses_builtin_template(
    runner, workspace_tmpdir, fake_cwms
):
    config_path = workspace_tmpdir / "report.yaml"
    out_path = workspace_tmpdir / "report.html"
    _write_minimal_config(config_path)

    result = runner.invoke(
        cli,
        ["report", "generate", "--config", str(config_path), "--out", str(out_path)],
    )

    assert result.exit_code == 0, result.output
    assert "[report] Loading config:" in result.output
    assert "[report] Fetching CWMS data and shaping report context" in result.output
    assert "[report] Rendering HTML with built-in template WM-Daily" in result.output
    assert "[report] Wrote" in result.output
    html = out_path.read_text(encoding="utf-8")
    assert "Example District" in html
    assert "Daily Reservoir Report" in html
    assert "KEYS Lake" in html
    assert "722.34" in html


def test_report_generate_accepts_report_package(runner, workspace_tmpdir, fake_cwms):
    package_path = workspace_tmpdir / "daily-package"
    package_path.mkdir()
    config_path = package_path / "report.yaml"
    out_path = workspace_tmpdir / "report.html"
    _write_minimal_config(config_path)
    (package_path / "report-package.yaml").write_text(
        "\n".join(
            [
                "schema: https://wmes.usace.army.mil/report-package/v1",
                "name: example-daily",
                "version: 0.1.0",
                "entrypoint:",
                "  config: report.yaml",
                "outputs:",
                "  - html",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        cli,
        ["report", "generate", "--package", str(package_path), "--out", str(out_path)],
    )

    assert result.exit_code == 0, result.output
    assert "[report] Loading package: example-daily" in result.output
    assert "[report] Loading config:" in result.output
    html = out_path.read_text(encoding="utf-8")
    assert "Daily Reservoir Report" in html
    assert "KEYS Lake" in html


def test_report_generate_accepts_package_yml_manifest(
    runner, workspace_tmpdir, fake_cwms
):
    package_path = workspace_tmpdir / "daily-package"
    package_path.mkdir()
    config_path = package_path / "report.yaml"
    out_path = workspace_tmpdir / "report.html"
    _write_minimal_config(config_path)
    (package_path / "package.yml").write_text(
        "\n".join(
            [
                "schema: https://wmes.usace.army.mil/report-package/v1",
                "name: example-daily",
                "version: 0.1.0",
                "entrypoint:",
                "  config: report.yaml",
                "outputs:",
                "  - html",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        cli,
        ["report", "generate", "--package", str(package_path), "--out", str(out_path)],
    )

    assert result.exit_code == 0, result.output
    assert "[report] Loading package: example-daily" in result.output
    html = out_path.read_text(encoding="utf-8")
    assert "Daily Reservoir Report" in html
    assert "KEYS Lake" in html


def test_report_generate_accepts_named_report_package_entry(
    runner, workspace_tmpdir, fake_cwms
):
    package_path = workspace_tmpdir / "named-package"
    package_path.mkdir()
    config_path = package_path / "daily.yaml"
    out_path = workspace_tmpdir / "report.html"
    _write_minimal_config(config_path)
    (package_path / "report-package.yaml").write_text(
        "\n".join(
            [
                "schema: https://wmes.usace.army.mil/report-package/v1",
                "name: example-reports",
                "version: 0.1.0",
                "reports:",
                "  daily:",
                "    config: daily.yaml",
                "    outputs:",
                "      - html",
                "  monthly:",
                "    config: missing.yaml",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        cli,
        [
            "report",
            "generate",
            "--package",
            str(package_path),
            "--report",
            "daily",
            "--out",
            str(out_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Daily Reservoir Report" in out_path.read_text(encoding="utf-8")


def test_report_generate_uses_package_relative_text_template(
    runner, workspace_tmpdir, fake_cwms
):
    package_path = workspace_tmpdir / "text-package"
    template_dir = package_path / "templates"
    template_dir.mkdir(parents=True)
    config_path = package_path / "report.yaml"
    out_path = workspace_tmpdir / "report.txt"
    _write_minimal_config(config_path)
    (template_dir / "report.txt.j2").write_text(
        "PACKAGE {{ report.name }} {{ rows[0] }} {{ data[rows[0]].elev.text }}\n",
        encoding="utf-8",
    )
    (package_path / "report-package.yaml").write_text(
        "\n".join(
            [
                "schema: https://wmes.usace.army.mil/report-package/v1",
                "name: example-text",
                "version: 0.1.0",
                "entrypoint:",
                "  config: report.yaml",
                "  templates:",
                "    text: templates/report.txt.j2",
                "outputs:",
                "  - text",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        cli,
        [
            "report",
            "generate",
            "--package",
            str(package_path),
            "--format",
            "text",
            "--out",
            str(out_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Rendering text with user template file" in result.output
    assert "templates" in result.output
    assert out_path.read_text(encoding="utf-8") == (
        "PACKAGE Daily Reservoir Report KEYS 722.34\n"
    )


def test_report_package_template_uses_custom_dataset_fields_and_helpers(
    runner, workspace_tmpdir, fake_cwms, monkeypatch
):
    import pandas as pd

    def fake_fetch_timeseries_df(
        tsids, office, unit, begin, end, timeout_seconds, retry_count=3
    ):
        return pd.DataFrame(
            [
                {
                    "ts_id": tsids[0],
                    "date-time": begin,
                    "value": 100.0,
                    "units": unit,
                },
                {
                    "ts_id": tsids[0],
                    "date-time": begin + timedelta(days=1),
                    "value": 250.0,
                    "units": unit,
                },
            ]
        )

    monkeypatch.setattr(
        "cwmscli.reporting.timeseries.fetch_timeseries_df",
        fake_fetch_timeseries_df,
    )
    package_path = workspace_tmpdir / "custom-monthly-package"
    template_dir = package_path / "templates"
    template_dir.mkdir(parents=True)
    out_path = workspace_tmpdir / "custom_report.txt"
    (package_path / "report-package.yaml").write_text(
        "\n".join(
            [
                "name: custom-monthly-package",
                "entrypoint:",
                "  config: report.yaml",
                "  templates:",
                "    text: templates/report.txt.j2",
            ]
        ),
        encoding="utf-8",
    )
    (package_path / "report.yaml").write_text(
        "\n".join(
            [
                "office: SWT",
                "cda_api_root: https://cwms-data.usace.army.mil/cwms-data",
                "time_zone: UTC",
                "dataset:",
                "  kind: time_series",
                "  project: KEYS",
                '  month: "2026-05"',
                "  water_supply:",
                "    withdrawn_acft: 12345",
                "  hydropower:",
                "    powerhouse: Keystone",
                "  series:",
                "    release:",
                '      tsid: "{project}.Flow-Res Out.Ave.~1Day.1Day.Rev-Regi-Flowgroup"',
                "      unit: cfs",
                "report:",
                '  district: "Tulsa District"',
                '  name: "Custom Monthly Report"',
            ]
        ),
        encoding="utf-8",
    )
    (template_dir / "report.txt.j2").write_text(
        "project={{ project }} "
        "ws={{ options.water_supply.withdrawn_acft }} "
        "powerhouse={{ options.hydropower.powerhouse }} "
        "release_total={{ round_int(sum_values('release')) }}",
        encoding="utf-8",
    )

    result = runner.invoke(
        cli,
        [
            "report",
            "generate",
            "--package",
            str(package_path),
            "--format",
            "text",
            "--out",
            str(out_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert out_path.read_text(encoding="utf-8") == (
        "project=KEYS ws=12345 powerhouse=Keystone release_total=350"
    )


def test_report_package_with_multiple_reports_requires_selection(
    runner, workspace_tmpdir, fake_cwms
):
    package_path = workspace_tmpdir / "multi-package"
    package_path.mkdir()
    _write_minimal_config(package_path / "daily.yaml")
    (package_path / "report-package.yaml").write_text(
        "\n".join(
            [
                "name: example-reports",
                "reports:",
                "  daily:",
                "    config: daily.yaml",
                "  monthly:",
                "    config: daily.yaml",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(cli, ["report", "generate", "--package", str(package_path)])

    assert result.exit_code != 0
    assert "Select one with --report" in result.output


def test_report_packages_inspect_lists_named_reports(runner, workspace_tmpdir):
    package_path = workspace_tmpdir / "named-package"
    package_path.mkdir()
    (package_path / "report-package.yaml").write_text(
        "\n".join(
            [
                "name: example-reports",
                "version: 0.1.0",
                "default_report: monthly",
                "reports:",
                "  daily:",
                "    config: daily.yaml",
                "    outputs:",
                "      - html",
                "    description: Daily web report",
                "  monthly:",
                "    config: monthly.yaml",
                "    outputs:",
                "      - text",
                "      - web",
                "    description: Monthly lake report",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        cli, ["report", "packages", "inspect", "--package", str(package_path)]
    )

    assert result.exit_code == 0, result.output
    assert "Package: example-reports" in result.output
    assert "Version: 0.1.0" in result.output
    assert "Default report: monthly" in result.output
    assert "daily" in result.output
    assert "daily.yaml" in result.output
    assert "html" in result.output
    assert "monthly" in result.output
    assert "monthly.yaml" in result.output
    assert "text, web" in result.output


def test_report_packages_inspect_lists_single_entrypoint(runner, workspace_tmpdir):
    package_path = workspace_tmpdir / "single-package"
    package_path.mkdir()
    (package_path / "report-package.yaml").write_text(
        "\n".join(
            [
                "name: example-daily",
                "description: Example package",
                "entrypoint:",
                "  config: report.yaml",
                "outputs:",
                "  - html",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        cli, ["report", "packages", "inspect", "--package", str(package_path)]
    )

    assert result.exit_code == 0, result.output
    assert "Package: example-daily" in result.output
    assert "example-daily" in result.output
    assert "report.yaml" in result.output
    assert "html" in result.output
    assert "Example package" in result.output


def test_report_example_wm_daily_swt_generates_with_fake_cwms(
    runner, workspace_tmpdir, fake_cwms
):
    config_path = EXAMPLES_DIR / "wm_daily_swt.yaml"
    out_path = workspace_tmpdir / "wm_daily_swt.html"

    result = runner.invoke(
        cli,
        ["report", "generate", "--config", str(config_path), "--out", str(out_path)],
    )

    assert result.exit_code == 0, result.output
    html = out_path.read_text(encoding="utf-8")
    assert "Tulsa District" in html
    assert "WM Daily Reservoir Report" in html
    assert "KEYS Lake" in html
    assert "OOLO Lake" in html
    assert "SKIA Lake" in html
    assert "https://www.swt-wc.usace.army.mil/KEYS.lakepage.html" in html


def test_report_time_series_config_generates_text_with_template(
    runner, workspace_tmpdir, fake_cwms, monkeypatch
):
    import pandas as pd

    def fake_fetch_timeseries_df(
        tsids, office, unit, begin, end, timeout_seconds, retry_count=3
    ):
        rows = []
        value_by_unit = {
            "ft": 725.25,
            "ac-ft": 450000,
            "cfs": 1000,
            "in": 0.10,
        }
        for tsid in tsids:
            current = begin
            while current <= end:
                rows.append(
                    {
                        "ts_id": tsid,
                        "date-time": current,
                        "value": value_by_unit[unit],
                        "units": unit,
                    }
                )
                current += timedelta(hours=1)
        return pd.DataFrame(rows)

    monkeypatch.setattr(
        "cwmscli.reporting.timeseries.fetch_timeseries_df",
        fake_fetch_timeseries_df,
    )
    config_path = workspace_tmpdir / "time_series.yaml"
    template_path = workspace_tmpdir / "time_series.txt.j2"
    out_path = workspace_tmpdir / "time_series.txt"
    _write_time_series_config(config_path)
    template_path.write_text(
        "{{ options.title }} {{ month.label }} "
        "value={{ fmt_float(value_at('stage', month.start), 2) }}",
        encoding="utf-8",
    )

    result = runner.invoke(
        cli,
        [
            "report",
            "generate",
            "--config",
            str(config_path),
            "--format",
            "text",
            "--template-file",
            str(template_path),
            "--out",
            str(out_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert (
        f"[report] Rendering text with user template file {template_path}"
        in result.output
    )
    text = out_path.read_text(encoding="utf-8", newline="")
    assert text == "Example Lake MAY 2026 value=725.25"


def test_report_generate_accepts_dataset_overrides(
    runner, workspace_tmpdir, fake_cwms, monkeypatch
):
    import pandas as pd

    captured = []

    def fake_fetch_timeseries_df(
        tsids, office, unit, begin, end, timeout_seconds, retry_count=3
    ):
        captured.append((tsids[0], begin, end))
        rows = []
        value_by_unit = {
            "ft": 725.25,
            "ac-ft": 450000,
            "cfs": 1000,
            "in": 0.10,
        }
        current = begin
        while current <= end:
            rows.append(
                {
                    "ts_id": tsids[0],
                    "date-time": current,
                    "value": value_by_unit[unit],
                    "units": unit,
                }
            )
            current += timedelta(hours=1)
        return pd.DataFrame(rows)

    monkeypatch.setattr(
        "cwmscli.reporting.timeseries.fetch_timeseries_df",
        fake_fetch_timeseries_df,
    )
    config_path = workspace_tmpdir / "time_series.yaml"
    template_path = workspace_tmpdir / "time_series.txt.j2"
    out_path = workspace_tmpdir / "series_override.txt"
    _write_time_series_config(config_path)
    template_path.write_text(
        "{{ options.title }} {{ month.abbr }} {{ month.start.year }}",
        encoding="utf-8",
    )

    result = runner.invoke(
        cli,
        [
            "report",
            "generate",
            "--config",
            str(config_path),
            "--format",
            "text",
            "--template-file",
            str(template_path),
            "--set",
            "dataset.project=ELDR",
            "--set",
            "dataset.title=El Dorado Lake",
            "--set",
            "dataset.month=2026-04",
            "--out",
            str(out_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Applying 3 config override(s)" in result.output
    text = out_path.read_text(encoding="utf-8", newline="")
    assert text == "El Dorado Lake APR 2026"
    assert captured[0][0] == "ELDR.Stage.Inst.1Hour.0.Raw"
    assert captured[0][1].isoformat() == "2026-03-31T00:00:00-05:00"
    assert captured[0][2].isoformat() == "2026-05-02T00:00:00-05:00"


def test_report_generate_accepts_escaped_nested_dataset_overrides(
    runner, workspace_tmpdir, fake_cwms
):
    config_path = workspace_tmpdir / "time_series.yaml"
    template_path = workspace_tmpdir / "time_series.txt.j2"
    out_path = workspace_tmpdir / "series_override.txt"
    _write_time_series_config(config_path)
    template_path.write_text(
        "{{ options.report_overrides['2026-05'].summary.max_storage }}",
        encoding="utf-8",
    )

    result = runner.invoke(
        cli,
        [
            "report",
            "generate",
            "--config",
            str(config_path),
            "--format",
            "text",
            "--template-file",
            str(template_path),
            "--set",
            'dataset.report_overrides={\\"2026-05\\":{\\"summary\\":{\\"max_storage\\":31612}}}',
            "--out",
            str(out_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert out_path.read_text(encoding="utf-8", newline="") == "31612"


def test_report_generate_accepts_shell_stripped_nested_dataset_overrides(
    runner, workspace_tmpdir, fake_cwms
):
    config_path = workspace_tmpdir / "time_series.yaml"
    template_path = workspace_tmpdir / "time_series.txt.j2"
    out_path = workspace_tmpdir / "series_override.txt"
    _write_time_series_config(config_path)
    template_path.write_text(
        "{{ options.report_overrides['2026-05'].daily['14'].power_release }}",
        encoding="utf-8",
    )

    result = runner.invoke(
        cli,
        [
            "report",
            "generate",
            "--config",
            str(config_path),
            "--format",
            "text",
            "--template-file",
            str(template_path),
            "--set",
            "dataset.report_overrides={2026-05:{daily:{14:{power_release:6313}}}}",
            "--out",
            str(out_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert out_path.read_text(encoding="utf-8", newline="") == "6313"


def test_report_template_supports_series_arithmetic_helpers(
    runner, workspace_tmpdir, fake_cwms, monkeypatch
):
    import pandas as pd

    def fake_fetch_timeseries_df(
        tsids, office, unit, begin, end, timeout_seconds, retry_count=3
    ):
        return pd.DataFrame(
            [
                {
                    "ts_id": tsids[0],
                    "date-time": begin,
                    "value": 10.0,
                    "units": unit,
                },
                {
                    "ts_id": tsids[0],
                    "date-time": begin + timedelta(days=1),
                    "value": 20.0,
                    "units": unit,
                },
                {
                    "ts_id": tsids[0],
                    "date-time": begin + timedelta(days=2),
                    "value": None,
                    "units": unit,
                },
            ]
        )

    monkeypatch.setattr(
        "cwmscli.reporting.timeseries.fetch_timeseries_df",
        fake_fetch_timeseries_df,
    )
    config_path = workspace_tmpdir / "arithmetic.yaml"
    template_path = workspace_tmpdir / "arithmetic.txt.j2"
    out_path = workspace_tmpdir / "arithmetic.txt"
    config_path.write_text(
        "\n".join(
            [
                "office: SWT",
                "cda_api_root: https://cwms-data.usace.army.mil/cwms-data",
                "time_zone: UTC",
                "dataset:",
                "  kind: time_series",
                "  project: KEYS",
                '  month: "2026-05"',
                "  series:",
                "    inflow:",
                '      tsid: "{project}.Flow-Res In.Ave.~1Day.1Day.Regi-Rev-Adjusted"',
                "      unit: cfs",
                "report:",
                '  district: "Tulsa District"',
                '  name: "Arithmetic Report"',
            ]
        ),
        encoding="utf-8",
    )
    template_path.write_text(
        "sum={{ round_int(sum_values('inflow')) }} "
        "count={{ count_values('inflow') }} "
        "avg={{ round_int(avg_values('inflow')) }} "
        "min={{ round_int(min_row('inflow').value) }} "
        "max={{ round_int(max_row('inflow').value) }} "
        "max_day={{ report_day(max_row('inflow')['date-time'], month.start) }}",
        encoding="utf-8",
    )

    result = runner.invoke(
        cli,
        [
            "report",
            "generate",
            "--config",
            str(config_path),
            "--format",
            "text",
            "--template-file",
            str(template_path),
            "--out",
            str(out_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert out_path.read_text(encoding="utf-8") == (
        "sum=30 count=2 avg=15 min=10 max=20 max_day=1"
    )


def test_report_formatters_treat_nan_and_infinity_as_missing():
    assert _format_float(math.nan, 2) == "--"
    assert _format_float(math.inf, 2) == "--"
    assert _format_int(math.nan) == "--"
    assert _format_int(math.inf) == "--"


def test_report_generate_text_output(runner, workspace_tmpdir, fake_cwms):
    config_path = workspace_tmpdir / "report.yaml"
    out_path = workspace_tmpdir / "report.txt"
    _write_minimal_config(config_path)

    result = runner.invoke(
        cli,
        [
            "report",
            "generate",
            "--config",
            str(config_path),
            "--format",
            "text",
            "--out",
            str(out_path),
        ],
    )

    assert result.exit_code == 0, result.output
    text = out_path.read_text(encoding="utf-8")
    assert "Example District" in text
    assert "KEYS Lake" in text
    assert "722.34" in text


def test_report_generate_supports_level_column(runner, workspace_tmpdir, fake_cwms):
    config_path = workspace_tmpdir / "report.yaml"
    out_path = workspace_tmpdir / "report.html"
    lines = [
        "office: MVD",
        "cda_api_root: https://cwms-data.usace.army.mil/cwms-data",
        'begin: "2026-01-01T00:00:00Z"',
        'end: "2026-01-01T01:00:00Z"',
        "report:",
        '  district: "Example District"',
        '  name: "Daily Reservoir Report"',
        "projects:",
        '  - "KEYS"',
        "columns:",
        "  - title: Conservation",
        "    key: conservation",
        '    level: "{project}.Elev.Inst.0.Top of Conservation"',
        "    unit: ft",
        "    precision: 2",
    ]
    config_path.write_text("\n".join(lines), encoding="utf-8")

    result = runner.invoke(
        cli,
        ["report", "generate", "--config", str(config_path), "--out", str(out_path)],
    )

    assert result.exit_code == 0, result.output
    html = out_path.read_text(encoding="utf-8")
    assert "Conservation" in html
    assert "725.00" in html


def test_report_generate_accepts_local_template_file(
    runner, workspace_tmpdir, fake_cwms
):
    config_path = workspace_tmpdir / "report.yaml"
    template_path = workspace_tmpdir / "custom.html.j2"
    out_path = workspace_tmpdir / "custom.html"
    _write_minimal_config(config_path)
    template_path.write_text(
        "<h1>{{ report.name }}</h1>{% for row in rows %}<p>{{ row }}</p>{% endfor %}",
        encoding="utf-8",
    )

    result = runner.invoke(
        cli,
        [
            "report",
            "generate",
            "--config",
            str(config_path),
            "--template-file",
            str(template_path),
            "--out",
            str(out_path),
        ],
    )

    assert result.exit_code == 0, result.output
    html = out_path.read_text(encoding="utf-8")
    assert "<h1>Daily Reservoir Report</h1>" in html
    assert "<p>KEYS</p>" in html


def test_report_templates_list_uses_pandas_table_and_source_column(runner):
    result = runner.invoke(cli, ["report", "templates", "list"])

    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    header_index = next(
        index for index, line in enumerate(lines) if line.startswith("Template")
    )
    header = lines[header_index]
    wm_daily = next(line for line in lines if line.startswith("WM-Daily"))
    assert header.index("Source") == wm_daily.index("builtin")
    assert header.index("Description") == wm_daily.index(
        "Generic Water Management daily table report"
    )
    assert "WM-Daily" in result.output
    assert "builtin" in result.output
    assert "Generic Water Management daily table report" in result.output


def test_report_templates_list_includes_user_defined_template(
    runner, workspace_tmpdir, monkeypatch
):
    template_path = workspace_tmpdir / "custom.html.j2"
    template_path.write_text("<p>{{ report.name }}</p>", encoding="utf-8")
    monkeypatch.setattr(
        colors,
        "c",
        lambda text, color, bright=False: f"{color}:{text}:{bright}",
    )

    result = runner.invoke(
        cli,
        ["report", "templates", "list", "--template-file", str(template_path)],
    )

    assert result.exit_code == 0, result.output
    assert str(template_path) in result.output
    assert "cyan:user-defined:True" in result.output
    assert "green:builtin:True" in result.output


def test_report_rejects_unknown_builtin_template(runner, workspace_tmpdir, fake_cwms):
    config_path = workspace_tmpdir / "report.yaml"
    _write_minimal_config(config_path)

    result = runner.invoke(
        cli,
        [
            "report",
            "generate",
            "--config",
            str(config_path),
            "--template",
            "MissingTemplate",
        ],
    )

    assert result.exit_code != 0
    assert "Unknown built-in report template" in result.output
