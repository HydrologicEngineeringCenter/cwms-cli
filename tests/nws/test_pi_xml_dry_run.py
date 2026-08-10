import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from cwms.api import ApiError

import cwmscli.nws.load_pixml as mod

CONFIG = Path(__file__).parents[2] / "docs" / "nws" / "mvp.example.json"


def _api_error(status_code: int) -> ApiError:
    """An ApiError shaped like the one cwms.api.get raises for a bad response."""
    return ApiError(
        SimpleNamespace(
            url="http://cda.example/cwms-data/blobs/X",
            status_code=status_code,
            reason="Not Found" if status_code == 404 else "Server Error",
            content=b"",
        )
    )


# Minimal MVP-style PI-XML: a clean flow series, an odd-suffix series resolved via
# the timeseries-group alias, a precip series, and an unknown-parameter series.
PIXML = """<?xml version="1.0" encoding="UTF-8"?>
<TimeSeries xmlns="http://www.wldelft.nl/fews/PI" version="1.5">
  <timeZone>0.0</timeZone>
  <series>
    <header>
      <type>instantaneous</type><locationId>WABM5</locationId>
      <parameterId>SQIN</parameterId>
      <timeStep unit="second" multiplier="21600"/>
      <missVal>-999</missVal><units>CFS</units>
    </header>
    <event date="2024-09-05" time="12:00:00" value="864.1" flag="0"/>
    <event date="2024-09-05" time="18:00:00" value="847.4" flag="0"/>
  </series>
  <series>
    <header>
      <type>instantaneous</type><locationId>WABM5LOC</locationId>
      <parameterId>SQIN</parameterId>
      <timeStep unit="second" multiplier="21600"/>
      <missVal>-999</missVal><units>CFS</units>
    </header>
    <event date="2024-09-05" time="12:00:00" value="12.3" flag="0"/>
    <event date="2024-09-05" time="18:00:00" value="-999" flag="0"/>
  </series>
  <series>
    <header>
      <type>accumulative</type><locationId>WABM5</locationId>
      <parameterId>RAIM</parameterId>
      <timeStep unit="second" multiplier="21600"/>
      <missVal>-999</missVal><units>IN</units>
    </header>
    <event date="2024-09-05" time="12:00:00" value="0.1" flag="0"/>
  </series>
  <series>
    <header>
      <type>instantaneous</type><locationId>WABM5</locationId>
      <parameterId>PELV</parameterId>
      <timeStep unit="second" multiplier="21600"/>
      <missVal>-999</missVal><units>FT</units>
    </header>
    <event date="2024-09-05" time="12:00:00" value="5.0" flag="0"/>
  </series>
</TimeSeries>
"""

BASE_NAME = "MSR_2024091612_MSR_main_m10_mississippi_river.20240916142934"
AUTO_NAME = "MSR_2024091612_MSR_main_auto_m10_mississippi_river.20240916142934"

# Same product declared in CST rather than UTC.
PIXML_CST = PIXML.replace("<timeZone>0.0</timeZone>", "<timeZone>-6.0</timeZone>")

PIXML_SAME_SOURCE_ALIAS_COLLISION = """<?xml version="1.0" encoding="UTF-8"?>
<TimeSeries xmlns="http://www.wldelft.nl/fews/PI" version="1.5">
  <timeZone>0.0</timeZone>
  <series>
    <header>
      <type>instantaneous</type><locationId>WABM5</locationId>
      <parameterId>SQIN</parameterId>
      <timeStep unit="second" multiplier="21600"/>
      <missVal>-999</missVal><units>CFS</units>
    </header>
    <event date="2024-09-05" time="12:00:00" value="864.1" flag="0"/>
  </series>
  <series>
    <header>
      <type>instantaneous</type><locationId>WABM5</locationId>
      <parameterId>SQIN</parameterId>
      <timeStep unit="second" multiplier="3600"/>
      <missVal>-999</missVal><units>CFS</units>
    </header>
    <event date="2024-09-05" time="12:00:00" value="865.0" flag="0"/>
  </series>
</TimeSeries>
"""

