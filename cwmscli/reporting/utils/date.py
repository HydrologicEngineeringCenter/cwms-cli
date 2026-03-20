from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def parse_when(expr: str, tz: str = "GMT", *, _now: datetime | None = None) -> datetime:
    """
    Parse a flexible datetime expression:
      - ISO 8601 (e.g. 2025-09-22T08:00[:SS][Z|±HH:MM])
      - ISO with strftime placeholders (e.g. "%Y-%m-01T08:00:00")
      - Natural language (e.g. "2 years ago September 1 08:00", "yesterday 08:00")
    Returns a timezone-aware datetime in the provided tz.
    """
    s = (expr or "").strip()
    if not s:
        raise ValueError("empty datetime expression")

    tzinfo = ZoneInfo(tz)
    now = _now or datetime.now(tzinfo)

    # Expand strftime placeholders first if any
    if "%" in s:
        s = now.strftime(s)

    # Try strict ISO first
    try:
        iso = s.replace("Z", "+00:00") if s.endswith("Z") else s
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tzinfo)
        else:
            dt = dt.astimezone(tzinfo)
        return dt
    except Exception:
        pass

    # Give options to the parsers
    #  - dateutil.parser: https://dateutil.readthedocs.io/en/stable/parser.html
    #  - dateparser: https://dateparser.readthedocs.io
    try:
        from dateutil import parser as du_parser

        dt = du_parser.parse(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tzinfo)
        else:
            dt = dt.astimezone(tzinfo)
        return dt
    except Exception:
        pass

    try:
        from dateparser import parse as dp_parse

        dt = dp_parse(
            s,
            settings={
                "RETURN_AS_TIMEZONE_AWARE": True,
                "TIMEZONE": tz,
                "PREFER_DAY_OF_MONTH": "first",
            },
        )
        if dt:
            # convert to expected tz if not already
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tzinfo)
            else:
                dt = dt.astimezone(tzinfo)
            return dt
    except Exception:
        pass

    raise ValueError(f"Could not parse datetime expression: {expr!r}")


def parse_range(begin_expr: str, end_expr: str, tz: str = "America/Chicago"):
    begin = parse_when(begin_expr, tz)
    end = parse_when(end_expr, tz)
    if end <= begin:
        raise ValueError(
            f"end ({end.isoformat()}) must be after begin ({begin.isoformat()})"
        )
    return begin, end
