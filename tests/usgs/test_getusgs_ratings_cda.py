from __future__ import annotations

import logging
from json import loads
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("dataretrieval.configuration")

from cwmscli.usgs import getUSGS_ratings_cda as ratings


@pytest.fixture
def exsa_comment() -> str:
    return "\n".join(
        [
            '# //STATION AGENCY="USGS" NUMBER="03275600" TIME_ZONE="EST"',
            '# //RATING SHIFTED="20261006143000 EST"',
            '# //RATING REMARKS="Updated at Abington"',
            "# //RETRIEVED: 2026-10-06 14:35:00",
        ]
    )


@pytest.fixture
def base_comment() -> str:
    return "\n".join(
        [
            '# //STATION AGENCY="USGS" NUMBER="03275600" TIME_ZONE="EST"',
            '# //RATING_DATETIME BEGIN="20190905180000" END="20200526164500"',
            '# //RATING_DATETIME BEGIN="20200526164500" END="--------------"',
            "# //RETRIEVED: 2026-10-06 14:35:00",
        ]
    )


@pytest.fixture
def corr_comment() -> str:
    return "\n".join(
        [
            '# //STATION AGENCY="USGS" NUMBER="03275600" TIME_ZONE="EST"',
            '# //CORR1_PREV BEGIN="20260301000000" END="--------------"',
            "# //RETRIEVED: 2026-10-06 14:35:00",
        ]
    )


@pytest.fixture
def exsa_rating(exsa_comment: str) -> pd.DataFrame:
    rating = pd.DataFrame(
        {
            "INDEP": [1.0, 2.0, 3.0],
            "SHIFT": [0.0, -0.1, -0.1],
            "DEP": [10.0, 30.0, 60.0],
            "STOR": [np.nan, np.nan, "*"],
        }
    )
    rating.attrs["comment"] = exsa_comment
    rating.attrs["url"] = (
        "https://api.waterdata.usgs.gov/stac-files/ratings/" "USGS.03275600.exsa.rdb"
    )
    return rating


@pytest.fixture
def base_rating(base_comment: str) -> pd.DataFrame:
    rating = pd.DataFrame(
        {
            "INDEP": [1.0, 2.0, 3.0],
            "DEP": [10.0, 30.0, 60.0],
            "STOR": [np.nan, np.nan, "*"],
        }
    )
    rating.attrs["comment"] = base_comment
    rating.attrs["url"] = (
        "https://api.waterdata.usgs.gov/stac-files/ratings/" "USGS.03275600.base.rdb"
    )
    return rating


@pytest.fixture
def corr_rating(corr_comment: str) -> pd.DataFrame:
    rating = pd.DataFrame(
        {
            "INDEP": [1.0, 2.0, 3.0, 4.0],
            "CORR": [0.0, 0.0, 0.5, 0.5],
            "CORRINDEP": [1.0, 2.0, 3.5, 4.5],
        }
    )
    rating.attrs["comment"] = corr_comment
    rating.attrs["url"] = (
        "https://api.waterdata.usgs.gov/stac-files/ratings/" "USGS.03275600.corr.rdb"
    )
    return rating


def test_parse_effective_dates_parses_json_array_as_utc_timestamps():
    dates = ratings.parse_effective_dates(
        '["2024-01-01T00:00:00Z", "2025-02-02T12:30:00Z"]'
    )

    assert len(dates) == 2
    assert dates[0] == pd.Timestamp("2024-01-01T00:00:00Z")
    assert dates[1] == pd.Timestamp("2025-02-02T12:30:00Z")


def test_parse_effective_dates_accepts_list_values():
    dates = ratings.parse_effective_dates(
        ["2024-01-01T00:00:00Z", "2025-02-02T12:30:00Z"]
    )

    assert dates == [
        pd.Timestamp("2024-01-01T00:00:00Z"),
        pd.Timestamp("2025-02-02T12:30:00Z"),
    ]


@pytest.mark.parametrize(
    ("abbreviation", "expected"),
    [
        ("EST", "US/Eastern"),
        ("EDT", "US/Eastern"),
        ("CST", "US/Central"),
        ("CDT", "US/Central"),
        ("PST", "US/Pacific"),
        ("UTC", "UTC"),
        ("America/Denver", "America/Denver"),
    ],
)
def test_convert_tz_maps_usgs_time_zone_abbreviations(abbreviation, expected):
    assert ratings.convert_tz(abbreviation) == expected


