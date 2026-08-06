"""Tests for `cwms-cli env` commands and the file-based env store."""

import json
import os
import stat
import subprocess
import sys

import pytest
from click.testing import CliRunner

from cwmscli.commands.env import (
    _format_env,
    _quote_bash,
    _quote_cmd,
    _quote_dotenv,
    _quote_fish,
    _quote_powershell,
    env_group,
)
from cwmscli.utils.env_store import (
    EnvStoreError,
    delete_env,
    envs_dir,
    list_envs,
    load_env,
    save_env,
)


@pytest.fixture
def isolated_envs(monkeypatch, tmp_path):
    """Redirect env storage to a tmp dir for each test."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    return tmp_path


# ---------- env_store ----------


def test_save_load_roundtrip(isolated_envs):
    config = {
        "ENVIRONMENT": "demo",
        "CDA_API_ROOT": "https://example.mil/cwms-data",
        "CDA_API_KEY": "abc123",
        "OFFICE": "SWT",
    }
    save_env("demo", config)
    assert load_env("demo") == config


def test_save_env_writes_0600(isolated_envs):
    if sys.platform == "win32":
        pytest.skip("POSIX permission semantics")
    path = save_env("demo", {"CDA_API_KEY": "k"})
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o600


def test_save_env_overwrites_with_0600(isolated_envs):
    if sys.platform == "win32":
        pytest.skip("POSIX permission semantics")
    path = save_env("demo", {"a": "1"})
    os.chmod(path, 0o644)
    save_env("demo", {"a": "2"})
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert load_env("demo") == {"a": "2"}


def test_load_env_missing_returns_none(isolated_envs):
    assert load_env("nope") is None


def test_load_env_malformed_returns_none(isolated_envs):
    path = envs_dir() / "bad.json"
    path.write_text("{not valid json")
    assert load_env("bad") is None


def test_load_env_non_dict_returns_none(isolated_envs):
    path = envs_dir() / "list.json"
    path.write_text("[1, 2, 3]")
    assert load_env("list") is None


def test_delete_env_existing(isolated_envs):
    save_env("demo", {"a": "1"})
    assert delete_env("demo") is True
    assert load_env("demo") is None


def test_delete_env_missing(isolated_envs):
    assert delete_env("nope") is False


def test_list_envs(isolated_envs):
    assert list_envs() == ["cwbi-prod"]
    save_env("alpha", {"a": "1"})
    save_env("beta", {"a": "1"})
    save_env("gamma", {"a": "1"})
    assert list_envs() == ["alpha", "beta", "cwbi-prod", "gamma"]


def test_list_envs_deduplicates_defaults(isolated_envs):
    save_env("cwbi-prod", {"CDA_API_ROOT": "https://custom"})
    assert list_envs().count("cwbi-prod") == 1


@pytest.mark.parametrize("bad", ["", ".", "..", "a/b", "a\\b"])
def test_invalid_env_names_rejected(isolated_envs, bad):
    with pytest.raises(EnvStoreError):
        save_env(bad, {"a": "1"})


# ---------- built-in defaults ----------


def test_load_env_returns_builtin_default(isolated_envs):
    data = load_env("cwbi-prod")
    assert data is not None
    assert data["CDA_API_ROOT"] == "https://cwms-data.usace.army.mil/cwms-data"
    assert data["ENVIRONMENT"] == "cwbi-prod"


def test_on_disk_env_overrides_builtin(isolated_envs):
    save_env("cwbi-prod", {"CDA_API_ROOT": "https://custom", "CDA_API_KEY": "k"})
    data = load_env("cwbi-prod")
    assert data["CDA_API_ROOT"] == "https://custom"
    assert data["CDA_API_KEY"] == "k"


def test_show_labels_builtin(isolated_envs):
    runner = CliRunner()
    result = runner.invoke(env_group, ["show"])
    assert result.exit_code == 0
    assert "cwbi-prod (built-in)" in result.output


def test_show_no_builtin_label_when_customized(isolated_envs):
    save_env(
        "cwbi-prod",
        {"CDA_API_ROOT": "https://cwms-data.usace.army.mil/cwms-data", "OFFICE": "SWT"},
    )
    runner = CliRunner()
    result = runner.invoke(env_group, ["show"])
    assert result.exit_code == 0
    assert "cwbi-prod" in result.output
    assert "(built-in)" not in result.output


# ---------- env setup ----------


def test_setup_creates_file_with_0600(isolated_envs):
    runner = CliRunner()
    result = runner.invoke(
        env_group,
        ["setup", "myenv", "--api-root", "https://x.mil/cwms-data", "--api-key", "k"],
    )
    assert result.exit_code == 0, result.output
    path = envs_dir() / "myenv.json"
    assert path.exists()
    if sys.platform != "win32":
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    stored = json.loads(path.read_text())
    assert stored["CDA_API_ROOT"] == "https://x.mil/cwms-data"
    assert stored["CDA_API_KEY"] == "k"
    assert stored["ENVIRONMENT"] == "myenv"


def test_setup_uses_default_for_known_name(isolated_envs):
    runner = CliRunner()
    result = runner.invoke(env_group, ["setup", "cwbi-prod", "--api-key", "k"])
    assert result.exit_code == 0, result.output
    stored = load_env("cwbi-prod")
    assert stored["CDA_API_ROOT"] == "https://cwms-data.usace.army.mil/cwms-data"


def test_setup_requires_api_root_for_unknown_name(isolated_envs):
    runner = CliRunner()
    result = runner.invoke(env_group, ["setup", "newenv", "--api-key", "k"])
    assert result.exit_code != 0
    assert "--api-root is required" in result.output


def test_setup_partial_update_preserves_fields(isolated_envs):
    runner = CliRunner()
    runner.invoke(
        env_group,
        [
            "setup",
            "myenv",
            "--api-root",
            "https://x.mil/cwms-data",
            "--api-key",
            "old",
            "--office",
            "SWT",
        ],
    )
    result = runner.invoke(env_group, ["setup", "myenv", "--api-key", "new"])
    assert result.exit_code == 0, result.output
    stored = load_env("myenv")
    assert stored["CDA_API_KEY"] == "new"
    assert stored["CDA_API_ROOT"] == "https://x.mil/cwms-data"
    assert stored["OFFICE"] == "SWT"


def test_setup_uppercases_office(isolated_envs):
    runner = CliRunner()
    runner.invoke(
        env_group,
        ["setup", "myenv", "--api-root", "https://x", "--office", "swt"],
    )
    assert load_env("myenv")["OFFICE"] == "SWT"


# ---------- env show ----------


def test_show_empty_still_shows_builtins(isolated_envs):
    runner = CliRunner()
    result = runner.invoke(env_group, ["show"])
    assert result.exit_code == 0
    assert "cwbi-prod (built-in)" in result.output


def test_show_lists_envs_and_redacts_key(isolated_envs):
    save_env(
        "withkey",
        {"CDA_API_ROOT": "https://x", "CDA_API_KEY": "supersecret", "OFFICE": "SWT"},
    )
    save_env("nokey", {"CDA_API_ROOT": "https://y"})
    runner = CliRunner()
    result = runner.invoke(env_group, ["show"])
    assert result.exit_code == 0
    assert "withkey" in result.output
    assert "nokey" in result.output
    assert "has API key" in result.output
    assert "no API key" in result.output
    assert "supersecret" not in result.output


def test_show_marks_current_env(isolated_envs, monkeypatch):
    save_env("active", {"CDA_API_ROOT": "https://x"})
    monkeypatch.setenv("ENVIRONMENT", "active")
    runner = CliRunner()
    result = runner.invoke(env_group, ["show"])
    assert "Current environment:" in result.output
    assert "* active" in result.output


# ---------- env show --check ----------

from cwmscli.commands.env import _check_env


def _fake_check(result_map):
    """Return a _check_env replacement that returns canned results by API root."""
    default = {
        "reachable": True,
        "latency_ms": 42,
        "auth": "skipped",
        "error": None,
    }

    def _check(env_config):
        root = env_config.get("CDA_API_ROOT", "")
        return result_map.get(root, default)

    return _check


def test_show_check_reachable(isolated_envs, monkeypatch):
    save_env("demo", {"CDA_API_ROOT": "https://x.mil/cwms-data"})
    monkeypatch.setattr(
        "cwmscli.commands.env._check_env",
        _fake_check({}),
    )
    runner = CliRunner()
    result = runner.invoke(env_group, ["show", "--check"])
    assert result.exit_code == 0
    assert "reachable" in result.output
    assert "42ms)" in result.output


def test_show_check_unreachable(isolated_envs, monkeypatch):
    save_env("demo", {"CDA_API_ROOT": "https://x.mil/cwms-data"})
    monkeypatch.setattr(
        "cwmscli.commands.env._check_env",
        _fake_check(
            {
                "https://x.mil/cwms-data": {
                    "reachable": False,
                    "latency_ms": None,
                    "auth": "skipped",
                    "error": "Connection refused",
                },
            }
        ),
    )
    runner = CliRunner()
    result = runner.invoke(env_group, ["show", "--check"])
    assert result.exit_code == 0
    assert "unreachable" in result.output
    assert "Connection refused" in result.output


def test_show_check_auth_ok(isolated_envs, monkeypatch):
    save_env(
        "demo",
        {"CDA_API_ROOT": "https://x.mil/cwms-data", "CDA_API_KEY": "apikey mykey"},
    )
    monkeypatch.setattr(
        "cwmscli.commands.env._check_env",
        _fake_check(
            {
                "https://x.mil/cwms-data": {
                    "reachable": True,
                    "latency_ms": 100,
                    "auth": "ok",
                    "error": None,
                },
            }
        ),
    )
    runner = CliRunner()
    result = runner.invoke(env_group, ["show", "--check"])
    assert result.exit_code == 0
    assert "authenticated" in result.output


def test_show_check_auth_failed(isolated_envs, monkeypatch):
    save_env(
        "demo",
        {"CDA_API_ROOT": "https://x.mil/cwms-data", "CDA_API_KEY": "apikey bad"},
    )
    monkeypatch.setattr(
        "cwmscli.commands.env._check_env",
        _fake_check(
            {
                "https://x.mil/cwms-data": {
                    "reachable": True,
                    "latency_ms": 100,
                    "auth": "failed",
                    "error": None,
                },
            }
        ),
    )
    runner = CliRunner()
    result = runner.invoke(env_group, ["show", "--check"])
    assert result.exit_code == 0
    assert "auth failed" in result.output


def test_show_check_no_key_skips_auth(isolated_envs, monkeypatch):
    save_env("demo", {"CDA_API_ROOT": "https://x.mil/cwms-data"})
    monkeypatch.setattr(
        "cwmscli.commands.env._check_env",
        _fake_check({}),
    )
    runner = CliRunner()
    result = runner.invoke(env_group, ["show", "--check"])
    assert result.exit_code == 0
    assert "authenticated" not in result.output
    assert "auth failed" not in result.output


def test_show_without_check_flag_unchanged(isolated_envs):
    save_env("demo", {"CDA_API_ROOT": "https://x.mil/cwms-data"})
    runner = CliRunner()
    result = runner.invoke(env_group, ["show"])
    assert result.exit_code == 0
    assert "Connect:" not in result.output
    assert "Auth:" not in result.output


# ---------- env delete ----------


def test_delete_with_yes_flag(isolated_envs):
    save_env("doomed", {"a": "1"})
    runner = CliRunner()
    result = runner.invoke(env_group, ["delete", "doomed", "--yes"])
    assert result.exit_code == 0
    assert load_env("doomed") is None


def test_delete_confirmation_cancel(isolated_envs):
    save_env("safe", {"a": "1"})
    runner = CliRunner()
    result = runner.invoke(env_group, ["delete", "safe"], input="n\n")
    assert result.exit_code == 0
    assert "Cancelled" in result.output
    assert load_env("safe") == {"a": "1"}


def test_delete_missing_env_errors(isolated_envs):
    runner = CliRunner()
    result = runner.invoke(env_group, ["delete", "ghost", "--yes"])
    assert result.exit_code != 0
    assert "not found" in result.output


# ---------- quoting helpers ----------


@pytest.mark.parametrize(
    "value",
    [
        "plain",
        "with spaces",
        "with'apostrophe",
        'with"quote',
        "with\\backslash",
        "with$dollar",
        "with`backtick",
        "with'multi'apos",
        "a'b\"c\\d$e",
    ],
)
def test_bash_quoting_roundtrip(value):
    """Eval the bash output and confirm the value comes back unchanged."""
    if sys.platform == "win32":
        pytest.skip("bash round-trip is not part of Windows shell coverage")
    line = f"export X={_quote_bash(value)}"
    out = subprocess.check_output(["bash", "-c", f'{line}; printf %s "$X"'])
    assert out.decode() == value


@pytest.mark.parametrize(
    "value",
    [
        "plain",
        "with spaces",
        'with"quote',
        "with\\backslash",
        "with$dollar",
    ],
)
def test_dotenv_quoting_roundtrip(value):
    """Parse dotenv with python-dotenv-style rules and confirm round-trip."""
    line = f"X={_quote_dotenv(value)}"
    # Strip the wrapping double quotes, then unescape \\ and \"
    raw = line.split("=", 1)[1]
    assert raw.startswith('"') and raw.endswith('"')
    inner = raw[1:-1]
    decoded = inner.replace('\\"', '"').replace("\\\\", "\\")
    assert decoded == value


def test_powershell_quote_doubles_apostrophes():
    assert _quote_powershell("a'b") == "'a''b'"
    assert _quote_powershell("plain") == "'plain'"


def test_cmd_quote_doubles_percent_and_quote():
    assert _quote_cmd("100%") == "100%%"
    assert _quote_cmd('a"b') == 'a""b'


def test_fish_quote_escapes_apostrophe_and_backslash():
    assert _quote_fish("a'b") == "'a\\'b'"
    assert _quote_fish("a\\b") == "'a\\\\b'"
    assert _quote_fish("plain") == "'plain'"


# ---------- env export ----------


@pytest.fixture
def env_with_key(isolated_envs):
    save_env(
        "demo",
        {
            "ENVIRONMENT": "demo",
            "CDA_API_ROOT": "https://x.mil/cwms-data",
            "CDA_API_KEY": "secret",
            "OFFICE": "SWT",
        },
    )
    return "demo"


def test_export_dotenv_format(env_with_key):
    runner = CliRunner()
    result = runner.invoke(env_group, ["export", env_with_key, "--show-key"])
    assert result.exit_code == 0
    out = result.output
    assert 'CDA_API_ROOT="https://x.mil/cwms-data"' in out
    assert 'CDA_API_KEY="secret"' in out
    assert 'OFFICE="SWT"' in out


def test_export_bash_format_evaluates(env_with_key):
    if sys.platform == "win32":
        pytest.skip("bash export evaluation is not part of Windows shell coverage")
    runner = CliRunner()
    result = runner.invoke(
        env_group, ["export", env_with_key, "--format", "bash", "--show-key"]
    )
    assert result.exit_code == 0
    script = (
        result.output + '\nprintf "%s|%s|%s" "$CDA_API_ROOT" "$CDA_API_KEY" "$OFFICE"'
    )
    out = subprocess.check_output(["bash", "-c", script]).decode()
    assert out == "https://x.mil/cwms-data|secret|SWT"


def test_export_powershell_format_structure(env_with_key):
    runner = CliRunner()
    result = runner.invoke(
        env_group, ["export", env_with_key, "--format", "powershell", "--show-key"]
    )
    assert result.exit_code == 0
    assert "$env:CDA_API_KEY = 'secret'" in result.output


def test_export_cmd_format_structure(env_with_key):
    runner = CliRunner()
    result = runner.invoke(
        env_group, ["export", env_with_key, "--format", "cmd", "--show-key"]
    )
    assert result.exit_code == 0
    # @ prefix prevents cmd from echoing the line (which would leak the key)
    assert '@set "CDA_API_KEY=secret"' in result.output


def test_export_cmd_format_all_lines_silenced(env_with_key):
    runner = CliRunner()
    result = runner.invoke(
        env_group, ["export", env_with_key, "--format", "cmd", "--show-key"]
    )
    assert result.exit_code == 0
    for line in result.output.strip().splitlines():
        if line.startswith("set "):
            pytest.fail(f"unsuppressed set line would echo the value: {line!r}")


def test_export_fish_format_structure(env_with_key):
    runner = CliRunner()
    result = runner.invoke(
        env_group, ["export", env_with_key, "--format", "fish", "--show-key"]
    )
    assert result.exit_code == 0
    assert "set -gx CDA_API_KEY 'secret'" in result.output


def test_export_tty_refusal(env_with_key, monkeypatch):
    monkeypatch.setattr("cwmscli.commands.env._stdout_is_tty", lambda: True)
    runner = CliRunner()
    result = runner.invoke(env_group, ["export", env_with_key])
    assert result.exit_code != 0
    assert "into your current shell" in result.output
    assert "--format bash" in result.output
    assert "Out-String | Invoke-Expression" in result.output
    assert "secret" not in result.output


def test_export_help_uses_detected_shell(env_with_key, monkeypatch):
    monkeypatch.setattr("cwmscli.commands.env._stdout_is_tty", lambda: True)
    monkeypatch.setattr("cwmscli.commands.env._detect_shell_kind", lambda: "powershell")
    runner = CliRunner()
    result = runner.invoke(env_group, ["export", env_with_key])
    assert result.exit_code != 0
    # Powershell recipe is the primary; bash etc. listed as "other shells"
    first_line = result.output.splitlines()[0]
    assert "powershell detected" in first_line
    assert "For other shells:" in result.output


def test_export_show_key_overrides_tty_refusal(env_with_key, monkeypatch):
    monkeypatch.setattr("cwmscli.commands.env._stdout_is_tty", lambda: True)
    runner = CliRunner()
    result = runner.invoke(env_group, ["export", env_with_key, "--show-key"])
    assert result.exit_code == 0
    assert "secret" in result.output


def test_export_no_key_omits_key(env_with_key):
    runner = CliRunner()
    result = runner.invoke(env_group, ["export", env_with_key, "--no-key"])
    assert result.exit_code == 0
    assert "CDA_API_KEY" not in result.output
    assert "CDA_API_ROOT" in result.output


def test_export_no_key_allows_tty_when_no_key(isolated_envs, monkeypatch):
    save_env("nokey", {"CDA_API_ROOT": "https://x", "OFFICE": "SWT"})
    monkeypatch.setattr("cwmscli.commands.env._stdout_is_tty", lambda: True)
    runner = CliRunner()
    result = runner.invoke(env_group, ["export", "nokey"])
    assert result.exit_code == 0
    assert "https://x" in result.output


def test_export_output_writes_0600(env_with_key, tmp_path):
    out = tmp_path / "out.env"
    runner = CliRunner()
    result = runner.invoke(env_group, ["export", env_with_key, "--output", str(out)])
    assert result.exit_code == 0, result.output
    assert out.exists()
    if sys.platform != "win32":
        assert stat.S_IMODE(os.stat(out).st_mode) == 0o600
    contents = out.read_text()
    assert 'CDA_API_KEY="secret"' in contents


def test_export_output_dotenv_prints_gitignore_reminder(env_with_key, tmp_path):
    out = tmp_path / ".env"
    runner = CliRunner()
    result = runner.invoke(env_group, ["export", env_with_key, "--output", str(out)])
    assert result.exit_code == 0
    assert "gitignore" in result.output


def test_export_missing_env_errors(isolated_envs):
    runner = CliRunner()
    result = runner.invoke(env_group, ["export", "ghost"])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_format_env_sorts_keys():
    out = _format_env({"B": "2", "A": "1"}, "dotenv")
    assert out.splitlines() == ['A="1"', 'B="2"']
