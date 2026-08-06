import pytest

from cwmscli.dss.naming import ExportRule, default_pathname
from cwmscli.dss.transfer import DssSink, DssSource, transform_export


@pytest.mark.integration
@pytest.mark.parametrize(
    ("tsid", "times", "dss_time_zone"),
    [
        (
            "Test.Flow.Inst.1Hour.0.Raw",
            ["2026-01-01T00:00:00+00:00", "2026-01-01T01:00:00+00:00"],
            "UTC",
        ),
        (
            "Test.Flow.Inst.0.0.Raw",
            ["2026-01-01T00:07:00+00:00", "2026-01-01T01:13:00+00:00"],
            "UTC",
        ),
        (
            "Test.Flow.Inst.1Hour.0.Central",
            ["2026-07-01T00:00:00+00:00", "2026-07-01T01:00:00+00:00"],
            "US/Central",
        ),
    ],
)
def test_real_temporary_dss_round_trip(tmp_path, tsid, times, dss_time_zone):
    from hec import DssDataStore, TimeSeries

    DssDataStore.set_message_level(0)
    filename = tmp_path / "roundtrip.dss"
    timeseries = TimeSeries(tsid, times, [1.0, 2.0], [0, 0])
    pathname = default_pathname(timeseries.name)
    transformed = transform_export(
        timeseries,
        ExportRule(timeseries.name, pathname, None, 1.0, None),
        dss_time_zone,
    )

    sink = DssSink(str(filename))
    try:
        sink.store(transformed)
    finally:
        sink.close()

    source = DssSource(
        str(filename),
        timeseries.data.index[0].to_pydatetime(),
        timeseries.data.index[-1].to_pydatetime(),
    )
    try:
        identifiers = list(source.catalog())
        retrieved = source.retrieve(identifiers[0])
    finally:
        source.close()

    assert retrieved.values == [1.0, 2.0]
    assert retrieved.qualities == [0, 0]