PIXML_LOCATION_SUFFIX_PARAMETER_RULES = """<?xml version="1.0" encoding="UTF-8"?>
<TimeSeries xmlns="http://www.wldelft.nl/fews/PI" version="1.5">
  <timeZone>0.0</timeZone>
  <series>
    <header>
      <type>instantaneous</type><locationId>WABM5LOC</locationId>
      <parameterId>SQIN</parameterId>
      <timeStep unit="second" multiplier="21600"/>
      <missVal>-999</missVal><units>CFS</units>
    </header>
    <event date="2024-09-05" time="12:00:00" value="12.3" flag="0"/>
  </series>
  <series>
    <header>
      <type>instantaneous</type><locationId>WABM5IN</locationId>
      <parameterId>SQIN</parameterId>
      <timeStep unit="second" multiplier="21600"/>
      <missVal>-999</missVal><units>CFS</units>
    </header>
    <event date="2024-09-05" time="12:00:00" value="864.1" flag="0"/>
  </series>
</TimeSeries>
"""

PIXML_LEGACY_MVP_PARAMETER_RULES = """<?xml version="1.0" encoding="UTF-8"?>
<TimeSeries xmlns="http://www.wldelft.nl/fews/PI" version="1.5">
  <timeZone>0.0</timeZone>
  <series>
    <header>
      <type>instantaneous</type><locationId>WABM5</locationId>
      <parameterId>SPEL</parameterId>
      <timeStep unit="second" multiplier="21600"/>
      <missVal>-999</missVal><units>FT</units>
    </header>
    <event date="2024-09-05" time="12:00:00" value="100.0" flag="0"/>
  </series>
  <series>
    <header>
      <type>instantaneous</type><locationId>WABM5INQ</locationId>
      <parameterId>SQIN</parameterId>
      <timeStep unit="second" multiplier="21600"/>
      <missVal>-999</missVal><units>CFS</units>
    </header>
    <event date="2024-09-05" time="12:00:00" value="864.1" flag="0"/>
  </series>
  <series>
    <header>
      <type>instantaneous</type><locationId>WABM5LOC</locationId>
      <parameterId>SQIN</parameterId>
      <timeStep unit="second" multiplier="21600"/>
      <missVal>-999</missVal><units>CFS</units>
    </header>
    <event date="2024-09-05" time="12:00:00" value="12.3" flag="0"/>
  </series>
  <series>
    <header>
      <type>instantaneous</type><locationId>WABM5OUT</locationId>
      <parameterId>QINE</parameterId>
      <timeStep unit="second" multiplier="21600"/>
      <missVal>-999</missVal><units>CFS</units>
    </header>
    <event date="2024-09-05" time="12:00:00" value="100.1" flag="0"/>
  </series>
  <series>
    <header>
      <type>instantaneous</type><locationId>WABM5ROR</locationId>
      <parameterId>SQIN</parameterId>
      <timeStep unit="second" multiplier="21600"/>
      <missVal>-999</missVal><units>CFS</units>
    </header>
    <event date="2024-09-05" time="12:00:00" value="0.0" flag="0"/>
  </series>
  <series>
    <header>
      <type>accumulative</type><locationId>WABM5ROR</locationId>
      <parameterId>MAP</parameterId>
      <timeStep unit="second" multiplier="21600"/>
      <missVal>-999</missVal><units>IN</units>
    </header>
    <event date="2024-09-05" time="12:00:00" value="0.1" flag="0"/>
  </series>
  <series>
    <header>
      <type>accumulative</type><locationId>WABM5</locationId>
      <parameterId>RAIM</parameterId>
      <timeStep unit="second" multiplier="21600"/>
      <missVal>-999</missVal><units>IN</units>
    </header>
    <event date="2024-09-05" time="12:00:00" value="0.2" flag="0"/>
  </series>
</TimeSeries>
"""

PIXML_ROR_PRECIP_PREFERENCE = """<?xml version="1.0" encoding="UTF-8"?>
<TimeSeries xmlns="http://www.wldelft.nl/fews/PI" version="1.5">
  <timeZone>0.0</timeZone>
  <series>
    <header>
      <type>accumulative</type><locationId>WABM5</locationId>
      <parameterId>RAIM</parameterId>
      <timeStep unit="second" multiplier="21600"/>
      <missVal>-999</missVal><units>IN</units>
    </header>
    <event date="2024-09-05" time="12:00:00" value="0.2" flag="0"/>
  </series>
  <series>
    <header>
      <type>accumulative</type><locationId>WABM5ROR</locationId>
      <parameterId>RAIM</parameterId>
      <timeStep unit="second" multiplier="21600"/>
      <missVal>-999</missVal><units>IN</units>
    </header>
    <event date="2024-09-05" time="12:00:00" value="0.1" flag="0"/>
  </series>
</TimeSeries>
"""

