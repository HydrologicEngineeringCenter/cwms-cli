import shutil
import sys
import types
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from click.testing import CliRunner

from cwmscli.__main__ import cli
from cwmscli.reporting.config import Config


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

    def init_session(api_root=None):
        return None

    def get_multi_timeseries_df(ts_ids, office_id, unit, begin, end, melted):
        import pandas as pd

        rows = []
        tzinfo = ZoneInfo("UTC")

        if begin is None:
            begin = datetime(2026, 1, 1, tzinfo=tzinfo)
        if end is None:
            end = begin
        if begin.tzinfo is None:
            begin = begin.replace(tzinfo=tzinfo)
        if end.tzinfo is None:
            end = end.replace(tzinfo=tzinfo)

        def value_for(ts_id, index):
            if ts_id == "KEYS.Elev.Inst.1Hour.0.Ccp-Rev" and index == 0:
                return 722.34
            base = sum(ord(ch) for ch in ts_id) % 50
            return float(base + index + 700)

        for ts_id in ts_ids:
            if "1Month" in ts_id:
                current = datetime(begin.year, begin.month, 1, tzinfo=begin.tzinfo)
                index = 0
                while current < end:
                    rows.append(
                        {
                            "ts_id": ts_id,
                            "date-time": current.astimezone(tzinfo).isoformat(),
                            "value": value_for(ts_id, index),
                        }
                    )
                    if current.month == 12:
                        current = datetime(
                            current.year + 1, 1, 1, tzinfo=current.tzinfo
                        )
                    else:
                        current = datetime(
                            current.year, current.month + 1, 1, tzinfo=current.tzinfo
                        )
                    index += 1
            elif "1Hour" in ts_id:
                current = begin
                index = 0
                while current <= end:
                    rows.append(
                        {
                            "ts_id": ts_id,
                            "date-time": current.astimezone(tzinfo).isoformat(),
                            "value": value_for(ts_id, index),
                        }
                    )
                    current += timedelta(hours=1)
                    index += 1
            else:
                current = begin
                index = 0
                while current <= end:
                    rows.append(
                        {
                            "ts_id": ts_id,
                            "date-time": current.astimezone(tzinfo).isoformat(),
                            "value": value_for(ts_id, index),
                        }
                    )
                    current += timedelta(days=1)
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
            "href": f"https://example/{location_id}",
        }

    module.init_session = init_session
    module.get_multi_timeseries_df = get_multi_timeseries_df
    module.get_level_as_timeseries = get_level_as_timeseries
    module.get_location = get_location
    monkeypatch.setitem(sys.modules, "cwms", module)
    return module


def test_report_config_parses_engine_and_column_window(workspace_tmpdir):
    config_path = workspace_tmpdir / "report.yaml"
    config_path.write_text(
        "\n".join(
            [
                "office: SWT",
                "engine:",
                "  name: text",
                "  options:",
                "    project_width: 20",
                "report:",
                '  name: "Example"',
                "projects:",
                '  - "KEYS"',
                "columns:",
                "  - title: Pool Elev",
                "    key: elev",
                '    tsid: "{project}.Elev.Inst.1Hour.0.Ccp-Rev"',
                '    begin: "today 0800"',
                '    end: "today 0800"',
            ]
        ),
        encoding="utf-8",
    )

    cfg = Config.from_yaml(str(config_path))
    assert cfg.engine.name == "text"
    assert cfg.engine.options["project_width"] == 20
    assert cfg.columns[0].begin == "today 0800"
    assert cfg.columns[0].end == "today 0800"


def test_report_generate_text_engine_writes_output(runner, workspace_tmpdir, fake_cwms):
    config_path = workspace_tmpdir / "report.yaml"
    out_path = workspace_tmpdir / "report.txt"
    config_path.write_text(
        "\n".join(
            [
                "office: SWT",
                "engine:",
                "  name: text",
                "  options:",
                "    project_width: 12",
                "report:",
                '  district: "Tulsa District"',
                '  name: "Daily Reservoir Report"',
                "projects:",
                '  - "KEYS"',
                "columns:",
                "  - title: Pool Elev",
                "    key: elev",
                '    tsid: "{project}.Elev.Inst.1Hour.0.Ccp-Rev"',
                "    precision: 2",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        cli,
        ["report", "generate", "--config", str(config_path), "--out", str(out_path)],
    )

    assert result.exit_code == 0, result.output
    text = out_path.read_text(encoding="utf-8")
    assert "Tulsa District" in text
    assert "Daily Reservoir Report" in text
    assert "KEYS Lake" in text
    assert "722.34" in text


EXAMPLES_DIR = Path("cwmscli") / "reporting" / "examples"


def _example_cli_args_with_output(
    config_path: Path, cfg: Config, out_path: Path | None
) -> list[str]:
    args = ["report", "generate", "--config", str(config_path)]

    if cfg.dataset.kind in {
        "monthly_project",
        "monthly_location",
        "yearly_project",
        "yearly_location",
    }:
        dataset = cfg.dataset.options or {}
        selected_location = dataset.get("location") or dataset.get("project")
        if not selected_location:
            configured = dataset.get("locations") or dataset.get("projects") or []
            if configured:
                args.extend(["--location", str(configured[0])])

    if out_path is not None:
        args.extend(["--out", str(out_path)])
    return args


@pytest.mark.parametrize(
    "config_path",
    sorted(EXAMPLES_DIR.glob("*.yaml")),
    ids=lambda path: path.stem,
)
def test_report_examples_generate(runner, workspace_tmpdir, fake_cwms, config_path):
    resolved_config_path = config_path.resolve()
    cfg = Config.from_yaml(str(resolved_config_path))
    suffix = ".html" if cfg.engine.name == "jinja2" else ".txt"
    out_path = workspace_tmpdir / f"{resolved_config_path.stem}{suffix}"
    args = _example_cli_args_with_output(resolved_config_path, cfg, out_path)

    result = runner.invoke(cli, args)

    assert result.exit_code == 0, f"{config_path.name} failed:\n{result.output}"
    assert out_path.exists(), f"{config_path.name} did not write {out_path}"
    content = out_path.read_text(encoding="utf-8")
    assert content.strip(), f"{config_path.name} wrote empty output"
