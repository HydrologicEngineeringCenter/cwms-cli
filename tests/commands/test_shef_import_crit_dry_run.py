import json
import sys
import types
from io import StringIO
from pathlib import Path

import pytest
from click.testing import CliRunner

from cwmscli.commands.shef.import_critfile import import_shef_critfile


@pytest.fixture
def fake_cwms(monkeypatch):
    """Mock the cwms module for testing."""
    fake_cwms_module = types.ModuleType("cwms")

    # Create a fake api submodule
    fake_api = types.ModuleType("api")

    def fake_init_session(api_root, api_key):
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
            "members": data.to_dict("records")[0],
        }

    fake_cwms_module.timeseries_group_df_to_json = fake_timeseries_group_df_to_json

    # Mock update_timeseries_groups
    def fake_update_timeseries_groups(group_id, office_id, replace_assigned_ts, data):
        pass

    fake_cwms_module.update_timeseries_groups = fake_update_timeseries_groups

    monkeypatch.setitem(sys.modules, "cwms", fake_cwms_module)
    return fake_cwms_module


@pytest.fixture
def crit_file(tmp_path):
    """Create a test crit file."""
    crit_content = """#stopStream and startStream for this criteria file to put in memory
#
# The criteria file is grouped by NESDIS Transmit ID
# SHEFIT criteria for a data path:
# NESDISID.SHEFCODE.RZZ.INTERVAL=location.parameter.parameter-type.interval.duration.version
#
# INTERVAL is one of the following and must match 'interval':
#  0 is Instantaneous data
#  0015 is 15 minute data
#  0030 is 30 minute data
#  1001 is Hourly data
#  1006 is Six hour data
#
#############################################################################################
#
# Souris River near Sherwood, ND
#
1636FAA0.VB.RZZ.0015=Sherwood.Volt.Inst.15Minutes.0.CEMVP-GOES-Raw;TZ=UTC;DLTime=false;Units=volt
1636FAA0.H2.RZZ.0015=Sherwood.Stage.Inst.15Minutes.0.CEMVP-GOES-Raw;TZ=UTC;DLTime=false;Units=ft
1636FAA0.TW.RZZ.0015=Sherwood.Temp-Water.Inst.15Minutes.0.CEMVP-GOES-Raw;TZ=UTC;DLTime=false;Units=C
#
# Sheyenne River at Valley City, ND
#
163EE3A2.VB.RZZ.0015=VCRN8.Volt.Inst.15Minutes.0.CEMVP-GOES-Raw;TZ=UTC;DLTime=false;Units=volt
163EE3A2.H3.RZZ.0015=VCRN8.Stage.Inst.15Minutes.0.CEMVP-GOES-Raw;TZ=UTC;DLTime=false;Units=ft
#
# Mississippi River near Willow Beach, MN
#
17023384.HG.RZZ.0015=WILM5.Stage.Inst.15Minutes.0.CEMVP-GOES-Raw;TZ=UTC;DLTime=false;Units=ft
17023384.VB.RZZ.1001=WILM5.Volt.Inst.1Hour.0.CEMVP-GOES-Raw;TZ=UTC;DLTime=false;Units=volt
"""
    crit_file = tmp_path / "test.crit"
    crit_file.write_text(crit_content, encoding="utf-8")
    return str(crit_file)


def test_import_shef_critfile_dry_run(fake_cwms, crit_file, caplog):
    """Test that import_shef_critfile with dry_run logs timeseries entries without making API calls."""
    import logging

    caplog.set_level(logging.INFO)

    import_shef_critfile(
        file_path=crit_file,
        office_id="CWMS",
        api_root="https://test.example.com/",
        api_key="test-key",
        group_id="SHEF Data Acquisition",
        category_id="Data Acquisition",
        dry_run=True,
    )

    output = caplog.text

    # Verify dry run output contains expected markers
    assert (
        "--- DRY RUN: The following timeseries entries will be added to SHEF Data Acquisition ---"
        in output
    )
    assert "--- Dry run complete. Nothing was posted to the API. ---" in output

    # Verify timeseries-id and alias-id are logged
    assert "timeseries-id:" in output
    assert "alias-id:" in output
    assert "Sherwood.Volt" in output
    assert "1636FAA0.VB.RZZ.0015" in output


def test_import_shef_critfile_dry_run_parses_all_entries(fake_cwms, crit_file, caplog):
    """Test that all entries from the crit file are logged in dry run mode."""
    import logging

    caplog.set_level(logging.INFO)

    import_shef_critfile(
        file_path=crit_file,
        office_id="CWMS",
        api_root="https://test.example.com/",
        api_key="test-key",
        group_id="SHEF Data Acquisition",
        category_id="Data Acquisition",
        dry_run=True,
    )

    output = caplog.text

    # Count the number of entries displayed
    # The crit file has 7 uncommented data lines
    timeseries_count = output.count("timeseries-id:")
    assert (
        timeseries_count == 7
    ), f"Expected 7 entries in output, found {timeseries_count}"


