def colorize_count(valid: int, total: int) -> str:
    """Colorize the count based on the percentage of valid data.
    Args:
        valid (int): Number of valid data.
        total (int): Total number of data.
    Returns:
        str: ANSI Escape Code representing the colorized count status.
    """
    percent = valid / total if total else 0

    if valid == 0:
        color = "red"
    elif percent >= 0.95:
        color = "green"
    else:
        color = "yellow"

    return f"{colorize(f'{valid}/{total}', color)}"


def colorize(text: str, color: str) -> str:
    """Colorize the text with ANSI Escape Codes provided a color
    Args:
        text (str): Text to colorize.
        color (str): Color to use.

    Returns:
        str: ANSI Escape Code representing the colorized count status.
    """
    COLORS = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "cyan": "\033[96m",
        "white": "\033[97m",
        "gray": "\033[90m",
        "reset": "\033[0m",
    }

    if color not in COLORS:
        return text

    return f"{COLORS.get(color.lower(), COLORS['reset'])}{text}{COLORS['reset']}"
