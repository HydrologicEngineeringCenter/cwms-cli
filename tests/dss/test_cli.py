from click.testing import CliRunner

from cwmscli.__main__ import cli
from cwmscli.dss.cli import export_cmd, import_cmd
from cwmscli.dss.compat import _normalize_legacy_args


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
