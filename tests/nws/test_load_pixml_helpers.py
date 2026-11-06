import gzip
import json
import logging
import zipfile
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from xml.etree import ElementTree as ET

import pandas as pd
import pytest

import cwmscli.nws.load_pixml as mod

NS = {"pi": mod.DEFAULT_PI_NAMESPACE}


@pytest.mark.parametrize(
    ("input_", "expected"),
    [
        ("/tmp/forecast.xml", "forecast.xml"),
        (
            "https://example.test/products/forecast.xml?download=1#latest",
            "forecast.xml",
        ),
    ],
)
def test_basename(input_, expected):
    assert mod._basename(input_) == expected


def test_fetch_xml_reads_extensionless_and_case_insensitive_archives(tmp_path):
    xml = b"<TimeSeries/>"
    raw_path = tmp_path / "forecast"
    raw_path.write_bytes(xml)
    gzip_path = tmp_path / "forecast.XML.GZ"
    with gzip.open(gzip_path, "wb") as stream:
        stream.write(xml)
    zip_path = tmp_path / "forecast.ZIP"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("forecast.xml", xml)

    assert mod.fetch_xml(str(raw_path)) == xml
    assert mod.fetch_xml(str(gzip_path)) == xml
    assert mod.fetch_xml(str(zip_path)) == xml


def test_document_timezone_parses_fractional_offset():
    root = ET.fromstring(
        f'<TimeSeries xmlns="{mod.DEFAULT_PI_NAMESPACE}"><timeZone>-5.5</timeZone>'
        "</TimeSeries>"
    )

    assert mod._document_timezone(root, NS).utcoffset(None) == timedelta(hours=-5.5)


@pytest.mark.parametrize("value", [None, "", "not-an-offset"])
def test_document_timezone_defaults_invalid_or_missing_values_to_utc(value, caplog):
    time_zone = "" if value is None else f"<timeZone>{value}</timeZone>"
    root = ET.fromstring(
        f'<TimeSeries xmlns="{mod.DEFAULT_PI_NAMESPACE}">{time_zone}</TimeSeries>'
    )

    with caplog.at_level(logging.WARNING, logger=mod.__name__):
        result = mod._document_timezone(root, NS)

    assert result == timezone.utc
    if value == "not-an-offset":
        assert "Unparsable <timeZone>" in caplog.text


def test_forecast_datetime_handles_present_and_missing_elements():
    present = ET.fromstring(
        f'<header xmlns="{mod.DEFAULT_PI_NAMESPACE}">'
        '<forecastDate date="2024-09-16" time="12:30:00"/>'
        "</header>"
    )
    missing = ET.fromstring(f'<header xmlns="{mod.DEFAULT_PI_NAMESPACE}"/>')

    assert mod._forecast_datetime(present, NS) == "2024-09-16 12:30:00"
    assert mod._forecast_datetime(missing, NS) is None


@pytest.mark.parametrize(
    ("location_id", "expected"),
    [
        ("WABM5", "Wabasha"),
        ("WABM5LOC", "Wabasha"),
        ("XXXXX", None),
    ],
)
def test_lookup_location_uses_exact_then_handbook_prefix(location_id, expected):
    assert mod._lookup_location(location_id, {"WABM5": "Wabasha"}) == expected


def test_standard_groups_are_defaults_and_can_be_disabled(monkeypatch):
    custom_locations = [{"group_id": "Custom Locations"}]
    custom_timeseries = {"group_id": "Custom Timeseries"}

    assert mod._location_alias_groups({}) == mod.DEFAULT_LOCATION_ALIAS_GROUPS
    assert (
        mod._location_alias_groups({"location_alias_groups": custom_locations})
        is custom_locations
    )
    assert mod._location_alias_groups({"location_alias_groups": []}) == ()
    assert mod._timeseries_group({}) == mod.DEFAULT_TIMESERIES_GROUP
    assert (
        mod._timeseries_group({"timeseries_group": custom_timeseries})
        is custom_timeseries
    )
    assert mod._timeseries_group({"timeseries_group": None}) is None

    location_queries = []
    fake_cwms = SimpleNamespace(
        get_location_group=lambda **kwargs: (
            location_queries.append(kwargs)
            or SimpleNamespace(df=pd.DataFrame(columns=["location-id", "alias-id"]))
        )
    )
    monkeypatch.setattr(mod, "cwms", fake_cwms)

    mod.build_alias_table({}, "MVM")

    assert location_queries == [
        {
            "loc_group_id": "NWS Handbook 5 ID",
            "category_id": "Agency Aliases",
            "office_id": "MVM",
            "group_office_id": "CWMS",
            "category_office_id": "CWMS",
        },
        {
            "loc_group_id": "PIXML RFC CHPS Aliases",
            "category_id": "Data Acquisition",
            "office_id": "MVM",
            "group_office_id": "CWMS",
            "category_office_id": "CWMS",
        },
    ]


