from functools import partial

import pytest

from cwmscli.dss.naming import ExportRule, ImportRule
from cwmscli.dss.transfer import (
    NullSink,
    transfer_all,
    transform_export,
    transform_import,
)


def _timeseries(name="Test.Flow.Inst.1Hour.0.Raw"):
    from hec import TimeSeries

    return TimeSeries(
        name,
        ["2026-01-01T00:00:00+00:00", "2026-01-01T01:00:00+00:00"],
        [1.0, float("nan")],
        [0, 5],
    )


def test_import_transform_preserves_quality_and_applies_factor():
    timeseries = _timeseries("//Test/Flow--Inst--0//1HOUR/Raw/")
    timeseries.iset_parameter_type("INST-VAL")
    timeseries.iset_unit("cfs")
    rule = ImportRule(timeseries.name, "Test.Flow.Inst.1Hour.0.Raw", "cfs", 2)

    result = transform_import(timeseries, rule)

    assert result.name == rule.tsid
    assert result.values[0] == 2
    assert result.qualities == [0, 5]
    assert result.time_zone == "UTC"


def test_export_transform_preserves_legacy_name_and_timezone():
    timeseries = _timeseries()
    rule = ExportRule(
        timeseries.name, "//Test/Flow--Inst--0//1HOUR/Raw/", None, 2, "cfs"
    )

    result = transform_export(timeseries, rule, "US/Central")

    assert result.name.upper() == rule.pathname.upper()
    assert result.values[0] == 2
    assert result.qualities == [0, 5]
    assert result.time_zone == "US/Central"


class _Source:
    def catalog(self):
        return ["good", "bad", "skipped"]

    def retrieve(self, identifier):
        if identifier == "bad":
            raise RuntimeError("broken")
        return type("Series", (), {"name": identifier})()


class _Sink:
    def __init__(self):
        self.stored = []

    def store(self, timeseries):
        self.stored.append(timeseries.name)


def test_partial_failures_continue_and_are_counted():
    sink = _Sink()
    summary = transfer_all(
        source=_Source(),
        sink=sink,
        resolve=lambda identifier: None if identifier == "skipped" else identifier,
        transform=lambda timeseries, rule: timeseries,
        dry_run=False,
    )

    assert summary.discovered == 3
    assert summary.transferred == 1
    assert summary.skipped == 1
    assert summary.failed == 1
    assert sink.stored == ["good"]


def test_dry_run_never_calls_sink():
    summary = transfer_all(
        source=type(
            "Source",
            (),
            {
                "catalog": lambda self: ["one"],
                "retrieve": lambda self, identifier: type(
                    "Series", (), {"name": identifier}
                )(),
            },
        )(),
        sink=NullSink(),
        resolve=lambda identifier: identifier,
        transform=lambda timeseries, rule: timeseries,
        dry_run=True,
    )
    assert summary.transferred == 1


def test_explicit_identifiers_bypass_catalog():
    source = _Source()
    source.catalog = lambda: pytest.fail("catalog should not be requested")

    summary = transfer_all(
        source=source,
        sink=NullSink(),
        resolve=lambda identifier: identifier,
        transform=lambda timeseries, rule: timeseries,
        dry_run=True,
        identifiers=["good"],
    )

    assert summary.discovered == 1
    assert summary.transferred == 1
