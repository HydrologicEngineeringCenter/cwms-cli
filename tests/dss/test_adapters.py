from datetime import datetime, timezone

import cwmscli.dss.transfer as transfer
from cwmscli.dss.transfer import CwmsSink, CwmsSource


class _FakeStore:
    def __init__(self):
        self.stored = []
        self.closed = False

    def catalog(self, data_type):
        assert data_type == "timeseries"
        return ["Test.Flow.Inst.1Hour.0.Raw"]

    def retrieve(self, identifier):
        return identifier

    def store(self, timeseries):
        self.stored.append(timeseries)

    def close(self):
        self.closed = True


def test_cwms_source_uses_time_window_and_shared_session_options(monkeypatch):
    from hec import CwmsDataStore

    opened = {}
    fake = _FakeStore()

    def fake_open(name, **kwargs):
        opened.update(name=name, **kwargs)
        return fake

    sessions = []
    monkeypatch.setattr(CwmsDataStore, "open", fake_open)

    def fake_init_session(cwms_module, **kwargs):
        sessions.append(kwargs)

    monkeypatch.setattr(transfer, "init_cwms_session", fake_init_session)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 2, tzinfo=timezone.utc)

    source = CwmsSource("https://example/cwms-data", "SWT", start, end, None, "key.txt")

    assert list(source.catalog()) == ["Test.Flow.Inst.1Hour.0.Raw"]
    assert source.retrieve("id") == "id"
    assert opened["office"] == "SWT"
    assert opened["start_time"] == start
    assert opened["end_time"] == end
    assert sessions == [
        {
            "api_root": "https://example/cwms-data",
            "api_key": None,
            "api_key_loc": "key.txt",
        }
    ]
    source.close()
    assert fake.closed


def test_cwms_sink_passes_api_key_and_stores(monkeypatch):
    from hec import CwmsDataStore

    opened = {}
    fake = _FakeStore()
    sessions = []

    def fake_open(name, **kwargs):
        opened.update(name=name, **kwargs)
        return fake

    monkeypatch.setattr(CwmsDataStore, "open", fake_open)
    monkeypatch.setattr(
        transfer,
        "init_cwms_session",
        lambda cwms_module, **kwargs: sessions.append(kwargs),
    )

    sink = CwmsSink("https://example/cwms-data", "SWT", "secret", None)
    sink.store("timeseries")

    assert "api_key" not in opened
    assert opened["read_only"] is False
    assert sessions == [
        {
            "api_root": "https://example/cwms-data",
            "api_key": "secret",
            "api_key_loc": None,
        }
    ]
    assert fake.stored == ["timeseries"]


def test_cwms_source_without_credentials_uses_shared_saved_login_resolution(
    monkeypatch,
):
    from hec import CwmsDataStore

    fake = _FakeStore()
    sessions = []
    monkeypatch.setattr(CwmsDataStore, "open", lambda name, **kwargs: fake)
    monkeypatch.setattr(
        transfer,
        "init_cwms_session",
        lambda cwms_module, **kwargs: sessions.append(kwargs),
    )
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 2, tzinfo=timezone.utc)

    CwmsSource("https://example/cwms-data", "SWT", start, end, None, None)

    assert sessions == [
        {
            "api_root": "https://example/cwms-data",
            "api_key": None,
            "api_key_loc": None,
        }
    ]