def test_get_usgs_effective_date_uses_rating_shifted_for_exsa(exsa_comment):
    effective_date = ratings.get_usgs_effective_date(exsa_comment, "EXSA")

    assert effective_date == pd.Timestamp(
        "2026-10-06T14:30:00",
        tz="US/Eastern",
    )


def test_get_usgs_effective_date_accepts_dataretrieval_comment_lines(
    exsa_comment,
):
    effective_date = ratings.get_usgs_effective_date(
        exsa_comment.splitlines(),
        "EXSA",
    )

    assert effective_date == pd.Timestamp(
        "2026-10-06T14:30:00",
        tz="US/Eastern",
    )


def test_get_usgs_effective_date_uses_latest_rating_datetime_begin_for_base(
    base_comment,
):
    effective_date = ratings.get_usgs_effective_date(base_comment, "BASE")

    assert effective_date == pd.Timestamp(
        "2020-05-26T16:45:00",
        tz="US/Eastern",
    )


def test_get_usgs_effective_date_uses_correction_begin_for_corr(corr_comment):
    effective_date = ratings.get_usgs_effective_date(corr_comment, "CORR")

    assert effective_date == pd.Timestamp(
        "2026-03-01T00:00:00",
        tz="US/Eastern",
    )


def test_get_usgs_effective_date_falls_back_to_retrieved_date():
    comment = "\n".join(
        [
            '# //STATION AGENCY="USGS" NUMBER="03275600" TIME_ZONE="EST"',
            "# //RETRIEVED: 2026-10-06 14:35:00",
        ]
    )

    effective_date = ratings.get_usgs_effective_date(comment, "EXSA")

    assert effective_date == pd.Timestamp(
        "2026-10-06T14:35:00",
        tz="US/Eastern",
    )


def test_get_usgs_rating_description_uses_rating_remarks():
    description = ratings.get_usgs_rating_description(
        ['# //RATING REMARKS="Rating shifted for debris"'],
        rating_type="EXSA",
        source_url="https://example.test/rating.rdb",
    )

    assert description == "Rating shifted for debris"


def test_get_usgs_rating_description_falls_back_to_asset_url():
    description = ratings.get_usgs_rating_description(
        [],
        rating_type="EXSA",
        source_url="https://example.test/rating.rdb",
    )

    assert description == "USGS EXSA rating downloaded from https://example.test/rating.rdb"


def test_convert_usgs_rating_df_converts_exsa_to_cwms_simple_rating(
    exsa_rating,
):
    result = ratings.convert_usgs_rating_df(exsa_rating, "EXSA")

    expected = pd.DataFrame({"ind": [1.0, 2.0, 3.0], "dep": [10.0, 30.0, 60.0]})

    pd.testing.assert_frame_equal(result, expected)


def test_convert_usgs_rating_df_converts_base_to_cwms_simple_rating(
    base_rating,
):
    result = ratings.convert_usgs_rating_df(base_rating, "BASE")

    expected = pd.DataFrame({"ind": [1.0, 2.0, 3.0], "dep": [10.0, 30.0, 60.0]})

    pd.testing.assert_frame_equal(result, expected)


def test_convert_usgs_rating_df_reduces_corr_to_first_and_last_values(
    corr_rating,
):
    result = ratings.convert_usgs_rating_df(corr_rating, "CORR")

    expected = pd.DataFrame({"ind": [1.0, 2.0, 3.0, 4.0], "dep": [1.0, 2.0, 3.5, 4.5]})

    pd.testing.assert_frame_equal(result, expected)


def test_get_current_usgs_rating_requests_current_asset_without_time(
    monkeypatch,
    exsa_rating,
):
    captured_kwargs = {}

    def fake_get_ratings(**kwargs):
        captured_kwargs.update(kwargs)
        return {"USGS-03275600.exsa.rdb": exsa_rating}

    monkeypatch.setattr(ratings.waterdata, "get_ratings", fake_get_ratings)

    result = ratings.get_current_usgs_rating(
        usgs_station_number="03275600",
        rating_type="EXSA",
    )

    assert result is exsa_rating
    assert captured_kwargs == {
        "monitoring_location_id": "USGS-03275600",
        "file_type": "exsa",
    }
    assert "time" not in captured_kwargs