def test_standard_timeseries_aliases_are_parameter_aware(monkeypatch):
    rows = [
        {
            "timeseries-id": "LR118.Flow.Inst.6Hours.0.LMRFC-NAEFS-FCST",
            "alias-id": "RIGA4",
        },
        {
            "timeseries-id": "LR118.Stage.Inst.6Hours.0.LMRFC-NAEFS-FCST",
            "alias-id": "RIGA4",
        },
        {
            "timeseries-id": "Baton Rouge-LCL.Flow.Inst.6Hours.0.LMRFC-NAEFS-FCST",
            "alias-id": "BTRL1LCL",
        },
    ]
    timeseries_queries = []
    fake_cwms = SimpleNamespace(
        get_timeseries_group=lambda **kwargs: (
            timeseries_queries.append(kwargs) or SimpleNamespace(df=pd.DataFrame(rows))
        )
    )
    monkeypatch.setattr(mod, "cwms", fake_cwms)

    mapping = mod.build_tsgroup_map({}, "MVM", {})

    assert timeseries_queries == [
        {
            "group_id": "PIXML RFC CHPS Acquisition",
            "category_id": "Data Acquisition",
            "office_id": "MVM",
            "category_office_id": "CWMS",
            "group_office_id": "CWMS",
        }
    ]
    assert mapping["RIGA4.FLOW"] == rows[0]["timeseries-id"]
    assert mapping["RIGA4.STAGE"] == rows[1]["timeseries-id"]
    assert mapping["BTRL1LCL.FLOW"] == rows[2]["timeseries-id"]

    record = {
        "locationId": "RIGA4",
        "parameterId": "FLOW",
        "timeStep_unit": "second",
        "timeStep_multiplier": "21600",
    }
    assert mod.resolve_tsid(record, {}, {}, mapping, "") == (
        rows[0]["timeseries-id"],
        None,
    )
    record["parameterId"] = "STAGE"
    assert mod.resolve_tsid(record, {}, {}, mapping, "") == (
        rows[1]["timeseries-id"],
        None,
    )


def test_series_detail_and_formatting_helpers():
    record = {
        "locationId": "WABM5",
        "parameterId": "SQIN",
        "ensembleId": "member-1",
        "timeStep_unit": "second",
        "timeStep_multiplier": "21600",
        "events": [("2024-09-16 12:00:00", "1.0")],
    }

    assert mod._series_source(record) == "WABM5.SQIN"
    detail = mod._series_detail(record, 2)
    assert detail["interval"] == "6Hours"
    assert detail["event_count"] == 1
    assert mod._format_time_step(detail) == "21600 second"
    assert mod._format_series_detail(detail) == (
        "series #2 WABM5.SQIN (6Hours, 1 values, member-1)"
    )
    assert mod._series_summary(detail) == "#2 6Hours 1 values"
    assert mod._skip("reason", "message") == {
        "reason": "reason",
        "message": "message",
    }


@pytest.mark.parametrize(
    ("time_step", "expected"),
    [
        ({"unit": "second", "multiplier": "60"}, "60 second"),
        ({"unit": "nonequidistant", "multiplier": None}, "nonequidistant"),
        ({"unit": None, "multiplier": "60"}, "60"),
        ({"unit": None, "multiplier": None}, "unknown"),
    ],
)
def test_format_time_step_handles_partial_values(time_step, expected):
    assert mod._format_time_step({"time_step": time_step}) == expected


@pytest.mark.parametrize(
    ("rule", "expected"),
    [
        ({"parameter_id": "SQIN"}, True),
        ({"parameter_id": "RAIM"}, False),
        ({"location_id": "WABM5LOC"}, True),
        ({"location_id": "OTHER"}, False),
        ({"location_id_suffix": "LOC"}, True),
        ({"location_id_suffix": "INQ"}, False),
    ],
)
def test_series_rule_matches_supported_constraints(rule, expected):
    assert mod._series_rule_matches(rule, "WABM5LOC", "SQIN") is expected


def test_parameter_and_duplicate_rule_helpers():
    config = {
        "build_missing_timeseries": True,
        "parameter_map": {"SQIN": "Flow-Sim"},
        "parameter_rules": [
            {
                "parameter_id": "SQIN",
                "location_id_suffix": "LOC",
                "cwms_parameter": "Flow-Local",
            }
        ],
        "parameter_suffix_rules": [
            {
                "parameter_id": "SQIN",
                "location_id_suffix": "LOC",
                "cwms_parameter_suffix": "-Adjusted",
            }
        ],
        "duplicate_preference_rules": [
            {
                "parameter_id": "SQIN",
                "location_id_suffix": "LOC",
                "priority": 10,
            }
        ],
        "default_type": "Inst",
        "default_duration": "0",
        "param_type_rules": [
            {"param_contains": "Flow", "type": "Ave", "duration": "6Hours"}
        ],
    }

    assert mod._build_missing_timeseries(config) is True
    assert mod._build_missing_timeseries({}) is False
    assert (
        mod._resolve_parameter_name(config, "WABM5LOC", "SQIN") == "Flow-Local-Adjusted"
    )
    assert mod._resolve_parameter_name(config, "WABM5", "SQIN") == "Flow-Sim"
    assert mod._resolve_parameter_name(config, "WABM5", "UNKNOWN") is None
    assert (
        mod._duplicate_priority(
            config, {"location_id": "WABM5LOC", "parameter_id": "SQIN"}
        )
        == 10
    )
    assert (
        mod._duplicate_priority(
            config, {"location_id": "WABM5", "parameter_id": "SQIN"}
        )
        == 0
    )
    assert mod._param_type_and_duration(config, "Flow-Sim") == ("Ave", "6Hours")
    assert mod._param_type_and_duration(config, "Elev") == ("Inst", "0")


