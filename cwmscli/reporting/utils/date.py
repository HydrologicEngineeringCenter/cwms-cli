from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo


def parse_when(
    expr: str, tz: str = "GMT", *, _now: Optional[datetime] = None
) -> datetime:
    """
    Parse a report datetime expression:
      - ISO 8601, with optional timezone
      - strftime placeholders, such as "%Y-%m-01T08:00:00"
      - small relative days, such as "today 0800" or "yesterday 08:00"
    """
    value = (expr or "").strip()
    if not value:
        raise ValueError("empty datetime expression")

    tzinfo = ZoneInfo(tz)
    now = _now or datetime.now(tzinfo)

    if "%" in value:
        value = now.strftime(value)

    relative = _parse_relative_day(value, now)
    if relative is not None:
        return relative

    try:
        iso = value.replace("Z", "+00:00") if value.endswith("Z") else value
        parsed = datetime.fromisoformat(iso)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=tzinfo)
        return parsed.astimezone(tzinfo)
    except Exception:
        pass

    try:
        from dateutil import parser as du_parser

        parsed = du_parser.parse(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=tzinfo)
        return parsed.astimezone(tzinfo)
    except Exception:
        pass

    raise ValueError(f"Could not parse datetime expression: {expr!r}")


def _parse_relative_day(expr: str, now: datetime) -> Optional[datetime]:
    parts = expr.lower().split()
    if not parts or parts[0] not in {"today", "yesterday", "tomorrow"}:
        return None

    day_offsets = {"today": 0, "yesterday": -1, "tomorrow": 1}
    base_date = (now + timedelta(days=day_offsets[parts[0]])).date()
    hour = 0
    minute = 0
    if len(parts) > 1:
        time_text = parts[1].replace(":", "")
        if not time_text.isdigit() or len(time_text) not in {2, 4}:
            return None
        if len(time_text) == 2:
            hour = int(time_text)
        else:
            hour = int(time_text[:2])
            minute = int(time_text[2:])
    return datetime(
        base_date.year,
        base_date.month,
        base_date.day,
        hour,
        minute,
        tzinfo=now.tzinfo,
    )


def parse_range(begin_expr: str, end_expr: str, tz: str = "America/Chicago"):
    begin = parse_when(begin_expr, tz)
    end = parse_when(end_expr, tz)
    if end <= begin:
        raise ValueError(
            f"end ({end.isoformat()}) must be after begin ({begin.isoformat()})"
        )
    return begin, end