def test_get_current_usgs_rating_returns_none_when_usgs_has_no_rating(
    monkeypatch,
):
    monkeypatch.setattr(ratings.waterdata, "get_ratings", lambda **_kwargs: {})

    result = ratings.get_current_usgs_rating(
        usgs_station_number="03275600",
        rating_type="EXSA",
    )

    assert result is None


def test_get_usgs_updated_ratings_returns_only_recent_matching_stac_features(
    monkeypatch,
):
    calls = []

    def fake_get_ratings(**kwargs):
        calls.append(kwargs)

        if kwargs["file_type"] == "exsa":
            return [
                {
                    "id": "USGS-03275600.exsa.rdb",
                    "properties": {
                        "monitoring_location_id": "USGS-03275600",
                        "file_type": "exsa",
                        "datetime": "2026-10-06T14:35:00Z",
                    },
                    "assets": {
                        "data": {
                            "href": (
                                "https://api.waterdata.usgs.gov/stac-files/"
                                "ratings/USGS.03275600.exsa.rdb"
                            )
                        }
                    },
                }
            ]

        return []

    monkeypatch.setattr(ratings.waterdata, "get_ratings", fake_get_ratings)

    configured_ratings = pd.DataFrame(
        {
            "USGS_St_Num": ["03275600", "03328500"],
            "rating-type": ["EXSA", "BASE"],
        }
    )

    result = ratings.get_usgs_updated_ratings(
        ratings=configured_ratings,
        days_back=2,
        chunk_size=25,
    )

    assert len(result) == 1
    assert result.iloc[0]["USGS_St_Num"] == "03275600"
    assert result.iloc[0]["rating-type"] == "EXSA"
    assert result.iloc[0]["date_updated"] == pd.Timestamp("2026-10-06T14:35:00Z")

    assert len(calls) == 2
    exsa_call = next(call for call in calls if call["file_type"] == "exsa")
    base_call = next(call for call in calls if call["file_type"] == "base")

    assert exsa_call["monitoring_location_id"] == ["USGS-03275600"]
    assert base_call["monitoring_location_id"] == ["USGS-03328500"]
    assert exsa_call["download_and_parse"] is False
    assert exsa_call["limit"] == 100
    assert exsa_call["time"][1] is None


def test_getusgs_rating_cda_only_processes_recently_updated_new_specs(
    monkeypatch,
):
    configured_ratings = pd.DataFrame(
        [
            {
                "rating-id": "existing-rating",
                "office-id": "LRL",
                "USGS_St_Num": "11111111",
                "rating-type": "EXSA",
                "effective-dates": '["2024-01-01T00:00:00Z"]',
            },
            {
                "rating-id": "recent-new-rating",
                "office-id": "LRL",
                "USGS_St_Num": "22222222",
                "rating-type": "EXSA",
                "effective-dates": np.nan,
            },
            {
                "rating-id": "stale-new-rating",
                "office-id": "LRL",
                "USGS_St_Num": "33333333",
                "rating-type": "EXSA",
                "effective-dates": np.nan,
            },
        ]
    )
    captured = {}

    monkeypatch.setattr(ratings, "init_cwms_session", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        ratings,
        "get_rating_ids_from_specs",
        lambda office_id: pd.DataFrame(),
    )
    monkeypatch.setattr(
        ratings,
        "get_location_aliases",
        lambda *args, **kwargs: configured_ratings.copy(),
    )

    def fake_get_usgs_updated_ratings(ratings, days_back):
        captured["scanned_ratings"] = ratings.copy()
        captured["days_back"] = days_back
        return pd.DataFrame(
            {
                "USGS_St_Num": ["11111111", "22222222"],
                "rating-type": ["EXSA", "EXSA"],
                "date_updated": pd.to_datetime(
                    ["2026-10-06T00:00:00Z", "2026-10-06T00:00:00Z"],
                    utc=True,
                ),
                "url": ["existing-url", "recent-url"],
            }
        )

    def fake_cwms_write_ratings(updated_ratings, dry_run=False):
        captured["updated_ratings"] = updated_ratings.copy()
        captured["dry_run"] = dry_run

    monkeypatch.setattr(
        ratings,
        "get_usgs_updated_ratings",
        fake_get_usgs_updated_ratings,
    )
    monkeypatch.setattr(ratings, "cwms_write_ratings", fake_cwms_write_ratings)

    ratings.getusgs_rating_cda(
        api_root="https://example.test/cda/",
        office_id="LRL",
        api_key="test-key",
        days_back=2,
        dry_run=True,
    )

    assert captured["days_back"] == 2
    assert set(captured["scanned_ratings"]["rating-id"]) == {
        "existing-rating",
        "recent-new-rating",
        "stale-new-rating",
    }
    assert set(captured["updated_ratings"]["rating-id"]) == {
        "existing-rating",
        "recent-new-rating",
    }
    assert captured["dry_run"] is True


