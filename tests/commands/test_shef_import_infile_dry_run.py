import json
import sys
import types
from io import StringIO
from pathlib import Path

import pytest
from click.testing import CliRunner

from cwmscli.commands.shef.import_infile import import_shef_infile


@pytest.fixture
def fake_cwms(monkeypatch):
    """Mock the cwms module for testing."""
    fake_cwms_module = types.ModuleType("cwms")

    # Create a fake api submodule
    fake_api = types.ModuleType("api")

    def fake_init_session(api_root, api_key=None, token=None):
        pass

    fake_api.init_session = fake_init_session
    fake_cwms_module.api = fake_api

    # Mock timeseries_group_df_to_json to return a simple dict
    def fake_timeseries_group_df_to_json(
        data, group_id, group_office_id, category_office_id, category_id
    ):
        return {
            "group-id": group_id,
            "office-id": group_office_id,
            "category-id": category_id,
            "members": data.to_dict("records"),
        }

    fake_cwms_module.timeseries_group_df_to_json = fake_timeseries_group_df_to_json

    # Mock update_timeseries_groups
    def fake_update_timeseries_groups(data, group_id, office_id, replace_assigned_ts):
        pass

    fake_cwms_module.update_timeseries_groups = fake_update_timeseries_groups

    # Mock store_timeseries_groups
    def fake_store_timeseries_groups(data, fail_if_exists):
        pass

    fake_cwms_module.store_timeseries_groups = fake_store_timeseries_groups

    monkeypatch.setitem(sys.modules, "cwms", fake_cwms_module)
    return fake_cwms_module


def test_import_shef_infile_dry_run_with_desktop_file(fake_cwms, caplog, capsys):
    """Test dry_run with the exportShef_CWMS_LD8-10.in fixture file."""
    import logging

    caplog.set_level(logging.INFO)

    fixture_path = Path(__file__).parent / "fixtures" / "exportShef_CWMS_LD8-10.in"

    # Skip test if fixture doesn't exist
    if not fixture_path.exists():
        pytest.skip(f"Fixture file not found: {fixture_path}")

    import_shef_infile(
        in_file=str(fixture_path),
        group_name="LD8-10 Export",
        office_id="CWMS",
        api_root="https://test.example.com/",
        api_key="test-key",
        dry_run=True,
    )

    # Capture both logged output and printed output
    log_output = caplog.text
    captured = capsys.readouterr()
    printed_output = captured.out

    # Verify dry run output contains expected markers (in printed JSON)
    assert "--- DRY RUN: CWMS JSON payload ---" in printed_output
    assert "--- Dry run complete. Nothing was posted to the API. ---" in printed_output
    # Verify entries were logged
    assert "Found" in log_output
    assert "timeseries entries:" in log_output


def test_import_shef_infile_dry_run_parses_entries(fake_cwms, caplog):
    """Test that entries from the .in file are parsed correctly."""
    import logging

    caplog.set_level(logging.INFO)

    fixture_path = Path(__file__).parent / "fixtures" / "exportShef_CWMS_LD8-10.in"

    if not fixture_path.exists():
        pytest.skip(f"Fixture file not found: {fixture_path}")

    import_shef_infile(
        in_file=str(fixture_path),
        group_name="LD8-10 Export",
        office_id="CWMS",
        api_root="https://test.example.com/",
        api_key="test-key",
        dry_run=True,
    )

    output = caplog.text

    # Verify entries are logged
    assert "Found" in output
    assert "timeseries entries:" in output
    assert "LockDam_08" in output or "LockDam_09" in output or "LockDam_10" in output


def test_import_shef_infile_dry_run_no_api_call(fake_cwms, caplog):
    """Test that API session is not initialized in dry run mode."""
    import logging

    caplog.set_level(logging.INFO)

    fixture_path = Path(__file__).parent / "fixtures" / "exportShef_CWMS_LD8-10.in"

    if not fixture_path.exists():
        pytest.skip(f"Fixture file not found: {fixture_path}")

    init_called = []
    original_init = fake_cwms.api.init_session

    def tracked_init_session(api_root, api_key=None, token=None):
        init_called.append(True)
        return original_init(api_root, api_key, token)

    # Patch the fake_cwms.api.init_session
    fake_cwms.api.init_session = tracked_init_session

    import_shef_infile(
        in_file=str(fixture_path),
        group_name="LD8-10 Export",
        office_id="CWMS",
        api_root="https://test.example.com/",
        api_key="test-key",
        dry_run=True,
    )

    # Verify init_session was NOT called during dry run
    assert (
        len(init_called) == 0
    ), "API session should not be initialized in dry run mode"


def test_import_shef_infile_with_empty_file(fake_cwms, tmp_path, caplog):
    """Test dry run behavior with an empty .in file."""
    import logging

    caplog.set_level(logging.INFO)

    empty_in = tmp_path / "empty.in"
    empty_in.write_text("# Just a comment\n", encoding="utf-8")

    import_shef_infile(
        in_file=str(empty_in),
        group_name="Empty Group",
        office_id="CWMS",
        api_root="https://test.example.com/",
        api_key="test-key",
        dry_run=True,
    )

    output = caplog.text

    # Should log error for no entries
    assert "No timeseries entries found" in output


def test_import_shef_infile_parses_location_mappings(fake_cwms, caplog):
    """Test that location mappings are parsed correctly from the .in file."""
    import logging

    caplog.set_level(logging.INFO)

    fixture_path = Path(__file__).parent / "fixtures" / "exportShef_CWMS_LD8-10.in"

    if not fixture_path.exists():
        pytest.skip(f"Fixture file not found: {fixture_path}")

    import_shef_infile(
        in_file=str(fixture_path),
        group_name="LD8-10 Export",
        office_id="CWMS",
        api_root="https://test.example.com/",
        api_key="test-key",
        dry_run=True,
    )

    output = caplog.text

    # Verify that location mappings were recognized (GENW3, LYNW3, GTTI4)
    # These are the SHEF location IDs from the LOCATION directives
    assert "GENW3" in output or "LYNW3" in output or "GTTI4" in output