PIXML_NON_CONTRIB_PARAMETER_SUFFIX = """<?xml version="1.0" encoding="UTF-8"?>
<TimeSeries xmlns="http://www.wldelft.nl/fews/PI" version="1.5">
  <timeZone>0.0</timeZone>
  <series>
    <header>
      <type>accumulative</type><locationId>WABM5NON</locationId>
      <parameterId>RAIM</parameterId>
      <timeStep unit="second" multiplier="21600"/>
      <missVal>-999</missVal><units>IN</units>
    </header>
    <event date="2024-09-05" time="12:00:00" value="0.2" flag="0"/>
  </series>
</TimeSeries>
"""


def _make_fake_cwms(calls, tsgroup_rows=None, blob=None):
    """Build a stand-in for the ``cwms`` module.

    ``tsgroup_rows`` overrides the timeseries-group rows (pass ``[]`` for a group
    with no alias entries). ``blob`` controls ``get_blob``: an exception instance
    is raised, anything else is returned; the default is a 404, i.e. no blob yet.
    """
    hb5 = type(
        "D",
        (),
        {
            "df": pd.DataFrame(
                [{"location-id": "Wabasha", "alias-id": "WABM5", "office-id": "MVP"}]
            )
        },
    )
    empty = type("D", (), {"df": pd.DataFrame(columns=["location-id", "alias-id"])})
    if tsgroup_rows is None:
        tsgroup_rows = [
            {
                "timeseries-id": "Wabasha.Flow-Local.Inst.6Hours.0.Fcst-NCRFC-CHIPS",
                "alias-id": "WABM5LOC.SQIN",
                "office-id": "MVP",
            }
        ]
    tsgroup = type(
        "D",
        (),
        {
            "df": pd.DataFrame(
                tsgroup_rows,
                columns=["timeseries-id", "alias-id", "office-id"],
            )
        },
    )
    blob_result = _api_error(404) if blob is None else blob

    class FakeCwms:
        @staticmethod
        def init_session(api_root=None, api_key=None, token=None):
            calls.append(("init_session", api_root, api_key))

        @staticmethod
        def get_location_group(**kwargs):
            return (
                hb5() if kwargs.get("loc_group_id") == "NWS Handbook 5 ID" else empty()
            )

        @staticmethod
        def get_timeseries_group(**kwargs):
            return tsgroup()

        @staticmethod
        def get_blob(blob_id=None, office_id=None):
            calls.append(("get_blob", blob_id, office_id))
            if isinstance(blob_result, Exception):
                raise blob_result
            return blob_result

        @staticmethod
        def timeseries_df_to_json(data, ts_id, units, office_id, version_date=None):
            calls.append(("df_to_json", ts_id, data))
            return {"name": ts_id, "units": units, "version-date": version_date}

        @staticmethod
        def store_timeseries(data=None):
            calls.append(("store_timeseries", data["name"], data["version-date"]))

        @staticmethod
        def store_blobs(data, fail_if_exists=True):
            calls.append(("store_blobs", data["id"], data["value"]))

        @staticmethod
        def update_blob(data, fail_if_not_exists=True):
            calls.append(("update_blob", data["id"], data["value"]))

    return FakeCwms


def _run(
    monkeypatch,
    tmp_path,
    filename,
    dry_run,
    config_file=CONFIG,
    xml=PIXML,
    tsgroup_rows=None,
    blob=None,
    calls=None,
):
    monkeypatch.setattr("cwmscli.utils.get_saved_login_token", lambda *a, **k: None)
    if calls is None:
        calls = []
    monkeypatch.setattr(
        mod, "cwms", _make_fake_cwms(calls, tsgroup_rows=tsgroup_rows, blob=blob)
    )
    xml_path = tmp_path / filename
    xml_path.write_text(xml)
    mod.load_pixml(
        input_=str(xml_path),
        config_file=str(config_file),
        config_blob=None,
        office="MVP",
        api_key="test-key",
        api_root="http://cda.example/cwms-data/",
        dry_run=dry_run,
    )
    return calls