def test_get_usgs_updated_ratings_returns_empty_dataframe_when_no_features(
    monkeypatch,
):
    monkeypatch.setattr(ratings.waterdata, "get_ratings", lambda **_kwargs: [])

    configured_ratings = pd.DataFrame(
        {"USGS_St_Num": ["03275600"], "rating-type": ["EXSA"]}
    )

    result = ratings.get_usgs_updated_ratings(
        ratings=configured_ratings,
        days_back=2,
    )

    assert result.empty
    assert result.columns.tolist() == [
        "USGS_St_Num",
        "rating-type",
        "date_updated",
        "url",
    ]


def test_get_usgs_updated_ratings_chunks_large_site_list(monkeypatch):
    calls = []

    def fake_get_ratings(**kwargs):
        calls.append(kwargs)
        return []

    monkeypatch.setattr(ratings.waterdata, "get_ratings", fake_get_ratings)

    configured_ratings = pd.DataFrame(
        {
            "USGS_St_Num": [f"{number:08d}" for number in range(30)],
            "rating-type": ["EXSA"] * 30,
        }
    )

    ratings.get_usgs_updated_ratings(
        ratings=configured_ratings,
        days_back=2,
        chunk_size=25,
    )

    assert len(calls) == 2
    assert len(calls[0]["monitoring_location_id"]) == 25
    assert len(calls[1]["monitoring_location_id"]) == 5


def test_cwms_write_ratings_stores_new_empty_cwms_spec(
    monkeypatch,
    exsa_rating,
):
    captured = {"rating_builder_kwargs": None, "update_kwargs": None}
    previous_rating_spec = {
        "auto-migrate-extension": True,
        "source-agency": "USGS",
        "version": "prior-rating-version",
    }

    monkeypatch.setattr(
        ratings,
        "get_current_usgs_rating",
        lambda **_kwargs: exsa_rating,
    )

    def fake_rating_simple_df_to_json(**kwargs):
        captured["rating_builder_kwargs"] = kwargs
        return {
            "rating-spec": previous_rating_spec.copy(),
            "simple-rating": {},
        }

    def fake_update_ratings(**kwargs):
        captured["update_kwargs"] = kwargs

    monkeypatch.setattr(
        ratings.cwms,
        "rating_simple_df_to_json",
        fake_rating_simple_df_to_json,
    )
    monkeypatch.setattr(ratings.cwms, "update_ratings", fake_update_ratings)

    updated_ratings = pd.DataFrame(
        [
            {
                "rating-id": "Abington.Stage;Flow.EXSA.USGS-NWIS",
                "office-id": "LRL",
                "USGS_St_Num": "03275600",
                "rating-type": "EXSA",
                "auto-activate": True,
                "auto-migrate-extension": True,
                "cwms_max_effective_date": pd.NaT,
            }
        ]
    )

    ratings.cwms_write_ratings(updated_ratings)

    assert captured["rating_builder_kwargs"] is not None
    assert captured["rating_builder_kwargs"]["rating_id"] == (
        "Abington.Stage;Flow.EXSA.USGS-NWIS"
    )
    assert captured["rating_builder_kwargs"]["office_id"] == "LRL"
    assert captured["rating_builder_kwargs"]["units"] == "ft;cfs"
    assert captured["rating_builder_kwargs"]["active"] is True
    assert captured["update_kwargs"] == {
        "data": {
            "rating-spec": previous_rating_spec,
            "simple-rating": {},
        },
        "rating_id": "Abington.Stage;Flow.EXSA.USGS-NWIS",
    }


