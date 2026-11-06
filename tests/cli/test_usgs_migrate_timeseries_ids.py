from types import SimpleNamespace

import pandas as pd
import pytest

import cwmscli.usgs.migrate_usgs_tsid as migration


def test_migrate_usgs_timeseries_ids_defaults_to_dry_run(monkeypatch, tmp_path):
    """
    Verify the public migration routine creates dry-run options by default.

    This does not make CWMS or USGS requests because run_migration is mocked.
    """

    captured = {}

    def fake_run_migration(options):
        captured["options"] = options

    monkeypatch.setattr(
        migration,
        "run_migration",
        fake_run_migration,
    )

    output_dir = tmp_path / "migration_output"

    migration.migrate_usgs_timeseries_ids(
        api_root="https://example.test/cda/",
        office_id="SPL",
        api_key="test-api-key",
        output_dir=str(output_dir),
    )

    options = captured["options"]

    assert isinstance(options, SimpleNamespace)
    assert options.api_root == "https://example.test/cda/"
    assert options.office == "SPL"
    assert options.api_key == "test-api-key"
    assert options.output_dir == str(output_dir)

    # Default behavior must not update CWMS.
    assert options.apply is False

    assert options.legacy_methods_csv is None
    assert options.timeseries_ids is None
    assert options.legacy_chunk_size == 100


def test_migrate_usgs_timeseries_ids_preserves_internal_spaces(
    monkeypatch,
    tmp_path,
):
    """
    Verify supplied TSIDs are passed through unchanged.

    CWMS location IDs may contain spaces, so the migration routine must not
    modify the contents of a TSID.
    """

    captured = {}

    def fake_run_migration(options):
        captured["options"] = options

    monkeypatch.setattr(
        migration,
        "run_migration",
        fake_run_migration,
    )

    tsids = [
        "Prado DS-SAR.Flow.Inst.0.0.usgs-raw",
        "Other Location.Stage.Inst.0.0.usgs-raw",
    ]

    migration.migrate_usgs_timeseries_ids(
        api_root="https://example.test/cda/",
        office_id="SPL",
        api_key="test-api-key",
        output_dir=str(tmp_path / "migration_output"),
        timeseries_ids=tsids,
    )

    options = captured["options"]

    assert options.office == "SPL"
    assert options.timeseries_ids == [
        "Prado DS-SAR.Flow.Inst.0.0.usgs-raw",
        "Other Location.Stage.Inst.0.0.usgs-raw",
    ]


def test_migrate_usgs_timeseries_ids_apply_passed_through(
    monkeypatch,
    tmp_path,
):
    """
    Verify apply=True is forwarded to the migration workflow.
    """

    captured = {}

    def fake_run_migration(options):
        captured["options"] = options

    monkeypatch.setattr(
        migration,
        "run_migration",
        fake_run_migration,
    )

    migration.migrate_usgs_timeseries_ids(
        api_root="https://example.test/cda/",
        office_id="LRL",
        api_key="test-api-key",
        output_dir=str(tmp_path / "migration_output"),
        apply=True,
    )

    options = captured["options"]

    assert options.office == "LRL"
    assert options.apply is True


def test_migrate_usgs_timeseries_ids_legacy_csv_and_chunk_size_passed_through(
    monkeypatch,
    tmp_path,
):
    """
    Verify optional legacy crosswalk and request chunk settings are preserved.
    """

    captured = {}

    def fake_run_migration(options):
        captured["options"] = options

    monkeypatch.setattr(
        migration,
        "run_migration",
        fake_run_migration,
    )

    legacy_csv = tmp_path / "legacy_methods.csv"
    legacy_csv.write_text(
        "USGS_St_Num,USGS_PARAMETER,methodID,methodDescription\n"
        '03309000,00065,220645,"[Gage height]"\n',
        encoding="utf-8",
    )

    migration.migrate_usgs_timeseries_ids(
        api_root="https://example.test/cda/",
        office_id="LRL",
        api_key="test-api-key",
        output_dir=str(tmp_path / "migration_output"),
        legacy_methods_csv=str(legacy_csv),
        legacy_chunk_size=25,
    )

    options = captured["options"]

    assert options.legacy_methods_csv == str(legacy_csv)
    assert options.legacy_chunk_size == 25


def test_migrate_usgs_timeseries_ids_rejects_invalid_chunk_size(tmp_path):
    """
    A zero or negative station chunk size would create an invalid request loop.
    """

    with pytest.raises(
        ValueError,
        match="legacy_chunk_size must be at least 1",
    ):
        migration.migrate_usgs_timeseries_ids(
            api_root="https://example.test/cda/",
            office_id="LRL",
            api_key="test-api-key",
            output_dir=str(tmp_path / "migration_output"),
            legacy_chunk_size=0,
        )


def test_format_legacy_method_description_with_both_fields():
    """
    Legacy WaterServices formatting combines sublocation and web description.
    """

    result = migration.format_legacy_method_description(
        "Below structure",
        "Discharge",
    )

    assert result == "Below structure, [Discharge]"


def test_format_legacy_method_description_with_sublocation_only():
    """A sublocation-only value has no comma or brackets."""

    result = migration.format_legacy_method_description(
        "Below structure",
        None,
    )

    assert result == "Below structure"


