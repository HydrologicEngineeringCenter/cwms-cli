import pandas as pd

import cwmscli.load.location.location_ids_bygroup as location_ids_bygroup_module


def test_copy_from_group_uses_combined_exact_regex_and_dry_run(monkeypatch):
    calls = []

    class FakeGroupResponse:
        df = pd.DataFrame(
            [
                {"location-id": "Black Butte-Outflow", "office-id": "SPK"},
                {"location-id": "Black Butte-Pool", "office-id": "SPK"},
            ]
        )

    class FakeLocationsResponse:
        df = pd.DataFrame(
            [{"name": "Black Butte-Outflow"}, {"name": "Black Butte-Pool"}]
        )
        json = [
            {"name": "Black Butte-Outflow", "active": True},
            {"name": "Black Butte-Pool", "active": True},
        ]

    class FakeCwms:
        @staticmethod
        def init_session(api_root, api_key=None):
            calls.append(("init_session", api_root, api_key))

        @staticmethod
        def get_location_group(**kwargs):
            calls.append(("get_location_group", kwargs))
            return FakeGroupResponse()

        @staticmethod
        def get_locations(**kwargs):
            calls.append(("get_locations", kwargs))
            return FakeLocationsResponse()

        @staticmethod
        def store_location(data, fail_if_exists=False):
            calls.append(("store_location", data["name"], fail_if_exists))

    monkeypatch.setattr(location_ids_bygroup_module, "cwms", FakeCwms)

    location_ids_bygroup_module.copy_from_group(
        source_cda="https://source.example/cwms-data",
        source_office="SPK",
        target_cda="http://localhost:8082/cwms-data",
        target_api_key="apikey 123",
        verbose=0,
        group_id="Sacramento River",
        category_id="Basin",
        group_office_id="SPK",
        category_office_id="SPK",
        filter_office=True,
        dry_run=True,
    )

    assert [call for call in calls if call[0] == "get_location_group"] == [
        (
            "get_location_group",
            {
                "loc_group_id": "Sacramento River",
                "category_id": "Basin",
                "office_id": "SPK",
                "group_office_id": "SPK",
                "category_office_id": "SPK",
            },
        )
    ]
    assert [call for call in calls if call[0] == "get_locations"] == [
        (
            "get_locations",
            {
                "office_id": "SPK",
                "location_ids": "^(Black\\ Butte\\-Outflow|Black\\ Butte\\-Pool)$",
            },
        )
    ]
    assert not [call for call in calls if call[0] == "store_location"]
