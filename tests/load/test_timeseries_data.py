from types import SimpleNamespace

import pandas as pd
import pytest
from click import ClickException
from click.testing import CliRunner

from cwmscli.__main__ import cli
from cwmscli.load.timeseries.timeseries_data import _load_timeseries_data


def test_load_timeseries_data_command_allows_group_without_category_filters(
    monkeypatch,
):
    calls = []

    def fake_load(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        "cwmscli.load.timeseries.timeseries_data._load_timeseries_data",
        fake_load,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "load",
            "timeseries",
            "data",
            "--source-cda",
            "https://cwms-data.usace.army.mil/cwms-data/",
            "--source-office",
            "MVP",
            "--target-cda",
            "http://localhost:8082/cwms-data/",
            "--ts-group",
            "Include.*",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    assert len(calls) == 1
    assert calls[0]["ts_group"] == "Include.*"
    assert calls[0]["ts_group_category_id"] is None
    assert calls[0]["ts_group_category_office_id"] is None


def test_load_timeseries_data_group_filters_to_single_source_office(
    monkeypatch, capsys
):
    captured = {
        "get_timeseries_groups": [],
        "get_multi_timeseries_df": [],
        "store_multi_timeseries_df": [],
        "init_session": [],
    }

    def fake_init_session(api_root, api_key=None):
        captured["init_session"].append((api_root, api_key))

    def fake_get_timeseries_groups(**kwargs):
        captured["get_timeseries_groups"].append(kwargs)
        return SimpleNamespace(
            json=[
                {
                    "id": "MVP Include",
                    "time-series-category": {"id": "MVP Dissemination"},
                    "assigned-time-series": [
                        {"office-id": "MVP", "timeseries-id": "A.Flow.Inst.1Hour.0"},
                        {"office-id": "SWT", "timeseries-id": "B.Flow.Inst.1Hour.0"},
                    ],
                },
                {
                    "id": "MVP Include Secondary",
                    "time-series-category": {"id": "MVP Dissemination"},
                    "assigned-time-series": [
                        {"office-id": "MVP", "timeseries-id": "A.Flow.Inst.1Hour.0"},
                        {"office-id": "MVP", "timeseries-id": "C.Stage.Inst.1Hour.0"},
                    ],
                },
            ]
        )

    def fake_get_multi_timeseries_df(**kwargs):
        captured["get_multi_timeseries_df"].append(kwargs)
        return pd.DataFrame(
            [
                {
                    "date-time": "2024-01-01T00:00:00Z",
                    "timeseries-id": kwargs["ts_ids"][0],
                    "value": 1.0,
                }
            ]
        )

    def fake_store_multi_timeseries_df(**kwargs):
        captured["store_multi_timeseries_df"].append(kwargs)

    fake_cwms = SimpleNamespace(
        init_session=fake_init_session,
        get_timeseries_groups=fake_get_timeseries_groups,
        get_multi_timeseries_df=fake_get_multi_timeseries_df,
        store_multi_timeseries_df=fake_store_multi_timeseries_df,
    )
    monkeypatch.setitem(__import__("sys").modules, "cwms", fake_cwms)

    _load_timeseries_data(
        source_cda="https://cwms-data.usace.army.mil/cwms-data/",
        source_office="MVP",
        target_cda="http://localhost:8082/cwms-data/",
        target_api_key=None,
        verbose=0,
        dry_run=True,
        ts_group="Include.*",
        ts_group_category_id="MVP Dissemination",
    )

    assert captured["get_timeseries_groups"] == [
        {
            "office_id": "MVP",
            "include_assigned": True,
            "timeseries_category_like": "MVP Dissemination",
            "timeseries_group_like": "Include.*",
            "category_office_id": None,
        }
    ]
    assert captured["get_multi_timeseries_df"] == [
        {
            "ts_ids": ["A.Flow.Inst.1Hour.0", "C.Stage.Inst.1Hour.0"],
            "office_id": "MVP",
            "melted": True,
            "begin": None,
            "end": None,
        }
    ]
    assert captured["store_multi_timeseries_df"] == []

    output = capsys.readouterr().out
    assert "Matched 2 timeseries group(s) for office 'MVP'" in output
    assert (
        "MVP Include (category: MVP Dissemination): 1 timeseries for office MVP"
        in output
    )
    assert (
        "MVP Include Secondary (category: MVP Dissemination): 2 timeseries for office MVP"
        in output
    )
    assert "SWT" not in str(captured["get_multi_timeseries_df"])


def test_load_timeseries_data_group_raises_when_no_members_belong_to_source_office(
    monkeypatch,
):
    def fake_init_session(api_root, api_key=None):
        return None

    def fake_get_timeseries_groups(**kwargs):
        return SimpleNamespace(
            json=[
                {
                    "id": "Cross Office",
                    "assigned-time-series": [
                        {"office-id": "SWT", "timeseries-id": "B.Flow.Inst.1Hour.0"}
                    ],
                }
            ]
        )

    fake_cwms = SimpleNamespace(
        init_session=fake_init_session,
        get_timeseries_groups=fake_get_timeseries_groups,
    )
    monkeypatch.setitem(__import__("sys").modules, "cwms", fake_cwms)

    with pytest.raises(ClickException, match="No assigned timeseries.*office 'MVP'"):
        _load_timeseries_data(
            source_cda="https://cwms-data.usace.army.mil/cwms-data/",
            source_office="MVP",
            target_cda="http://localhost:8082/cwms-data/",
            target_api_key=None,
            verbose=0,
            dry_run=True,
            ts_group="Include.*",
        )
