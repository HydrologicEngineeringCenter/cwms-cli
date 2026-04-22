import pandas as pd

import cwmscli.load.location.location_ids as location_ids_module


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