def test_import_shef_critfile_dry_run_no_api_call(fake_cwms, crit_file, monkeypatch):
    """Test that API session is not initialized in dry run mode."""

    init_called = []
    original_init = fake_cwms.api.init_session

    def tracked_init_session(api_root, api_key):
        init_called.append(True)
        return original_init(api_root, api_key)

    monkeypatch.setattr(fake_cwms.api, "init_session", tracked_init_session)

    import_shef_critfile(
        file_path=crit_file,
        office_id="CWMS",
        api_root="https://test.example.com/",
        api_key="test-key",
        group_id="SHEF Data Acquisition",
        category_id="Data Acquisition",
        dry_run=True,
    )

    # Verify init_session was NOT called during dry run
    assert (
        len(init_called) == 0
    ), "API session should not be initialized in dry run mode"


def test_import_shef_critfile_dry_run_with_empty_file(fake_cwms, tmp_path, caplog):
    """Test dry run behavior with an empty crit file."""
    import logging

    caplog.set_level(logging.INFO)

    empty_crit = tmp_path / "empty.crit"
    empty_crit.write_text("# Just a comment\n", encoding="utf-8")

    import_shef_critfile(
        file_path=str(empty_crit),
        office_id="CWMS",
        api_root="https://test.example.com/",
        api_key="test-key",
        group_id="SHEF Data Acquisition",
        category_id="Data Acquisition",
        dry_run=True,
    )

    output = caplog.text

    # Should log error for no entries
    assert "No timeseries entries found" in output


def test_import_shef_critfile_dry_run_with_commented_lines(fake_cwms, tmp_path, caplog):
    """Test that commented lines in crit file are properly ignored."""
    import logging

    caplog.set_level(logging.INFO)

    crit_content = """#1636FAA0.VB.RZZ.0015=Sherwood.Volt.Inst.15Minutes.0.CEMVP-GOES-Raw;TZ=UTC;DLTime=false;Units=volt
1636FAA0.H2.RZZ.0015=Sherwood.Stage.Inst.15Minutes.0.CEMVP-GOES-Raw;TZ=UTC;DLTime=false;Units=ft
#1636FAA0.TW.RZZ.0015=Sherwood.Temp-Water.Inst.15Minutes.0.CEMVP-GOES-Raw;TZ=UTC;DLTime=false;Units=C
"""
    crit_file = tmp_path / "commented.crit"
    crit_file.write_text(crit_content, encoding="utf-8")

    import_shef_critfile(
        file_path=str(crit_file),
        office_id="CWMS",
        api_root="https://test.example.com/",
        api_key="test-key",
        group_id="SHEF Data Acquisition",
        category_id="Data Acquisition",
        dry_run=True,
    )

    output = caplog.text

    # Should only have 1 entry (the uncommented one)
    assert output.count("timeseries-id:") == 1, "Should only have 1 uncommented entry"


def test_import_shef_critfile_dry_run_with_cemvp_fixture(fake_cwms, caplog):
    """Test dry_run with the actual CEMVP.crit fixture file."""
    import logging

    caplog.set_level(logging.INFO)

    fixture_path = Path(__file__).parent / "fixtures" / "CEMVP.crit"

    # Skip test if fixture doesn't exist
    if not fixture_path.exists():
        pytest.skip(f"Fixture file not found: {fixture_path}")

    import_shef_critfile(
        file_path=str(fixture_path),
        office_id="CWMS",
        api_root="https://test.example.com/",
        api_key="test-key",
        group_id="SHEF Data Acquisition",
        category_id="Data Acquisition",
        dry_run=True,
    )

    output = caplog.text

    # Verify dry run output contains expected markers
    assert (
        "--- DRY RUN: The following timeseries entries will be added to SHEF Data Acquisition ---"
        in output
    )
    assert "--- Dry run complete. Nothing was posted to the API. ---" in output

    # Count entries from the CEMVP file
    # The fixture has 16 uncommented data lines
    timeseries_count = output.count("timeseries-id:")
    assert (
        timeseries_count == 16
    ), f"Expected 16 entries from CEMVP.crit, found {timeseries_count}"

    # Verify specific CEMVP location names are present
    assert "Sherwood" in output
    assert "VCRN8" in output
    assert "WILM5" in output
    assert "DRTN8" in output
    assert "LockDam_06" in output

    # Verify timeseries-id and alias-id format is present
    assert "timeseries-id:" in output
    assert "alias-id:" in output


def test_shef_import_crit_cli_dry_run_flag(fake_cwms, monkeypatch):
    """Test that the CLI --dry-run flag is properly passed to the import function."""

    from cwmscli.__main__ import cli

    fixture_path = Path(__file__).parent / "fixtures" / "CEMVP.crit"

    # Skip test if fixture doesn't exist
    if not fixture_path.exists():
        pytest.skip(f"Fixture file not found: {fixture_path}")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "shef",
            "import_crit",
            "-f",
            str(fixture_path),
            "-o",
            "CWMS",
            "-a",
            "https://test.example.com/",
            "-k",
            "test-key",
            "--dry-run",
        ],
    )

    # Verify command succeeded
    assert result.exit_code == 0, f"Command failed with output: {result.output}"

    # Verify dry run output
    assert (
        "--- DRY RUN: The following timeseries entries will be added to SHEF Data Acquisition ---"
        in result.output
    )
    assert "--- Dry run complete. Nothing was posted to the API. ---" in result.output
    assert "timeseries-id:" in result.output
    assert "alias-id:" in result.output
