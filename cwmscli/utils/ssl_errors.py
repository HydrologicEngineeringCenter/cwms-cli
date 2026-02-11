from __future__ import annotations

import os
import ssl
import sys
from typing import Iterable


def _walk_exception_chain(exc: BaseException) -> Iterable[BaseException]:
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        yield cur
        cur = cur.__cause__ or cur.__context__


def is_cert_verify_error(exc: BaseException) -> bool:
    try:
        import requests
    except Exception:
        requests = None

    try:
        import urllib3
    except Exception:
        urllib3 = None

    for e in _walk_exception_chain(exc):
        if isinstance(e, ssl.SSLCertVerificationError):
            return True
        if isinstance(e, ssl.SSLError) and "CERTIFICATE_VERIFY_FAILED" in str(e):
            return True
        if requests is not None:
            if isinstance(e, getattr(requests.exceptions, "SSLError", ())):
                if (
                    "CERTIFICATE_VERIFY_FAILED" in str(e)
                    or "certificate verify failed" in str(e).lower()
                ):
                    return True
        if urllib3 is not None:
            if isinstance(e, getattr(urllib3.exceptions, "SSLError", ())):
                if (
                    "CERTIFICATE_VERIFY_FAILED" in str(e)
                    or "certificate verify failed" in str(e).lower()
                ):
                    return True
    return False


def ssl_help_text() -> str:
    if os.name == "nt" or sys.platform.startswith("win"):
        return (
            "TLS certificate verification failed.\n\n"
            "Windows fix (recommended):\n"
            "  python -m pip install --upgrade pip-system-certs\n\n"
            "Then re-run your command.\n"
        )

    if sys.platform.startswith(("sunos", "sunos5", "solaris")):
        return (
            "TLS certificate verification failed.\n\n"
            "Solaris fix: configure Python/requests to use your system/DoD trust bundle.\n"
            "Add one of these to your shell profile (e.g., ~/.bashrc) and start a new shell:\n\n"
            "  export SSL_CERT_FILE=/path/to/your/dod_ca_bundle.pem\n"
            "  # or\n"
            "  export REQUESTS_CA_BUNDLE=/path/to/your/dod_ca_bundle.pem\n\n"
            "Use the bundle path required by your environment.\n"
        )

    return (
        "TLS certificate verification failed.\n\n"
        "Fix: configure Python/requests to use your organization trust bundle.\n"
        "Common options:\n"
        "  export SSL_CERT_FILE=/path/to/ca-bundle.pem\n"
        "  export REQUESTS_CA_BUNDLE=/path/to/ca-bundle.pem\n"
    )
