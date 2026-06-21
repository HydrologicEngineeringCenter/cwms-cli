import importlib.metadata
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
    assert "[report] Fetching CWMS data and shaping table context" in result.output
    assert "[report] Rendering HTML with built-in template WM-Daily" in result.output
    assert "[report] Wrote" in result.output
    html = out_path.read_text(encoding="utf-8")
    assert "Example District" in html
    assert "Daily Reservoir Report" in html
    assert "KEYS Lake" in html
    assert "722.34" in html


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
    header, row = lines[header_index : header_index + 2]
    assert header.index("Source") == row.index("builtin")
    assert header.index("Description") == row.index(
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