def _write_config(tmp_path, *, strip_parameter_rules=False):
    config = json.loads(CONFIG.read_text())
    if strip_parameter_rules:
        config.pop("parameter_rules", None)
    config_path = tmp_path / (
        "mvp-no-parameter-rules.json" if strip_parameter_rules else "mvp-config.json"
    )
    config_path.write_text(json.dumps(config))
    return config_path


def test_base_dry_run_resolves_and_versions(monkeypatch, tmp_path, capsys):
    calls = _run(monkeypatch, tmp_path, BASE_NAME, dry_run=True)
    out = json.loads(capsys.readouterr().out)

    assert out["resolved_count"] == 4
    assert set(out["resolved_timeseries"]) == {
        "Wabasha.Flow-Sim.Inst.6Hours.0.Fcst-NCRFC-CHIPS",  # built, interval from timeStep
        "Wabasha.Flow-Local.Inst.6Hours.0.Fcst-NCRFC-CHIPS",  # ts-group alias override
        "Wabasha.Elev.Inst.6Hours.0.Fcst-NCRFC-CHIPS",  # PELV pool elevation
        "Wabasha.Precip-RainAndMelt.Total.6Hours.6Hours.Fcst-NCRFC-CHIPS",  # precip type rule
    }
    assert out["skipped"] == 0
    assert out["skipped_by_reason"] == {}
    assert out["duplicate_count"] == 0
    assert out["versioned"] is True
    assert out["version_date"].startswith("2024-09-16T01:11:00")  # filename ts, snapped
    upd = out["issued_update"]
    assert upd["watershed"] == "m10_mississippi_river"
    assert upd["slot"] == "base"
    assert upd["mapping"]["cwms_watershed"] == "MississippiRiverNavigation"
    assert upd["value"] == "2024-09-16 14:29:34"

    # Dry run performs read-only group lookups but never writes.
    assert not [
        c for c in calls if c[0] in ("store_timeseries", "store_blobs", "update_blob")
    ]


def test_auto_run_unversioned_and_version_part_swapped(monkeypatch, tmp_path, capsys):
    _run(monkeypatch, tmp_path, AUTO_NAME, dry_run=True)
    out = json.loads(capsys.readouterr().out)

    assert out["versioned"] is False
    assert out["version_date"] is None
    # Both built and aliased ids carry the -Auto version part.
    assert (
        "Wabasha.Flow-Sim.Inst.6Hours.0.Fcst-NCRFC-CHIPS-Auto"
        in out["resolved_timeseries"]
    )
    assert (
        "Wabasha.Flow-Local.Inst.6Hours.0.Fcst-NCRFC-CHIPS-Auto"
        in out["resolved_timeseries"]
    )
    assert out["issued_update"]["slot"] == "auto"
    assert out["issued_update"]["watershed"] == "m10_mississippi_river"


def test_base_store_passes_version_date_and_writes_blob(monkeypatch, tmp_path):
    calls = _run(monkeypatch, tmp_path, BASE_NAME, dry_run=False)

    stores = [c for c in calls if c[0] == "store_timeseries"]
    assert len(stores) == 4
    # Base run is versioned: every store carries a version date.
    assert all(c[2] is not None for c in stores)

    # A single consolidated issued-time blob is written, carrying the NCRFC->CWMS
    # mapping and this run's issued time.
    blob_writes = [c for c in calls if c[0] == "store_blobs"]
    assert len(blob_writes) == 1
    blob_id, blob_value = blob_writes[0][1], blob_writes[0][2]
    assert blob_id == "MVP-NCRFC-FORECAST-STATUS"
    doc = json.loads(blob_value)
    entry = doc["m10_mississippi_river"]
    assert entry["cwms_watershed"] == "MississippiRiverNavigation"
    assert entry["base"] == "2024-09-16 14:29:34"
    # Other configured watersheds are seeded (mapping present, times null).
    assert doc["min"]["cwms_watershed"] == "MinnesotaRiver"
    assert doc["min"]["base"] is None


