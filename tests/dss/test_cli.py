import logging

from click.testing import CliRunner

from cwmscli.__main__ import cli
from cwmscli.dss.cli import _finish, _PlainTextFormatter, export_cmd, import_cmd
from cwmscli.dss.compat import _normalize_legacy_args
from cwmscli.dss.transfer import TransferSummary
from cwmscli.utils import colors


def test_canonical_help_is_lazy():
    runner = CliRunner()
    assert runner.invoke(cli, ["dss", "import", "--help"]).exit_code == 0
    assert runner.invoke(cli, ["dss", "export", "--help"]).exit_code == 0


def test_legacy_db_option_has_targeted_error(tmp_path):
    result = CliRunner().invoke(
        import_cmd,
        [
            "-o",
            "SWT",
            "-dss",
            str(tmp_path / "data.dss"),
            "-p",
            "1",
            "-db",
            "legacy.conf",
        ],
    )
    assert result.exit_code == 2
    assert "This port uses CDA" in result.output


def test_monitor_and_identifier_have_targeted_errors(tmp_path):
    base = ["-o", "SWT", "-dss", str(tmp_path / "data.dss"), "-p", "1"]

    monitor = CliRunner().invoke(export_cmd, [*base, "-m"])
    identifier = CliRunner().invoke(import_cmd, [*base, "-id", "job"])

    assert monitor.exit_code == 2
    assert "batch-only" in monitor.output
    assert identifier.exit_code == 2
    assert "checkpointing is deferred" in identifier.output


def test_time_window_is_required(tmp_path):
    result = CliRunner().invoke(
        export_cmd, ["-o", "SWT", "-dss", str(tmp_path / "data.dss")]
    )
    assert result.exit_code == 2
    assert "Specify either" in result.output


def test_invalid_dss_time_zone_is_rejected(tmp_path):
    result = CliRunner().invoke(
        export_cmd,
        [
            "-o",
            "SWT",
            "-dss",
            str(tmp_path / "data.dss"),
            "-p",
            "1",
            "-tz",
            "Not/AZone",
        ],
    )
    assert result.exit_code == 2
    assert "unknown time zone" in result.output


def test_mapping_and_filter_are_mutually_exclusive(tmp_path):
    mapping = tmp_path / "map.csv"
    filters = tmp_path / "filter.txt"
    mapping.write_text("", encoding="utf-8")
    filters.write_text("", encoding="utf-8")
    result = CliRunner().invoke(
        export_cmd,
        [
            "-o",
            "SWT",
            "-dss",
            str(tmp_path / "data.dss"),
            "-p",
            "1",
            "-f",
            str(mapping),
            "-f2",
            str(filters),
        ],
    )
    assert result.exit_code == 2
    assert "mutually exclusive" in result.output


def test_legacy_equals_argument_forms_are_normalized():
    assert _normalize_legacy_args(["-o=SWT", "-dss=file.dss", "-p=24", "-tz=UTC"]) == [
        "-o",
        "SWT",
        "-dss",
        "file.dss",
        "-p",
        "24",
        "-tz",
        "UTC",
    ]
    assert _normalize_legacy_args(["-o=SWT", "-dss=file", ".dss", "-p=24"]) == [
        "-o",
        "SWT",
        "-dss",
        "file.dss",
        "-p",
        "24",
    ]


def test_summary_uses_project_colors_but_log_formatter_is_plain(capsys, monkeypatch):
    color_calls = []
    real_color = colors.c

    def record_color(text, color, bright=False):
        color_calls.append((text, color, bright))
        return text

    monkeypatch.setattr(colors, "c", record_color)
    _finish(TransferSummary(discovered=2, transferred=1, skipped=1), 1)
    output = capsys.readouterr().out

    monkeypatch.setattr(colors, "c", real_color)
    colors.set_enabled(True)
    try:
        record = logging.LogRecord(
            "test",
            logging.INFO,
            __file__,
            1,
            colors.ok("Transferred"),
            (),
            None,
        )
        formatted = _PlainTextFormatter("%(message)s").format(record)
    finally:
        colors.set_enabled(False)

    assert output == "Discovered: 2; transferred: 1; skipped: 1; failed: 0\n"
    assert [call[1] for call in color_calls] == ["cyan", "green", "yellow", "red"]
    assert formatted == "Transferred"
