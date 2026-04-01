# Click callbacks for click

import re


def csv_to_list(ctx, param, value):
    """Accept multiple values either via repeated flags or a single delimiter-separated string.

    Supported delimiters are comma (,) and pipe (|) to make CLI usage easier and avoid
    shell pipe interpretation issues when users type role shortcuts.
    """
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        out = []
        for v in value:
            if isinstance(v, str) and ("," in v or "|" in v):
                for part in re.split(r"[,|]", v):
                    part = part.strip()
                    if part:
                        out.append(part)
            else:
                out.append(v)
        return tuple(out)
    if isinstance(value, str):
        return tuple(p.strip() for p in re.split(r"[,|]", value) if p.strip())
    return value