def test_colliding_series_are_dropped_not_silently_overwritten(
    monkeypatch, tmp_path, capsys
):
    # Without the MVP suffix rules, WABM5LOC falls back to its 5-char Handbook-5
    # prefix and builds the same TSID as WABM5. The second series must be
    # dropped and reported rather than overwriting the first.
    _run(
        monkeypatch,
        tmp_path,
        BASE_NAME,
        dry_run=True,
        config_file=_write_config(tmp_path, strip_parameter_rules=True),
        tsgroup_rows=[],
    )
    out = json.loads(capsys.readouterr().out)

    tsid = "Wabasha.Flow-Sim.Inst.6Hours.0.Fcst-NCRFC-CHIPS"
    assert out["resolved_timeseries"].count(tsid) == 1
    assert out["duplicates"] == [
        {
            "timeseries_id": tsid,
            "kept": "WABM5.SQIN",
            "dropped": "WABM5LOC.SQIN",
            "kept_summary": "#1 6Hours 2 values",
            "ignored_summary": "#2 6Hours 2 values",
        }
    ]


def test_location_suffix_parameter_rules_split_in_and_loc(
    monkeypatch, tmp_path, capsys
):
    _run(
        monkeypatch,
        tmp_path,
        BASE_NAME,
        dry_run=True,
        config_file=_write_config(tmp_path),
        xml=PIXML_LOCATION_SUFFIX_PARAMETER_RULES,
        tsgroup_rows=[],
    )
    out = json.loads(capsys.readouterr().out)

    assert out["duplicate_count"] == 0
    assert out["duplicates"] == []
    assert sorted(out["resolved_timeseries"]) == [
        "Wabasha.Flow-In.Inst.6Hours.0.Fcst-NCRFC-CHIPS",
        "Wabasha.Flow-Local.Inst.6Hours.0.Fcst-NCRFC-CHIPS",
    ]


def test_legacy_mvp_suffix_patterns_resolve_to_distinct_parameters(
    monkeypatch, tmp_path, capsys
):
    _run(
        monkeypatch,
        tmp_path,
        BASE_NAME,
        dry_run=True,
        config_file=_write_config(tmp_path),
        xml=PIXML_LEGACY_MVP_PARAMETER_RULES,
        tsgroup_rows=[],
    )
    out = json.loads(capsys.readouterr().out)

    assert out["duplicate_count"] == 0
    assert out["duplicates"] == []
    assert sorted(out["resolved_timeseries"]) == [
        "Wabasha.Elev.Inst.6Hours.0.Fcst-NCRFC-CHIPS",
        "Wabasha.Flow-In.Inst.6Hours.0.Fcst-NCRFC-CHIPS",
        "Wabasha.Flow-Local.Inst.6Hours.0.Fcst-NCRFC-CHIPS",
        "Wabasha.Flow-Out.Inst.6Hours.0.Fcst-NCRFC-CHIPS",
        "Wabasha.Flow-Sim-RainOnPool.Inst.6Hours.0.Fcst-NCRFC-CHIPS",
        "Wabasha.Precip-Rain.Total.6Hours.6Hours.Fcst-NCRFC-CHIPS",
        "Wabasha.Precip-RainAndMelt.Total.6Hours.6Hours.Fcst-NCRFC-CHIPS",
    ]


def test_ror_precip_duplicate_preference_keeps_reservoir_series(
    monkeypatch, tmp_path, capsys
):
    _run(
        monkeypatch,
        tmp_path,
        BASE_NAME,
        dry_run=True,
        config_file=_write_config(tmp_path),
        xml=PIXML_ROR_PRECIP_PREFERENCE,
        tsgroup_rows=[],
    )
    out = json.loads(capsys.readouterr().out)

    assert out["resolved_timeseries"] == [
        "Wabasha.Precip-RainAndMelt.Total.6Hours.6Hours.Fcst-NCRFC-CHIPS"
    ]
    assert out["duplicates"] == [
        {
            "timeseries_id": "Wabasha.Precip-RainAndMelt.Total.6Hours.6Hours.Fcst-NCRFC-CHIPS",
            "kept": "WABM5ROR.RAIM",
            "dropped": "WABM5.RAIM",
            "kept_summary": "#2 6Hours 1 values",
            "ignored_summary": "#1 6Hours 1 values",
        }
    ]


