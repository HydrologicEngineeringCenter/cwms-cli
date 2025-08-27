import re


def eval_expression(expr, row, header_map):
    """
    Evaluate simple math expressions (+, -, *) using values from the row based on column names in the expression.
    """
    tokens = re.findall(
        r'"[^"]+"|\'[^\']+\'|\+|\-|\*|[^\+\-\*]+', expr.replace(" ", "")
    )
    result = None
    for i, token in enumerate(tokens):
        if token in {"+", "-", "*"}:
            continue

        col_name = token.strip('"').strip("'").lower()
        idx = header_map.get(col_name)
        if idx is None or idx >= len(row):
            # Immediately return to prevent adding None (0) to result
            return None
        else:
            try:
                val = float(row[idx])
            except ValueError:
                val = None

        if result is None:
            result = val
        else:
            op = tokens[i - 1]
            if val is None or result is None:
                result = None
            elif op == "+":
                result += val
            elif op == "-":
                result -= val
            elif op == "*":
                result *= val
    return result
