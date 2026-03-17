import re

EXPRESSION_TOKEN_PATTERN = r'"[^"]+"|\'[^\']+\'|\+|\-|\*|\/|[^\+\-\*\/]+'
OPERATORS = {"+", "-", "*", "/"}


def expression_columns(expr):
    """Return column identifiers referenced by an expression, excluding operators."""
    tokens = re.findall(EXPRESSION_TOKEN_PATTERN, expr.replace(" ", ""))
    columns = []
    for token in tokens:
        if token in OPERATORS:
            continue
        columns.append(token.strip('"').strip("'"))
    return columns


def eval_expression(expr, row, header_map):
    """
    Evaluate simple math expressions (+, -, *, /) using values from the row based on column names in the expression.
    """
    tokens = re.findall(EXPRESSION_TOKEN_PATTERN, expr.replace(" ", ""))
    result = None
    for i, token in enumerate(tokens):
        if token in OPERATORS:
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
            elif op == "/":
                # Handle 
                if val == 0:
                    return None
                result /= val
    return result
