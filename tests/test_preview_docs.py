from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "preview_docs.py"
SCRIPT_SPEC = importlib.util.spec_from_file_location("preview_docs", SCRIPT_PATH)
preview_docs = importlib.util.module_from_spec(SCRIPT_SPEC)
assert SCRIPT_SPEC.loader is not None
SCRIPT_SPEC.loader.exec_module(preview_docs)


def test_build_docs_uses_strict_sphinx_command(monkeypatch):
    calls = {}

    def fake_run(command, cwd, check):
        calls["command"] = command
        calls["cwd"] = cwd
        calls["check"] = check
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(preview_docs.subprocess, "run", fake_run)

    assert preview_docs.build_docs() == 0
    assert calls["command"] == [
        preview_docs.sys.executable,
        "-m",
        "sphinx",
        "-nW",
        "-b",
        "html",
        str(preview_docs.DOCS_DIR),
        str(preview_docs.BUILD_DIR),
    ]
    assert calls["cwd"] == preview_docs.ROOT
    assert calls["check"] is False


def test_main_reports_missing_docs_dependencies(monkeypatch, capsys):
    monkeypatch.setattr(
        preview_docs.importlib.util,
        "find_spec",
        lambda name: None if name == "sphinx" else object(),
    )
    monkeypatch.setattr(
        preview_docs,
        "build_docs",
        lambda: pytest.fail("build_docs should not run when deps are missing"),
    )

    assert preview_docs.main([]) == 1

    captured = capsys.readouterr()
    assert "Missing docs dependencies (sphinx)." in captured.err
    assert "pip install -r docs/requirements.txt" in captured.err


def test_serve_docs_uses_generated_html_directory(monkeypatch, capsys):
    calls = {}

    class FakeServer:
        def __init__(self, address, handler_class):
            calls["address"] = address
            calls["handler_class"] = handler_class

        def serve_forever(self):
            return None

        def server_close(self):
            calls["closed"] = True

    monkeypatch.setattr(preview_docs, "ThreadingHTTPServer", FakeServer)

    preview_docs.serve_docs(8123)

    assert calls["address"] == (preview_docs.DEFAULT_HOST, 8123)
    assert calls["handler_class"].keywords["directory"] == str(preview_docs.BUILD_DIR)
    assert calls["closed"] is True
    captured = capsys.readouterr()
    assert "http://127.0.0.1:8123/" in captured.out
    assert str(preview_docs.BUILD_DIR) in captured.out


def test_main_exits_before_serving_on_build_failure(monkeypatch):
    served = {"called": False}

    monkeypatch.setattr(preview_docs.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(preview_docs, "build_docs", lambda: 2)
    monkeypatch.setattr(
        preview_docs, "serve_docs", lambda port: served.__setitem__("called", True)
    )

    assert preview_docs.main([]) == 2
    assert served["called"] is False


def test_main_passes_custom_port_to_server(monkeypatch):
    calls = {}

    monkeypatch.setattr(preview_docs.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(preview_docs, "build_docs", lambda: 0)
    monkeypatch.setattr(
        preview_docs, "serve_docs", lambda port: calls.__setitem__("port", port)
    )

    assert preview_docs.main(["--port", "9001"]) == 0
    assert calls["port"] == 9001
