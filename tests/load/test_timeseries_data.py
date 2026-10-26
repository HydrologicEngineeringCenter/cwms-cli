from types import SimpleNamespace

import pandas as pd
import pytest
from click import ClickException
from click.testing import CliRunner

from cwmscli.__main__ import cli
from cwmscli.load.timeseries.timeseries_data import _load_timeseries_data


@pytest.mark.parametrize("outcome", ["fetch", "store", "success", "empty", "dry"])
def test_load_timeseries_data_exit_status(monkeypatch, outcome):
    """Batch must receive a nonzero exit status when any series fails to copy."""
    import cwms

    monkeypatch.setattr(
        "cwmscli.load.root._validate_cda_api_root", lambda *a, **k: None
    )
    monkeypatch.setattr(cwms, "init_session", lambda **kwargs: None)
    failure = RuntimeError(
        "3 time series failed to store: HTTP 404; incidentIdentifier=test-incident"
    )
    stores = []

    def fetch(**kwargs):
        if outcome == "fetch":
            raise failure
        return pd.DataFrame([] if outcome == "empty" else [{"value": 1.0}])

    def store(**kwargs):
        stores.append(kwargs)
        if outcome == "store":
            raise failure

    monkeypatch.setattr(cwms, "get_multi_timeseries_df", fetch)
    monkeypatch.setattr(cwms, "store_multi_timeseries_df", store)
    args = [
        "load",
        "timeseries",
        "data",
        "--source-cda",
        "https://example.com/cwms-data/",
        "--source-office",
        "MVP",
        "--target-cda",
        "http://localhost:8082/cwms-data/",
        "--ts-id",
        "A.Flow.Inst.1Hour.0.Test",
        "--verbose",
    ]
    if outcome == "dry":
        args.append("--dry-run")
    result = CliRunner().invoke(cli, args)

    if outcome in {"fetch", "store"}:
        assert result.exit_code == 1, result.output
        assert str(failure) in result.output
        assert "copy operation completed" not in result.output
    else:
        assert result.exit_code == 0, result.output
    assert len(stores) == (1 if outcome in {"store", "success"} else 0)


@pytest.mark.parametrize("source_office", ["MVP", "mvp", "MvP", " mvp "])
@pytest.mark.parametrize("office_from_env", [False, True])
def test_load_timeseries_data_command_allows_group_without_category_filters(
    monkeypatch,
    source_office,
    office_from_env,
):
    monkeypatch.setattr(
        "cwmscli.load.root._validate_cda_api_root", lambda *a, **k: None
    )
    calls = []

    def fake_load(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        "cwmscli.load.timeseries.timeseries_data._load_timeseries_data",
        fake_load,
    )

    runner = CliRunner()
    monkeypatch.setenv("CDA_SOURCE_OFFICE", source_office)
    result = runner.invoke(
        cli,
        [
            "load",
            "timeseries",
            "data",
            "--source-cda",
            "https://cwms-data.usace.army.mil/cwms-data/",
            *([] if office_from_env else ["--source-office", source_office]),
            "--target-cda",
            "http://localhost:8082/cwms-data/",
            "--ts-group",
            "Include.*",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    assert len(calls) == 1
    assert calls[0]["source_office"] == "MVP"
    assert calls[0]["ts_group"] == "Include.*"
    assert calls[0]["ts_group_category_id"] is None
    assert calls[0]["ts_group_category_office_id"] is None


@pytest.mark.parametrize("source_office", ["MVP", "mvp", "MvP", " mvp "])
@pytest.mark.parametrize("member_office", ["MVP", "mvp", "MvP"])
@pytest.mark.parametrize("dry_run", [False, True])
def test_load_timeseries_data_group_filters_to_single_source_office(
    monkeypatch, capsys, source_office, member_office, dry_run
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
                        {
                            "office-id": member_office,
                            "timeseries-id": "A.Flow.Inst.1Hour.0",
                        },
                        {"office-id": "SWT", "timeseries-id": "B.Flow.Inst.1Hour.0"},
                        {"timeseries-id": "Missing.Flow.Inst.1Hour.0"},
                        {"office-id": None, "timeseries-id": "Null.Flow.Inst.1Hour.0"},
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
        source_office=source_office,
        target_cda="http://localhost:8082/cwms-data/",
        target_api_key=None,
        verbose=0,
        dry_run=dry_run,
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
    if dry_run:
        assert captured["store_multi_timeseries_df"] == []
    else:
        assert len(captured["store_multi_timeseries_df"]) == 1
        stored = captured["store_multi_timeseries_df"][0]
        assert stored["office_id"] == "MVP"
        assert stored["data"]["value"].tolist() == [1.0]
        assert captured["init_session"][-1] == (
            "http://localhost:8082/cwms-data/",
            None,
        )

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
