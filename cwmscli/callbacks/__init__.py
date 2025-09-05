# Click callbacks for click


def csv_to_list(ctx, param, value):
    """Accept multiple values either via repeated flags or a single comma-delimited string."""
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        out = []
        for v in value:
            if isinstance(v, str) and "," in v:
                out.extend([p.strip() for p in v.split(",") if p.strip()])
            else:
                out.append(v)
        return tuple(out)
    if isinstance(value, str):
        return tuple([p.strip() for p in value.split(",") if p.strip()])
    return value