def test_ror_precip_duplicate_preference_stores_reservoir_values(monkeypatch, tmp_path):
    calls = _run(
        monkeypatch,
        tmp_path,
        BASE_NAME,
        dry_run=False,
        config_file=_write_config(tmp_path),
        xml=PIXML_ROR_PRECIP_PREFERENCE,
        tsgroup_rows=[],
    )

    frames = {c[1]: c[2] for c in calls if c[0] == "df_to_json"}
    df = frames["Wabasha.Precip-RainAndMelt.Total.6Hours.6Hours.Fcst-NCRFC-CHIPS"]
    assert list(df["value"]) == [0.1]


def test_non_contrib_parameter_suffix_is_applied(monkeypatch, tmp_path, capsys):
    _run(
        monkeypatch,
        tmp_path,
        BASE_NAME,
        dry_run=True,
        config_file=_write_config(tmp_path),
        xml=PIXML_NON_CONTRIB_PARAMETER_SUFFIX,
        tsgroup_rows=[],
    )
    out = json.loads(capsys.readouterr().out)

    assert out["resolved_timeseries"] == [
        "Wabasha.Precip-RainAndMelt-Non_contrib.Total.6Hours.6Hours.Fcst-NCRFC-CHIPS"
    ]
    assert out["duplicate_count"] == 0


def test_duplicate_report_distinguishes_same_source_headers(
    monkeypatch, tmp_path, capsys
):
    _run(
        monkeypatch,
        tmp_path,
        BASE_NAME,
        dry_run=True,
        xml=PIXML_SAME_SOURCE_ALIAS_COLLISION,
        tsgroup_rows=[
            {
                "timeseries-id": "Wabasha.Flow-Sim.Inst.6Hours.0.Fcst-NCRFC-CHIPS",
                "alias-id": "WABM5.SQIN",
                "office-id": "MVP",
            }
        ],
    )
    out = json.loads(capsys.readouterr().out)

    # With interval-aware alias resolution, the 6-hour and 1-hour series
    # resolve to distinct TSIDs instead of colliding on the same id.
    assert out["duplicate_count"] == 0
    assert out["duplicates"] == []
    assert sorted(out["resolved_timeseries"]) == [
        "Wabasha.Flow-Sim.Inst.1Hour.0.Fcst-NCRFC-CHIPS",
        "Wabasha.Flow-Sim.Inst.6Hours.0.Fcst-NCRFC-CHIPS",
    ]


def test_group_only_is_default_when_timeseries_group_is_configured(
    monkeypatch, tmp_path, capsys
):
    config = json.loads(CONFIG.read_text())
    config.pop("build_missing_timeseries", None)
    config_path = tmp_path / "group-only.json"
    config_path.write_text(json.dumps(config))

    _run(
        monkeypatch,
        tmp_path,
        BASE_NAME,
        dry_run=True,
        config_file=config_path,
    )
    out = json.loads(capsys.readouterr().out)

    assert out["resolved_count"] == 1
    assert out["resolved_timeseries"] == [
        "Wabasha.Flow-Local.Inst.6Hours.0.Fcst-NCRFC-CHIPS"
    ]
    assert out["skipped"] == 3
    assert out["skipped_by_reason"] == {
        "not_in_timeseries_group": 3,
    }


def test_group_only_skips_when_timeseries_group_is_empty(monkeypatch, tmp_path, capsys):
    config = json.loads(CONFIG.read_text())
    config.pop("build_missing_timeseries", None)
    config_path = tmp_path / "group-only-empty.json"
    config_path.write_text(json.dumps(config))

    _run(
        monkeypatch,
        tmp_path,
        BASE_NAME,
        dry_run=True,
        config_file=config_path,
        tsgroup_rows=[],
    )
    out = json.loads(capsys.readouterr().out)

    assert out["resolved_count"] == 0
    assert out["resolved_timeseries"] == []
    assert out["skipped"] == 4
    assert out["skipped_by_reason"] == {
        "not_in_timeseries_group": 4,
    }