def test_format_legacy_method_description_with_web_description_only():
    """A web-description-only value is enclosed in brackets."""

    result = migration.format_legacy_method_description(
        None,
        "Gage height",
    )

    assert result == "[Gage height]"


def test_create_update_plan_includes_only_unambiguous_matches():
    """
    Only exact one-to-one matches are eligible for CWMS alias-id updates.
    """

    crosswalk = pd.DataFrame(
        [
            {
                "office-id": "LRL",
                "timeseries-id": ("MammothCave.Stage.Inst.15Minutes.0.USGS-raw"),
                "time_series_id": "f38a57ccac5a426e8388b8507fa9bbce",
                "mapping_status": "matched",
            },
            {
                "office-id": "LRL",
                "timeseries-id": ("Olmsted-TW.Stage.Inst.15Minutes.0.USGS-raw"),
                "time_series_id": "c26ccd8dfe3c4b91918bb37662711683",
                "mapping_status": "ambiguous_multiple_new_time_series_ids",
            },
            {
                "office-id": "LRL",
                "timeseries-id": ("SmithlandDam-TW.Stage.Inst.15Minutes.0.USGS-raw"),
                "time_series_id": None,
                "mapping_status": "no_new_metadata_description_match",
            },
        ]
    )

    update_plan = migration.create_update_plan(crosswalk)

    assert len(update_plan) == 1

    assert update_plan.iloc[0]["timeseries-id"] == (
        "MammothCave.Stage.Inst.15Minutes.0.USGS-raw"
    )

    assert update_plan.iloc[0]["new_alias_id"] == ("f38a57ccac5a426e8388b8507fa9bbce")


def test_build_patch_dataframe_preserves_existing_attribute():
    """
    The migration must retain the existing CWMS group attribute field and
    replace only alias-id.
    """

    current_group = pd.DataFrame(
        [
            {
                "office-id": "LRL",
                "timeseries-id": ("MammothCave.Stage.Inst.15Minutes.0.USGS-raw"),
                "alias-id": "220645",
                "attribute": "00065",
                "ts-code": 12345,
            },
            {
                "office-id": "LRL",
                "timeseries-id": ("MammothCave.Flow.Inst.15Minutes.0.USGS-raw"),
                "alias-id": "244087",
                "attribute": "00060",
                "ts-code": 12346,
            },
        ]
    )

    update_plan = pd.DataFrame(
        [
            {
                "office-id": "LRL",
                "timeseries-id": ("MammothCave.Stage.Inst.15Minutes.0.USGS-raw"),
                "new_alias_id": "f38a57ccac5a426e8388b8507fa9bbce",
            }
        ]
    )

    patch_df = migration.build_patch_dataframe(
        current_group=current_group,
        update_plan=update_plan,
    )

    assert len(patch_df) == 1

    assert patch_df.iloc[0]["office-id"] == "LRL"

    assert patch_df.iloc[0]["timeseries-id"] == (
        "MammothCave.Stage.Inst.15Minutes.0.USGS-raw"
    )

    # New USGS API identifier replaces legacy methodID.
    assert patch_df.iloc[0]["alias-id"] == ("f38a57ccac5a426e8388b8507fa9bbce")

    # Existing CWMS parameter override is retained.
    assert patch_df.iloc[0]["attribute"] == "00065"

    # Existing CWMS TS code is retained when present.
    assert patch_df.iloc[0]["ts-code"] == 12345


def test_build_crosswalk_matches_legacy_description_to_new_timeseries_id():
    """
    Verify exact matching from old methodDescription to reconstructed new
    metadata description produces a safe matched status.
    """

    configured_ts = pd.DataFrame(
        [
            {
                "office-id": "LRL",
                "timeseries-id": ("MammothCave.Stage.Inst.15Minutes.0.USGS-raw"),
                "USGS_St_Num": "03309000",
                "USGS_PARAMETER": "00065",
                "USGS_Method_TS": "220645",
            }
        ]
    )

    legacy_methods = pd.DataFrame(
        [
            {
                "USGS_St_Num": "03309000",
                "USGS_PARAMETER": "00065",
                "methodID": "220645",
                "methodDescription": "[Gage height]",
            }
        ]
    )

    new_metadata = pd.DataFrame(
        [
            {
                "monitoring_location_id": "USGS-03309000",
                "USGS_PARAMETER": "00065",
                "time_series_id": "f38a57ccac5a426e8388b8507fa9bbce",
                "sublocation_identifier": None,
                "web_description": "Gage height",
                "reconstructed_method_description": "[Gage height]",
                "reconstructed_method_description_normalized": "[gage height]",
            }
        ]
    )

    crosswalk = migration.build_crosswalk(
        configured_ts=configured_ts,
        legacy_methods=legacy_methods,
        new_metadata=new_metadata,
    )

    assert len(crosswalk) == 1

    assert crosswalk.iloc[0]["mapping_status"] == "matched"

    assert crosswalk.iloc[0]["time_series_id"] == ("f38a57ccac5a426e8388b8507fa9bbce")

    assert crosswalk.iloc[0]["new_time_series_id_count"] == 1
