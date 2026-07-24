import json
from pathlib import Path

import pandas as pd

import cwmscli.nws.load_pixml as mod

CONFIG = Path(__file__).parents[2] / "docs" / "nws" / "mvp.example.json"

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


def _make_fake_cwms(calls):
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
    tsgroup = type(
        "D",
        (),
        {
            "df": pd.DataFrame(
                [
                    {
                        "timeseries-id": "Wabasha.Flow-Local.Inst.6Hours.0.Fcst-NCRFC-CHIPS",
                        "alias-id": "WABM5LOC.SQIN",
                        "office-id": "MVP",
                    }
                ]
            )
        },
    )

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
            raise Exception("not found")  # simulate first-time write

        @staticmethod
        def timeseries_df_to_json(data, ts_id, units, office_id, version_date=None):
            return {"name": ts_id, "units": units, "version-date": version_date}

        @staticmethod
        def store_timeseries(data=None):
            calls.append(("store_timeseries", data["name"], data["version-date"]))

        @staticmethod
        def store_blobs(data, fail_if_exists=True):
            calls.append(("store_blobs", data["id"], data["value"]))

        @staticmethod
        def update_blob(data, fail_if_not_exists=True):
            calls.append(("update_blob", data["id"]))

    return FakeCwms


def _run(monkeypatch, tmp_path, filename, dry_run):
    monkeypatch.setattr("cwmscli.utils.get_saved_login_token", lambda *a, **k: None)
    calls = []
    monkeypatch.setattr(mod, "cwms", _make_fake_cwms(calls))
    xml_path = tmp_path / filename
    xml_path.write_text(PIXML)
    mod.load_pixml(
        input_=str(xml_path),
        config_file=str(CONFIG),
        config_blob=None,
        office="MVP",
        api_key="test-key",
        api_root="http://cda.example/cwms-data/",
        dry_run=dry_run,
    )
    return calls


def test_base_dry_run_resolves_and_versions(monkeypatch, tmp_path, capsys):
    calls = _run(monkeypatch, tmp_path, BASE_NAME, dry_run=True)
    out = json.loads(capsys.readouterr().out)

    assert set(out["resolved_timeseries"]) == {
        "Wabasha.Flow-Sim.Inst.6Hours.0.Fcst-NCRFC-CHIPS",  # built, interval from timeStep
        "Wabasha.Flow-Local.Inst.6Hours.0.Fcst-NCRFC-CHIPS",  # ts-group alias override
        "Wabasha.Precip-RainAndMelt.Total.6Hours.6Hours.Fcst-NCRFC-CHIPS",  # precip type rule
    }
    assert out["skipped"] == 1  # PELV unknown parameter
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
    assert len(stores) == 3
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
