import pandas as pd
import pytest
from click.testing import CliRunner

import cwmscli.load.location.location_ids as location_ids_module
from cwmscli.load.location.location import location as location_group


def test_load_locations_prefers_saved_token_for_target(monkeypatch):
    calls = []

    monkeypatch.setattr(
        "cwmscli.utils.get_saved_login_token", lambda *args, **kwargs: "saved-token"
    )

    class FakeCatalogResponse:
        df = pd.DataFrame([{"name": "LOC_A"}])

    class FakeLocationResponse:
        json = [{"name": "LOC_A", "active": True}]

    class FakeCwms:
        @staticmethod
        def init_session(api_root, api_key=None, token=None):
            calls.append(("init_session", api_root, api_key, token))

        @staticmethod
        def get_locations_catalog(**kwargs):
            return FakeCatalogResponse()

        @staticmethod
        def get_locations(**kwargs):
            return FakeLocationResponse()

        @staticmethod
        def store_location(data, fail_if_exists=False):
            return {"stored": data["name"]}

    monkeypatch.setattr(location_ids_module, "cwms", FakeCwms)

    location_ids_module.load_locations(
        source_cda="https://source.example/cwms-data",
        source_office="SWT",
        target_cda="http://localhost:8082/cwms-data",
        target_api_key="apikey 123",
        verbose=0,
        dry_run=False,
        like="LOC*",
        location_kind_like=["PROJECT"],
    )

    assert calls[0] == (
        "init_session",
        "https://source.example/cwms-data",
        None,
        "saved-token",
    )
    assert calls[1] == (
        "init_session",
        "http://localhost:8082/cwms-data",
        None,
        "saved-token",
    )


def test_load_locations_uses_catalog_matches_to_fetch_full_records(monkeypatch):
    monkeypatch.setattr(
        "cwmscli.utils.get_saved_login_token", lambda *args, **kwargs: None
    )
    calls = []
    stored = []

    class FakeCatalogResponse:
        df = pd.DataFrame([{"name": "LOC_A"}, {"name": "LOC_B"}])

    class FakeLocationResponse:
        def __init__(self, location_id):
            self.json = [{"name": location_id, "active": True}]

    class FakeCwms:
        @staticmethod
        def init_session(api_root, api_key=None):
            calls.append(("init_session", api_root, api_key))

        @staticmethod
        def get_locations_catalog(**kwargs):
            calls.append(("get_locations_catalog", kwargs))
            return FakeCatalogResponse()

        @staticmethod
        def get_locations(**kwargs):
            calls.append(("get_locations", kwargs))
            return FakeLocationResponse(kwargs["location_ids"].strip("^$"))

        @staticmethod
        def store_location(data, fail_if_exists=False):
            stored.append((data["name"], fail_if_exists))
            return {"stored": data["name"]}

    monkeypatch.setattr(location_ids_module, "cwms", FakeCwms)

    location_ids_module.load_locations(
        source_cda="https://source.example/cwms-data",
        source_office="SWT",
        target_cda="http://localhost:8082/cwms-data",
        target_api_key="apikey 123",
        verbose=0,
        dry_run=False,
        like="LOC*",
        location_kind_like=["PROJECT"],
    )

    catalog_calls = [call for call in calls if call[0] == "get_locations_catalog"]
    assert catalog_calls == [
        (
            "get_locations_catalog",
            {"office_id": "SWT", "like": "LOC*", "location_kind_like": "PROJECT"},
        )
    ]

    get_location_calls = [call for call in calls if call[0] == "get_locations"]
    assert get_location_calls == [
        ("get_locations", {"office_id": "SWT", "location_ids": "^LOC_A$"}),
        ("get_locations", {"office_id": "SWT", "location_ids": "^LOC_B$"}),
    ]
    assert stored == [("LOC_A", False), ("LOC_B", False)]


def test_target_csv_writes_locations_and_skips_store(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "cwmscli.utils.get_saved_login_token", lambda *args, **kwargs: None
    )
    stored = []

    class FakeLocationResponse:
        json = [
            {"name": "LOC_A", "office-id": "SWT", "active": True, "latitude": 36.1},
            {"name": "LOC_B", "office-id": "SWT", "active": True, "latitude": 36.2},
        ]

    class FakeCwms:
        @staticmethod
        def init_session(api_root, api_key=None):
            pass

        @staticmethod
        def get_locations(**kwargs):
            return FakeLocationResponse()

        @staticmethod
        def store_location(data, fail_if_exists=False):
            stored.append(data["name"])

    monkeypatch.setattr(location_ids_module, "cwms", FakeCwms)

    out = tmp_path / "out.csv"
    location_ids_module.load_locations(
        source_cda="https://source.example/cwms-data",
        source_office="SWT",
        target_cda=None,
        target_api_key=None,
        verbose=0,
        dry_run=False,
        like=None,
        location_kind_like=["ALL"],
        target_csv=str(out),
    )

    assert stored == []
    df = pd.read_csv(out)
    assert df["name"].tolist() == ["LOC_A", "LOC_B"]
    assert "office-id" in df.columns
    # no anonymous index column leaks in
    assert "Unnamed: 0" not in df.columns


def test_source_csv_reads_and_calls_store_per_row(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "cwmscli.utils.get_saved_login_token", lambda *args, **kwargs: "saved-token"
    )
    stored = []

    src = tmp_path / "in.csv"
    pd.DataFrame(
        [
            {"name": "FROM_CSV_A", "office-id": "SWT", "active": True, "latitude": 1.0},
            {"name": "FROM_CSV_B", "office-id": "SWT", "active": True, "latitude": 2.0},
        ]
    ).to_csv(src, index=False)

    class FakeCwms:
        @staticmethod
        def init_session(api_root, api_key=None, token=None):
            pass

        @staticmethod
        def store_location(data, fail_if_exists=False):
            stored.append((data["name"], data["active"], data.get("latitude")))

    monkeypatch.setattr(location_ids_module, "cwms", FakeCwms)

    location_ids_module.load_locations(
        source_cda=None,
        source_office=None,
        target_cda="http://localhost:8082/cwms-data",
        target_api_key=None,
        verbose=0,
        dry_run=False,
        like=None,
        location_kind_like=["ALL"],
        source_csv=str(src),
    )

    assert stored == [
        ("FROM_CSV_A", True, 1.0),
        ("FROM_CSV_B", True, 2.0),
    ]


def test_cli_rejects_source_csv_and_target_csv_together(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "cwmscli.utils.get_saved_login_token", lambda *args, **kwargs: None
    )
    src = tmp_path / "in.csv"
    src.write_text("name,office-id,active\nLOC_A,SWT,True\n")
    out = tmp_path / "out.csv"

    runner = CliRunner()
    result = runner.invoke(
        location_group,
        [
            "ids-all",
            "--source-csv",
            str(src),
            "--target-csv",
            str(out),
        ],
    )
    assert result.exit_code != 0
    assert (
        "no CDA is involved" in result.output or "mutually exclusive" in result.output
    )


def test_cli_rejects_source_csv_with_explicit_source_cda(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "cwmscli.utils.get_saved_login_token", lambda *args, **kwargs: None
    )
    src = tmp_path / "in.csv"
    src.write_text("name,office-id,active\nLOC_A,SWT,True\n")

    runner = CliRunner()
    result = runner.invoke(
        location_group,
        [
            "ids-all",
            "--source-csv",
            str(src),
            "--source-cda",
            "https://override.example/cwms-data",
            "--target-cda",
            "http://localhost:8082/cwms-data",
            "--target-api-key",
            "k",
        ],
    )
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output
