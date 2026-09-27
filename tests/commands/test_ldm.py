import json

from cwmscli.commands import ldm


class FakeResponse:
    def __init__(self, payload=None, content=b"", text=""):
        self._payload = payload
        self.content = content or (
            json.dumps(payload).encode() if payload is not None else b""
        )
        self.text = text

    def raise_for_status(self):
        pass

    def json(self):
        if self._payload is None:
            raise ValueError
        return self._payload


def test_list_products_uses_ldm_key_header(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(
        ldm.requests,
        "request",
        lambda method, url, **kwargs: (
            calls.append((method, url, kwargs)) or FakeResponse({"products": []})
        ),
    )

    ldm.list_products("https://ldm.example/api", "secret")

    assert calls[0][0:2] == ("GET", "https://ldm.example/api/products")
    assert calls[0][2]["headers"]["key"] == "secret"
    assert json.loads(capsys.readouterr().out) == {"products": []}


def test_upload_product_file_uses_expected_multipart_contract(monkeypatch, tmp_path):
    input_file = tmp_path / "report.shef"
    input_file.write_text("data", encoding="utf-8")
    calls = []
    monkeypatch.setattr(
        ldm.requests,
        "request",
        lambda method, url, **kwargs: (
            calls.append((method, url, kwargs)) or FakeResponse([])
        ),
    )

    ldm.upload_product_file(
        "https://ldm.example/api", "secret", "coerr1lrn", str(input_file)
    )

    method, url, kwargs = calls[0]
    assert (method, url) == ("POST", "https://ldm.example/api/productfiles")
    assert kwargs["headers"]["key"] == "secret"
    assert kwargs["data"] == {"product_slug": "coerr1lrn"}
    assert kwargs["files"]["files"][0] == "report.shef"
    assert kwargs["files"]["files"][2] == "application/octet-stream"


def test_download_product_file_uses_returned_file_key(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        ldm.requests,
        "request",
        lambda method, url, **kwargs: (
            calls.append((method, url, kwargs)) or FakeResponse(content=b"payload")
        ),
    )
    destination = tmp_path / "downloaded.txt"

    ldm.download_product_file(
        "https://ldm.example/api",
        "secret",
        "products/coerr1lrn/report_123.shef",
        str(destination),
    )

    assert calls[0][0:2] == (
        "GET",
        "https://ldm.example/api/ldm/products/coerr1lrn/report_123.shef",
    )
    assert calls[0][2]["headers"]["key"] == "secret"
    assert destination.read_bytes() == b"payload"


def test_remove_product_destination_uses_delete(monkeypatch):
    calls = []
    monkeypatch.setattr(
        ldm.requests,
        "request",
        lambda method, url, **kwargs: (
            calls.append((method, url, kwargs)) or FakeResponse({"message": "removed"})
        ),
    )

    ldm.remove_product_destination(
        "https://ldm.example/api", "secret", "coerr1lrn", "cumulus"
    )

    assert calls[0][0:2] == (
        "DELETE",
        "https://ldm.example/api/products/coerr1lrn/destination/cumulus",
    )


def test_purge_product_files_requires_confirmation(monkeypatch):
    calls = []
    monkeypatch.setattr(
        ldm.requests,
        "request",
        lambda method, url, **kwargs: (
            calls.append((method, url, kwargs)) or FakeResponse({"message": "purged"})
        ),
    )

    try:
        ldm.purge_product_files("https://ldm.example/api", "secret", False)
    except ValueError as error:
        assert "--confirm" in str(error)
    else:
        raise AssertionError("purge should require confirmation")

    ldm.purge_product_files("https://ldm.example/api", "secret", True)
    assert calls[0][0:2] == (
        "POST",
        "https://ldm.example/api/admin/productfiles/purge",
    )