def test_cwms_write_ratings_migrates_extension_from_previous_rating(
    monkeypatch,
    exsa_rating,
):
    rating_id = "Abington.Stage;Flow.EXSA.USGS-NWIS"
    cwms_effective_date = pd.Timestamp("2026-10-05T00:00:00Z")
    previous_rating = {
        "rating-spec": {
            "auto-migrate-extension": True,
            "template-id": "Stage;Flow.USGS-EXSA",
        },
        "simple-rating": {
            "rating-points": {"point": [{"ind": 1.0, "dep": 2.0}]},
            "effective-date": cwms_effective_date.isoformat(),
            "create-date": "2026-10-05T00:00:00Z",
            "active": False,
        },
    }
    current_rating = Mock(json=previous_rating)
    captured = {}

    monkeypatch.setattr(
        ratings,
        "get_current_usgs_rating",
        lambda **_kwargs: exsa_rating,
    )
    monkeypatch.setattr(
        ratings.cwms,
        "get_ratings",
        lambda **kwargs: captured.setdefault("get_ratings_kwargs", kwargs)
        and current_rating,
    )
    monkeypatch.setattr(
        ratings.cwms,
        "update_ratings",
        lambda **kwargs: captured.setdefault("update_kwargs", kwargs),
    )

    ratings.cwms_write_ratings(
        pd.DataFrame(
            [
                {
                    "rating-id": rating_id,
                    "office-id": "LRL",
                    "USGS_St_Num": "03275600",
                    "rating-type": "EXSA",
                    "auto-activate": True,
                    "auto-migrate-extension": True,
                    "cwms_max_effective_date": cwms_effective_date,
                }
            ]
        )
    )

    assert captured["get_ratings_kwargs"] == {
        "rating_id": rating_id,
        "office_id": "LRL",
        "begin": cwms_effective_date,
        "end": cwms_effective_date,
        "method": "EAGER",
        "single_rating_df": True,
    }
    update_kwargs = captured["update_kwargs"]
    assert update_kwargs["rating_id"] == rating_id
    assert update_kwargs["data"]["rating-spec"] == previous_rating["rating-spec"]
    assert update_kwargs["data"]["simple-rating"]["rating-points"]["point"] == (
        loads(
            ratings.convert_usgs_rating_df(exsa_rating, "EXSA").to_json(
                orient="records"
            )
        )
    )
    assert update_kwargs["data"]["simple-rating"]["effective-date"] == (
        ratings.get_usgs_effective_date(
            exsa_rating.attrs["comment"], "EXSA"
        ).isoformat()
    )
    assert update_kwargs["data"]["simple-rating"]["description"] == (
        "Updated at Abington"
    )
    assert "create-date" not in update_kwargs["data"]["simple-rating"]
    assert update_kwargs["data"]["simple-rating"]["active"] is True


def test_migrate_extension_fetches_previous_rating_and_preserves_extension_points(
    monkeypatch,
):
    rating_id = "ABRN8.Stage;Flow.USGS-BASE.USGS-NWIS"
    office_id = "MVP"
    cwms_effective_date = pd.Timestamp("2025-06-13T14:15:00Z")
    effective_date = pd.Timestamp("2026-10-07T14:10:00Z")
    extension_points = {
        "point": [
            {"ind": "-0.37", "dep": "0.0"},
            {"ind": "29.0", "dep": "17000.0"},
        ]
    }
    rating_json = {
        "rating-spec": {
            "auto-migrate-extension": True,
            "template-id": "Stage;Flow.USGS-BASE",
        },
        "simple-rating": {
            "effective-date": "2025-06-13T14:15:00Z",
            "create-date": "2026-01-12T16:37:00Z",
            "active": "true",
            "rating-points": {"point": [{"ind": "9.35", "dep": "0.03"}]},
            "extension-points": extension_points,
        },
    }
    cwms_rating = pd.DataFrame(
        {"ind": [9.4, 11.6], "dep": [0.04, 260.0]}
    )
    captured = {}
    monkeypatch.setattr(
        ratings.cwms,
        "get_ratings",
        lambda **kwargs: captured.setdefault("get_ratings_kwargs", kwargs)
        and Mock(json=rating_json),
    )

    updated_rating = ratings.migrate_extension(
        rating_id=rating_id,
        office_id=office_id,
        cwms_effective_date=cwms_effective_date,
        cwms_rating=cwms_rating,
        usgs_effective_date=effective_date,
        active=False,
        description="Current USGS remarks",
    )

    assert captured["get_ratings_kwargs"] == {
        "rating_id": rating_id,
        "office_id": office_id,
        "begin": cwms_effective_date,
        "end": cwms_effective_date,
        "method": "EAGER",
        "single_rating_df": True,
    }
    simple_rating = updated_rating["simple-rating"]
    assert updated_rating["rating-spec"]["auto-migrate-extension"] is True
    assert simple_rating["extension-points"] == extension_points
    assert simple_rating["rating-points"]["point"] == [
        {"ind": 9.4, "dep": 0.04},
        {"ind": 11.6, "dep": 260.0},
    ]
    assert simple_rating["effective-date"] == effective_date.isoformat()
    assert "create-date" not in simple_rating
    assert simple_rating["active"] is False
    assert simple_rating["description"] == "Current USGS remarks"


