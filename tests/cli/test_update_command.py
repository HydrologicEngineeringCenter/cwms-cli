import sys

from click.testing import CliRunner

from cwmscli.__main__ import cli


class _DummyResult:
    def __init__(self, returncode):
        self.returncode = returncode


def test_update_command_runs_pip_upgrade(monkeypatch):
    calls = []

    def fake_run(cmd, check=False):
        calls.append((cmd, check))
        return _DummyResult(0)

    monkeypatch.setattr("cwmscli.commands.commands_cwms.subprocess.run", fake_run)
    monkeypatch.setattr(
        "cwmscli.commands.commands_cwms.get_cwms_cli_version", lambda: "1.2.3"
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["update"], input="y\n")

    assert result.exit_code == 0
    assert "Current cwms-cli version: 1.2.3" in result.output
    assert "Update complete" in result.output
    assert len(calls) == 1
    assert calls[0][0] == [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "cwms-cli",
    ]
    assert calls[0][1] is False


def test_update_command_includes_pre_flag(monkeypatch):
    calls = []

    def fake_run(cmd, check=False):
        calls.append((cmd, check))
        return _DummyResult(0)

    monkeypatch.setattr("cwmscli.commands.commands_cwms.subprocess.run", fake_run)

    runner = CliRunner()
    result = runner.invoke(cli, ["update", "--pre", "--yes"])

    assert result.exit_code == 0
    assert calls[0][0][-1] == "--pre"


def test_update_command_surfaces_pip_failure(monkeypatch):
    def fake_run(cmd, check=False):
        return _DummyResult(1)

    monkeypatch.setattr("cwmscli.commands.commands_cwms.subprocess.run", fake_run)

    runner = CliRunner()
    result = runner.invoke(cli, ["update", "--yes"])

    assert result.exit_code == 1
    assert "cwms-cli update failed" in result.output


def test_update_command_cancelled_by_user(monkeypatch):
    calls = []

    def fake_run(cmd, check=False):
        calls.append((cmd, check))
        return _DummyResult(0)

    monkeypatch.setattr("cwmscli.commands.commands_cwms.subprocess.run", fake_run)

    runner = CliRunner()
    result = runner.invoke(cli, ["update"], input="n\n")

    assert result.exit_code == 0
    assert "Update canceled." in result.output
    assert not calls
