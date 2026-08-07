import click
import pytest

from cwmscli.load.root import _validate_cda_api_root


class FakeResponse:
    def __init__(self, payload=None, error=None, headers=None, text=""):
        self.payload = payload
        self.error = error
        self.headers = headers or {}
        self.text = text

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def test_validate_cda_api_root_accepts_openapi_document(monkeypatch):
    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append((url, headers, timeout))
        return FakeResponse({"openapi": "3.0.1", "info": {"title": "CWMS Data API"}})

    monkeypatch.setattr("cwmscli.load.root.requests.get", fake_get)

    _validate_cda_api_root("http://localhost:8082/cwms-data/", role="Target")

    assert calls == [
        (
            "http://localhost:8082/cwms-data/swagger-docs",
            {"Accept": "application/json"},
            2.5,
        )
    ]


def test_validate_cda_api_root_rejects_non_openapi_document(monkeypatch):
    monkeypatch.setattr(
        "cwmscli.load.root.requests.get",
        lambda *a, **k: FakeResponse({"message": "not cda"}),
    )

    with pytest.raises(click.ClickException, match="did not return a CDA OpenAPI"):
        _validate_cda_api_root("https://example.test/not-cda", role="Target")


def test_validate_cda_api_root_accepts_cda_landing_page(monkeypatch):
    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append(url)
        if url.endswith("/swagger-docs"):
            return FakeResponse(ValueError("not json"))
        return FakeResponse(
            headers={"Content-Type": "text/html"},
            text="<title>CDA - CWMS Data API</title>",
        )

    monkeypatch.setattr("cwmscli.load.root.requests.get", fake_get)

    _validate_cda_api_root("http://localhost:7000/cwms-data", role="Target")

    assert calls == [
        "http://localhost:7000/cwms-data/swagger-docs",
        "http://localhost:7000/cwms-data",
    ]


def test_validate_cda_api_root_rejects_invalid_url():
    with pytest.raises(click.ClickException, match="absolute http"):
        _validate_cda_api_root("sas-t7/sas-data/", role="Target")


def test_validate_cda_api_root_reports_request_failure(monkeypatch):
    class FakeRequestException(Exception):
        pass

    def fake_get(*args, **kwargs):
        raise FakeRequestException("connection refused")

    monkeypatch.setattr("cwmscli.load.root.requests.get", fake_get)
    monkeypatch.setattr(
        "cwmscli.load.root.requests.RequestException", FakeRequestException
    )

    with pytest.raises(click.ClickException, match="failed to fetch"):
        _validate_cda_api_root("http://localhost:9999/cwms-data", role="Target")