def test_cwms_write_ratings_skips_storage_when_effective_date_matches(
    monkeypatch,
    exsa_rating,
):
    update_calls = []

    monkeypatch.setattr(
        ratings,
        "get_current_usgs_rating",
        lambda **_kwargs: exsa_rating,
    )
    monkeypatch.setattr(
        ratings.cwms,
        "rating_simple_df_to_json",
        lambda **_kwargs: {"rating-spec": {}, "simple-rating": {}},
    )
    monkeypatch.setattr(
        ratings.cwms,
        "update_ratings",
        lambda **kwargs: update_calls.append(kwargs),
    )

    updated_ratings = pd.DataFrame(
        [
            {
                "rating-id": "Abington.Stage;Flow.EXSA.USGS-NWIS",
                "office-id": "LRL",
                "USGS_St_Num": "03275600",
                "rating-type": "EXSA",
                "auto-activate": True,
                "auto-migrate-extension": False,
                "cwms_max_effective_date": pd.Timestamp("2026-10-06T18:30:00Z"),
            }
        ]
    )

    ratings.cwms_write_ratings(updated_ratings)

    assert update_calls == []


def test_cwms_write_ratings_logs_missing_usgs_rating_without_storing(
    monkeypatch,
):
    update_calls = []

    monkeypatch.setattr(
        ratings,
        "get_current_usgs_rating",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        ratings.cwms,
        "update_ratings",
        lambda **kwargs: update_calls.append(kwargs),
    )

    updated_ratings = pd.DataFrame(
        [
            {
                "rating-id": "Abington.Stage;Flow.EXSA.USGS-NWIS",
                "office-id": "LRL",
                "USGS_St_Num": "03275600",
                "rating-type": "EXSA",
                "auto-activate": True,
                "auto-migrate-extension": False,
                "cwms_max_effective_date": pd.NaT,
            }
        ]
    )

    ratings.cwms_write_ratings(updated_ratings)

    assert update_calls == []


def test_cwms_write_ratings_dry_run_prepares_but_does_not_store(
    monkeypatch,
    caplog,
):
    caplog.set_level(logging.INFO)

    rating_id = "TEST.Stage;Flow.USGS-EXSA"
    rating_data = pd.DataFrame({"ind": [1.0], "dep": [2.0]})
    effective_date = pd.Timestamp("2025-01-01", tz="UTC")
    rating_payload = {
        "rating-spec": {"auto-migrate-extension": False},
        "simple-rating": {},
    }
    update_ratings = Mock()

    monkeypatch.setattr(
        ratings,
        "get_current_usgs_rating",
        lambda **_kwargs: rating_data,
    )
    monkeypatch.setattr(
        ratings,
        "get_usgs_effective_date",
        lambda **_kwargs: effective_date,
    )
    monkeypatch.setattr(
        ratings,
        "convert_usgs_rating_df",
        lambda *_args: rating_data,
    )
    monkeypatch.setattr(
        ratings.cwms,
        "rating_simple_df_to_json",
        Mock(return_value=rating_payload),
    )
    monkeypatch.setattr(
        ratings.cwms,
        "update_ratings",
        update_ratings,
    )

    ratings.cwms_write_ratings(
        pd.DataFrame(
            [
                {
                    "rating-id": rating_id,
                    "USGS_St_Num": "12345678",
                    "rating-type": "EXSA",
                    "cwms_max_effective_date": pd.NaT,
                    "office-id": "SPL",
                    "auto-activate": False,
                    "auto-migrate-extension": False,
                }
            ]
        ),
        dry_run=True,
    )

    ratings.cwms.rating_simple_df_to_json.assert_called_once()
    update_ratings.assert_not_called()
    assert f"DRY RUN: Would store USGS EXSA rating for {rating_id}" in caplog.text
