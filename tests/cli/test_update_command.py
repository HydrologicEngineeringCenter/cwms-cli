import sys
from types import SimpleNamespace

from click.testing import CliRunner

from cwmscli.__main__ import cli
from cwmscli.utils.update import UpdateEnvironment


class _DummyResult:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _set_update_os(monkeypatch, name):
    """Set the updater OS without changing the process-wide ``os`` module."""
    monkeypatch.setattr("cwmscli.commands.commands_cwms.os", SimpleNamespace(name=name))


def test_update_command_runs_pip_upgrade(monkeypatch):
    calls = []
    update_environment = UpdateEnvironment(
        python_executable=r"C:\Python\python.exe",
        environment_prefix=r"C:\Python",
        environment_type="Python installation",
        package_location=r"C:\Python\Lib\site-packages",
    )

    def fake_run(cmd, check=False, capture_output=False, text=False):
        calls.append((cmd, check, capture_output, text))
        return _DummyResult(0)

    _set_update_os(monkeypatch, "posix")
    monkeypatch.setattr("cwmscli.commands.commands_cwms.subprocess.run", fake_run)
    monkeypatch.setattr(
        "cwmscli.commands.commands_cwms.get_cwms_cli_version", lambda: "1.2.3"
    )
    monkeypatch.setattr(
        "cwmscli.commands.commands_cwms.get_update_environment",
        lambda: update_environment,
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["update"], input="y\n")

    assert result.exit_code == 0
    assert "Current cwms-cli version: 1.2.3" in result.output
    assert "Python executable: C:\\Python\\python.exe" in result.output
    assert "Environment: C:\\Python (Python installation)" in result.output
    assert "Package location: C:\\Python\\Lib\\site-packages" in result.output
    assert result.output.index("Update environment:") < result.output.index(
        "Proceed with updating"
    )
    assert "Update complete" in result.output
    assert len(calls) == 1
    assert calls[0][0] == [
        r"C:\Python\python.exe",
        "-m",
        "pip",
        "install",
        "--upgrade",
        "cwms-cli",
    ]
    assert calls[0][1] is False
    assert calls[0][2] is True
    assert calls[0][3] is True


def test_update_command_includes_pre_flag(monkeypatch):
    calls = []

    def fake_run(cmd, check=False, capture_output=False, text=False):
        calls.append((cmd, check, capture_output, text))
        return _DummyResult(0)

    _set_update_os(monkeypatch, "posix")
    monkeypatch.setattr("cwmscli.commands.commands_cwms.subprocess.run", fake_run)

    runner = CliRunner()
    result = runner.invoke(cli, ["update", "--pre", "--yes"])

    assert result.exit_code == 0
    assert calls[0][0][-1] == "--pre"


def test_update_command_targets_specific_version(monkeypatch):
    calls = []

    def fake_run(cmd, check=False, capture_output=False, text=False):
        calls.append((cmd, check, capture_output, text))
        return _DummyResult(0)

    _set_update_os(monkeypatch, "posix")
    monkeypatch.setattr("cwmscli.commands.commands_cwms.subprocess.run", fake_run)

    runner = CliRunner()
    result = runner.invoke(cli, ["update", "--target-version", "1.2.0", "--yes"])

    assert result.exit_code == 0
    assert "Requested cwms-cli version: 1.2.0" in result.output
    assert calls[0][0] == [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "cwms-cli==1.2.0",
    ]


def test_update_command_surfaces_pip_failure(monkeypatch):
    def fake_run(cmd, check=False, capture_output=False, text=False):
        return _DummyResult(1)

    _set_update_os(monkeypatch, "posix")
    monkeypatch.setattr("cwmscli.commands.commands_cwms.subprocess.run", fake_run)

    runner = CliRunner()
    result = runner.invoke(cli, ["update", "--yes"])

    assert result.exit_code == 1
    assert "cwms-cli update failed" in result.output


def test_update_command_surfaces_missing_target_version(monkeypatch):
    def fake_run(cmd, check=False, capture_output=False, text=False):
        return _DummyResult(
            1,
            stderr=(
                "ERROR: Could not find a version that satisfies the requirement "
                "cwms-cli==9.9.9\n"
                "ERROR: No matching distribution found for cwms-cli==9.9.9\n"
            ),
        )

    _set_update_os(monkeypatch, "posix")
    monkeypatch.setattr("cwmscli.commands.commands_cwms.subprocess.run", fake_run)

    runner = CliRunner()
    result = runner.invoke(cli, ["update", "--target-version", "9.9.9", "--yes"])

    assert result.exit_code == 1
    assert "Requested cwms-cli version '9.9.9' was not found." in result.output


def test_update_command_cancelled_by_user(monkeypatch):
    calls = []

    def fake_run(cmd, check=False, capture_output=False, text=False):
        calls.append((cmd, check, capture_output, text))
        return _DummyResult(0)

    _set_update_os(monkeypatch, "posix")
    monkeypatch.setattr("cwmscli.commands.commands_cwms.subprocess.run", fake_run)

    runner = CliRunner()
    result = runner.invoke(cli, ["update"], input="n\n")

    assert result.exit_code == 0
    assert "Update canceled." in result.output
    assert not calls


def test_update_command_defers_to_separate_process_on_windows(monkeypatch):
    launched = []

    def fake_launch(cmd):
        launched.append(cmd)
        return r"C:\Temp\cwms-cli-update.cmd"

    def fake_run(*args, **kwargs):
        raise AssertionError("subprocess.run should not be used on Windows update")

    _set_update_os(monkeypatch, "nt")
    monkeypatch.setattr(
        "cwmscli.commands.commands_cwms.launch_windows_update", fake_launch
    )
    monkeypatch.setattr("cwmscli.commands.commands_cwms.subprocess.run", fake_run)

    runner = CliRunner()
    result = runner.invoke(cli, ["update", "--target-version", "0.3.5", "--yes"])

    assert result.exit_code == 0
    assert "Opened a separate command window" in result.output
    assert "Update helper script: C:\\Temp\\cwms-cli-update.cmd" in result.output
    assert launched == [
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "cwms-cli==0.3.5",
        ]
    ]