def test_colliding_series_are_not_stored(monkeypatch, tmp_path):
    calls = _run(
        monkeypatch,
        tmp_path,
        BASE_NAME,
        dry_run=False,
        config_file=_write_config(tmp_path, strip_parameter_rules=True),
        tsgroup_rows=[],
    )

    stored = [c[1] for c in calls if c[0] == "store_timeseries"]
    assert stored == [
        "Wabasha.Flow-Sim.Inst.6Hours.0.Fcst-NCRFC-CHIPS",
        "Wabasha.Precip-RainAndMelt.Total.6Hours.6Hours.Fcst-NCRFC-CHIPS",
        "Wabasha.Elev.Inst.6Hours.0.Fcst-NCRFC-CHIPS",
    ]


def test_event_times_use_document_timezone(monkeypatch, tmp_path):
    calls = _run(monkeypatch, tmp_path, BASE_NAME, dry_run=False, xml=PIXML_CST)

    frames = {c[1]: c[2] for c in calls if c[0] == "df_to_json"}
    df = frames["Wabasha.Flow-Sim.Inst.6Hours.0.Fcst-NCRFC-CHIPS"]
    # 12:00 and 18:00 declared in UTC-6 are 18:00 and 00:00 (next day) in UTC.
    assert [str(t) for t in df["date-time"]] == [
        "2024-09-05 18:00:00+00:00",
        "2024-09-06 00:00:00+00:00",
    ]


def test_utc_document_times_are_unshifted(monkeypatch, tmp_path):
    calls = _run(monkeypatch, tmp_path, BASE_NAME, dry_run=False)

    frames = {c[1]: c[2] for c in calls if c[0] == "df_to_json"}
    df = frames["Wabasha.Flow-Sim.Inst.6Hours.0.Fcst-NCRFC-CHIPS"]
    assert [str(t) for t in df["date-time"]] == [
        "2024-09-05 12:00:00+00:00",
        "2024-09-05 18:00:00+00:00",
    ]


def test_unreadable_issued_blob_aborts_instead_of_clobbering(monkeypatch, tmp_path):
    # A 500 on the read must not be mistaken for "no blob yet": the write is a
    # full-document rewrite and would blank every other watershed's times.
    calls = []
    with pytest.raises(ApiError):
        _run(
            monkeypatch,
            tmp_path,
            BASE_NAME,
            dry_run=False,
            blob=_api_error(500),
            calls=calls,
        )

    assert not [c for c in calls if c[0] in ("store_blobs", "update_blob")]


def test_existing_issued_blob_is_merged_not_replaced(monkeypatch, tmp_path):
    existing = json.dumps(
        {
            "min": {
                "label": "Minnesota River",
                "cwms_watershed": "MinnesotaRiver",
                "base": "2024-09-15 13:00:00",
            }
        }
    )
    calls = _run(monkeypatch, tmp_path, BASE_NAME, dry_run=False, blob=existing)

    writes = [c for c in calls if c[0] in ("store_blobs", "update_blob")]
    assert [c[0] for c in writes] == ["update_blob"]
    doc = json.loads(writes[0][2])
    # This run's watershed is recorded...
    assert doc["m10_mississippi_river"]["base"] == "2024-09-16 14:29:34"
    # ...without discarding a time already recorded for another watershed.
    assert doc["min"]["base"] == "2024-09-15 13:00:00"


def test_cli_smoke_dry_run(monkeypatch, tmp_path):
    from click.testing import CliRunner

    from cwmscli.__main__ import cli

    monkeypatch.setattr("cwmscli.utils.get_saved_login_token", lambda *a, **k: None)
    monkeypatch.setattr(mod, "cwms", _make_fake_cwms([]))
    xml_path = tmp_path / BASE_NAME
    xml_path.write_text(PIXML)

    result = CliRunner().invoke(
        cli,
        [
            "nws",
            "pixml",
            "-i",
            str(xml_path),
            "-c",
            str(CONFIG),
            "-o",
            "MVP",
            "-a",
            "http://cda.example/cwms-data/",
            "-k",
            "test-key",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Wabasha.Flow-Local.Inst.6Hours.0.Fcst-NCRFC-CHIPS" in result.output
