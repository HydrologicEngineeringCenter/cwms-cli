import json
import re
from typing import Any, Callable, Optional

import pandas as pd

ColorFn = Callable[[str, str], str]  # e.g. c("text", "BLUE")


_JSON_START = re.compile(r"^\s*[\{\[]")
# Very lightweight JSON "syntax highlighting" (works on pretty-printed JSON)
_JSON_TOKENS = re.compile(
    r'(?P<key>"(?:\\.|[^"\\])*")\s*:'
    r"|(?P<string>\"(?:\\.|[^\"\\])*\")"
    r"|(?P<number>-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)"
    r"|(?P<bool>\btrue\b|\bfalse\b)"
    r"|(?P<null>\bnull\b)"
)


def _maybe_parse_json(s: str) -> Optional[Any]:
    if not _JSON_START.match(s):
        return None
    try:
        return json.loads(s)
    except Exception:
        return None


def _colorize_json(pretty_json: str, c: ColorFn) -> str:
    def repl(m: re.Match[str]) -> str:
        if m.group("key") is not None:
            # key token (still includes quotes)
            return f'{c(m.group("key"), "CYAN")}:'
        if m.group("string") is not None:
            return c(m.group("string"), "GREEN")
        if m.group("number") is not None:
            return c(m.group("number"), "MAGENTA")
        if m.group("bool") is not None:
            return c(m.group("bool"), "YELLOW")
        if m.group("null") is not None:
            return c(m.group("null"), "RED")
        return m.group(0)

    return _JSON_TOKENS.sub(repl, pretty_json)


def _format_cell(val: Any, *, c: ColorFn, json_color: bool) -> str:
    s = "" if val is None else str(val)

    if json_color:
        obj = _maybe_parse_json(s)
        if obj is not None:
            pretty = json.dumps(obj, indent=2, sort_keys=True)
            return _colorize_json(pretty, c)

    return s


def format_df_for_log(
    df: pd.DataFrame,
    *,
    c: ColorFn,
    col_colors: dict[int, str] | None = None,
    json_color: bool = True,
    max_rows: int = 500,
) -> str:
    """
    Formats a pandas DataFrame for logging, applying optional colorization to columns and JSON values.
    This function iterates over the rows of the provided DataFrame and formats each cell for logging.
    You can specify colors for particular columns and whether to colorize JSON values. The output is a
    string suitable for logging, with each row on a new line.
    Args:
        df (pd.DataFrame): The DataFrame to format.
        c (ColorFn): A function that applies color to a string, e.g., c(text, color_name).
        col_colors (dict[int, str] | None, optional): A mapping from column indices to color names.
            If None, defaults to {0: "BLUE", 1: "GREEN"}.
        json_color (bool, optional): Whether to apply colorization to JSON values. Defaults to True.
        max_rows (int, optional): Maximum number of rows to display. Defaults to 500.
    Returns:
        str: The formatted string representation of the DataFrame for logging.
    Examples:
        >>> import pandas as pd
        >>> def color_fn(text, color): return f"<{color}>{text}</{color}>"
        >>> df = pd.DataFrame({'A': [1, 2], 'B': ['x', 'y']})
        >>> print(format_df_for_log(df, c=color_fn, col_colors={0: "RED", 1: "GREEN"}))
        <RED>1</RED>  <GREEN>x</GREEN>
        <RED>2</RED>  <GREEN>y</GREEN>

    """
    col_colors = col_colors or {0: "BLUE", 1: "GREEN"}

    lines: list[str] = []
    with pd.option_context("display.max_rows", max_rows, "display.max_columns", None):
        for row in df.itertuples(index=False, name=None):
            parts: list[str] = []
            for idx, val in enumerate(row):
                cell = _format_cell(val, c=c, json_color=json_color)
                if idx in col_colors:
                    parts.append(c(cell, col_colors[idx]))
                else:
                    parts.append(cell)
            lines.append("  ".join(parts))

    return "\n".join(lines)
