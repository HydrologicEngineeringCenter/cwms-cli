from datetime import datetime, timezone

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


class _FakeSession:
    def __init__(self):
        self.headers = {"Authorization": "apikey stale-environment-key"}


def test_cwms_source_uses_time_window_and_saved_token(monkeypatch):
    import cwms
    from hec import CwmsDataStore

    opened = {}
    fake = _FakeStore()

    def fake_open(name, **kwargs):
        opened.update(name=name, **kwargs)
        return fake

    sessions = []
    session = _FakeSession()
    monkeypatch.setattr(CwmsDataStore, "open", fake_open)

    def fake_init_session(**kwargs):
        sessions.append(kwargs)
        return session

    monkeypatch.setattr(cwms, "init_session", fake_init_session)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 2, tzinfo=timezone.utc)

    source = CwmsSource("https://example/cwms-data", "SWT", start, end, None, "token")

    assert list(source.catalog()) == ["Test.Flow.Inst.1Hour.0.Raw"]
    assert source.retrieve("id") == "id"
    assert opened["office"] == "SWT"
    assert opened["start_time"] == start
    assert opened["end_time"] == end
    assert sessions == [{"api_root": "https://example/cwms-data", "token": "token"}]
    assert session.headers == {"Authorization": "Bearer token"}
    source.close()
    assert fake.closed


def test_cwms_sink_passes_api_key_and_stores(monkeypatch):
    import cwms
    from hec import CwmsDataStore

    opened = {}
    fake = _FakeStore()
    session = _FakeSession()

    def fake_open(name, **kwargs):
        opened.update(name=name, **kwargs)
        return fake

    monkeypatch.setattr(CwmsDataStore, "open", fake_open)
    monkeypatch.setattr(cwms, "init_session", lambda **kwargs: session)

    sink = CwmsSink("https://example/cwms-data", "SWT", "secret", None)
    sink.store("timeseries")

    assert "api_key" not in opened
    assert opened["read_only"] is False
    assert session.headers == {"Authorization": "apikey secret"}
    assert fake.stored == ["timeseries"]


def test_anonymous_source_clears_environment_authorization(monkeypatch):
    import cwms
    from hec import CwmsDataStore

    fake = _FakeStore()
    session = _FakeSession()
    monkeypatch.setattr(CwmsDataStore, "open", lambda name, **kwargs: fake)
    monkeypatch.setattr(cwms, "init_session", lambda **kwargs: session)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 2, tzinfo=timezone.utc)

    CwmsSource("https://example/cwms-data", "SWT", start, end, None, None)

    assert session.headers == {}
