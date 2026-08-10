#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
BUILD_DIR = DOCS_DIR / "_build" / "html"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DOCS_MODULES = ("sphinx", "sphinx_rtd_theme", "sphinx_click")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and preview the cwms-cli docs locally."
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Local port for the preview server (default: {DEFAULT_PORT}).",
    )
    return parser.parse_args(argv)


def find_missing_docs_modules() -> list[str]:
    return [name for name in DOCS_MODULES if importlib.util.find_spec(name) is None]


def build_docs() -> int:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sphinx",
            "-nW",
            "-b",
            "html",
            str(DOCS_DIR),
            str(BUILD_DIR),
        ],
        cwd=ROOT,
        check=False,
    )
    return result.returncode


def serve_docs(port: int) -> None:
    handler = partial(SimpleHTTPRequestHandler, directory=str(BUILD_DIR))
    server = ThreadingHTTPServer((DEFAULT_HOST, port), handler)
    print(f"Docs preview available at http://{DEFAULT_HOST}:{port}/")
    print(f"Serving files from {BUILD_DIR}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping docs preview server.")
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    missing = find_missing_docs_modules()
    if missing:
        missing_list = ", ".join(missing)
        print(
            "Missing docs dependencies "
            f"({missing_list}). Install them with:\n"
            f"{sys.executable} -m pip install -r docs/requirements.txt",
            file=sys.stderr,
        )
        return 1

    build_status = build_docs()
    if build_status != 0:
        return build_status

    serve_docs(args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
