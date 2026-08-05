"""Tests for --source-env / --target-env resolution in load commands."""

import pytest
from click.testing import CliRunner

from cwmscli.load.location.location import location as location_group
from cwmscli.utils.env_store import save_env


@pytest.fixture
def isolated_envs(monkeypatch, tmp_path):
    """Redirect env storage to a tmp dir for each test."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("CDA_SOURCE_URL", raising=False)
    monkeypatch.delenv("CDA_TARGET_URL", raising=False)
    monkeypatch.delenv("CDA_SOURCE_OFFICE", raising=False)
    monkeypatch.delenv("CDA_API_KEY", raising=False)
    monkeypatch.setattr(
        "cwmscli.load.root._validate_cda_api_root", lambda *a, **k: None
    )
    return tmp_path


@pytest.fixture
def capture_load(monkeypatch):
    """Monkeypatch the inner load function to capture kwargs instead of calling CDA."""
    captured = {}

    def fake_load(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("cwmscli.load.location.location_ids.load_locations", fake_load)
    monkeypatch.setattr("cwmscli.utils.get_saved_login_token", lambda *a, **kw: None)
    return captured


def _invoke(args):
    return CliRunner().invoke(location_group, ["ids-all"] + args)


# ---------- resolution ----------


def test_source_env_resolves_cda_and_office(isolated_envs, capture_load):
    save_env(
        "prod",
        {
            "CDA_API_ROOT": "https://prod.mil/cwms-data",
            "OFFICE": "SWT",
        },
    )
    result = _invoke(
        [
            "--source-env",
            "prod",
            "--target-cda",
            "http://localhost:8082/cwms-data",
        ]
    )
    assert result.exit_code == 0, result.output
    assert capture_load["source_cda"] == "https://prod.mil/cwms-data"
    assert capture_load["source_office"] == "SWT"


def test_target_env_resolves_cda_and_api_key(isolated_envs, capture_load):
    save_env(
        "local",
        {
            "CDA_API_ROOT": "http://localhost:8082/cwms-data",
            "CDA_API_KEY": "apikey abc123",
        },
    )
    result = _invoke(
        [
            "--source-cda",
            "https://prod.mil/cwms-data",
            "--source-office",
            "SWT",
            "--target-env",
            "local",
        ]
    )
    assert result.exit_code == 0, result.output
    assert capture_load["target_cda"] == "http://localhost:8082/cwms-data"
    assert capture_load["target_api_key"] == "apikey abc123"


def test_both_envs_resolve(isolated_envs, capture_load):
    save_env(
        "prod",
        {
            "CDA_API_ROOT": "https://prod.mil/cwms-data",
            "OFFICE": "SWT",
        },
    )
    save_env(
        "local",
        {
            "CDA_API_ROOT": "http://localhost:8082/cwms-data",
            "CDA_API_KEY": "apikey abc123",
        },
    )
    result = _invoke(["--source-env", "prod", "--target-env", "local"])
    assert result.exit_code == 0, result.output
    assert capture_load["source_cda"] == "https://prod.mil/cwms-data"
    assert capture_load["source_office"] == "SWT"
    assert capture_load["target_cda"] == "http://localhost:8082/cwms-data"
    assert capture_load["target_api_key"] == "apikey abc123"


# ---------- explicit override ----------


def test_explicit_source_office_overrides_env(isolated_envs, capture_load):
    save_env(
        "prod",
        {
            "CDA_API_ROOT": "https://prod.mil/cwms-data",
            "OFFICE": "SWT",
        },
    )
    result = _invoke(
        [
            "--source-env",
            "prod",
            "--source-office",
            "LRD",
            "--target-cda",
            "http://localhost:8082/cwms-data",
        ]
    )
    assert result.exit_code == 0, result.output
    assert capture_load["source_office"] == "LRD"


# ---------- mutual exclusivity ----------


def test_source_env_and_source_cda_mutually_exclusive(isolated_envs):
    save_env("prod", {"CDA_API_ROOT": "https://prod.mil/cwms-data", "OFFICE": "SWT"})
    result = _invoke(
        [
            "--source-env",
            "prod",
            "--source-cda",
            "https://other.mil/cwms-data",
            "--source-office",
            "SWT",
        ]
    )
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output


def test_target_env_and_target_cda_mutually_exclusive(isolated_envs):
    save_env("local", {"CDA_API_ROOT": "http://localhost/cwms-data"})
    result = _invoke(
        [
            "--source-cda",
            "https://prod.mil/cwms-data",
            "--source-office",
            "SWT",
            "--target-env",
            "local",
            "--target-cda",
            "http://other:8082/cwms-data",
        ]
    )
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output


def test_source_env_and_source_csv_mutually_exclusive(isolated_envs, tmp_path):
    save_env("prod", {"CDA_API_ROOT": "https://prod.mil/cwms-data", "OFFICE": "SWT"})
    csv = tmp_path / "in.csv"
    csv.write_text("name,office-id,active\nLOC_A,SWT,True\n")
    result = _invoke(
        [
            "--source-env",
            "prod",
            "--source-csv",
            str(csv),
            "--target-cda",
            "http://localhost:8082/cwms-data",
        ]
    )
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output


# ---------- error paths ----------


def test_source_env_not_found(isolated_envs):
    result = _invoke(
        [
            "--source-env",
            "nonexistent",
            "--target-cda",
            "http://localhost:8082/cwms-data",
        ]
    )
    assert result.exit_code != 0
    assert "not found" in result.output


def test_target_env_not_found(isolated_envs):
    result = _invoke(
        [
            "--source-cda",
            "https://prod.mil/cwms-data",
            "--source-office",
            "SWT",
            "--target-env",
            "nonexistent",
        ]
    )
    assert result.exit_code != 0
    assert "not found" in result.output


def test_source_env_missing_api_root(isolated_envs):
    save_env("broken", {"OFFICE": "SWT"})
    result = _invoke(
        [
            "--source-env",
            "broken",
            "--target-cda",
            "http://localhost:8082/cwms-data",
        ]
    )
    assert result.exit_code != 0
    assert "CDA_API_ROOT" in result.output


# ---------- kwargs don't leak ----------


def test_env_kwargs_not_passed_to_command(isolated_envs, capture_load):
    save_env(
        "prod",
        {
            "CDA_API_ROOT": "https://prod.mil/cwms-data",
            "OFFICE": "SWT",
        },
    )
    save_env(
        "local",
        {
            "CDA_API_ROOT": "http://localhost:8082/cwms-data",
        },
    )
    result = _invoke(["--source-env", "prod", "--target-env", "local"])
    assert result.exit_code == 0, result.output
    assert "source_env" not in capture_load
    assert "target_env" not in capture_load