def test_date_helpers_cover_supported_and_invalid_values():
    assert mod._filename_timestamp("forecast.20240916142934") == datetime(
        2024, 9, 16, 14, 29, 34
    )
    assert mod._filename_timestamp("forecast.xml") is None
    assert mod._parse_dt("2024-09-16 14:29:34") == datetime(2024, 9, 16, 14, 29, 34)
    assert mod._parse_dt("2024-09-16 14:29") == datetime(2024, 9, 16, 14, 29)
    assert mod._parse_dt("invalid") is None
    assert mod._first_creation_datetime(
        [
            {"creationDate": None, "creationTime": None},
            {"creationDate": "2024-09-16", "creationTime": "14:29:34"},
        ]
    ) == datetime(2024, 9, 16, 14, 29, 34)
    assert mod._first_creation_datetime([]) is None


def test_issued_blob_document_helpers_preserve_existing_data():
    config = {
        "runs": [
            {"issued_slot": "base"},
            {"issued_slot": "auto"},
            {"issued_slot": "base"},
        ],
        "watersheds": {
            "m10": {"label": "Mississippi", "cwms_watershed": "MississippiRiver"}
        },
    }
    update = {
        "watershed": "m10",
        "slot": "base",
        "mapping": config["watersheds"]["m10"],
        "value": "2024-09-16 14:29:34",
    }

    assert mod._run_slots(config) == ["base", "auto"]
    document = mod._build_blob_document(config, {"other": {"base": "existing"}}, update)
    assert document["other"]["base"] == "existing"
    assert document["m10"] == {
        "label": "Mississippi",
        "cwms_watershed": "MississippiRiver",
        "base": "2024-09-16 14:29:34",
        "auto": None,
    }


def test_read_and_merge_issued_blob_helpers(monkeypatch):
    writes = []

    fake_cwms = SimpleNamespace(
        get_blob=lambda **kwargs: "{'m10': {'base': 'old'}}",
        update_blob=lambda payload: writes.append(payload),
    )
    monkeypatch.setattr(mod, "cwms", fake_cwms)

    existing = mod._read_issued_blob("MVP", "ISSUED")
    assert existing == {"m10": {"base": "old"}}

    config = {
        "runs": [{"issued_slot": "base"}],
        "issued_time": {"media_type": "application/json"},
        "watersheds": {"m10": {"label": "Mississippi"}},
    }
    update = {
        "blob_id": "ISSUED",
        "watershed": "m10",
        "slot": "base",
        "mapping": config["watersheds"]["m10"],
        "value": "new",
    }
    mod._merge_issued_blob(config, "MVP", update)

    assert len(writes) == 1
    assert json.loads(writes[0]["value"])["m10"]["base"] == "new"


@pytest.mark.parametrize(
    ("value", "missing_value", "expected"),
    [
        ("-999.0", "-999", True),
        ("NaN", "nan", True),
        ("1", "-999", False),
        ("missing", "missing", True),
        ("1", None, False),
    ],
)
def test_is_missing_value(value, missing_value, expected):
    assert mod._is_missing_value(value, missing_value) is expected


def test_series_dataframe_serializes_missing_values_as_null():
    record = {
        "missVal": "-999",
        "events": [
            ("2024-09-16 06:00:00", "1.5"),
            ("2024-09-16 12:00:00", "-999.0"),
        ],
    }

    frame = mod._series_dataframe(record, timezone(timedelta(hours=-6)))

    assert frame["date-time"].dt.strftime("%Y-%m-%d %H:%M:%S%z").tolist() == [
        "2024-09-16 12:00:00+0000",
        "2024-09-16 18:00:00+0000",
    ]
    assert frame["value"].iloc[0] == 1.5
    assert frame["value"].isna().tolist() == [False, True]
    assert frame["quality-code"].tolist() == [
        mod.CWMS_GOOD_QUALITY,
        mod.CWMS_MISSING_QUALITY,
    ]

    payload = mod.cwms.timeseries_df_to_json(
        data=frame,
        ts_id="Test.Flow.Inst.6Hours.0.Forecast",
        units="cfs",
        office_id="MVM",
    )
    assert payload["values"][1][1:] == [None, mod.CWMS_MISSING_QUALITY]
