from __future__ import annotations

from colorama import Fore, Style

_ENABLED: bool = False


def set_enabled(enabled: bool) -> None:
    global _ENABLED
    _ENABLED = enabled


def c(text: str, color: str, bright: bool = False) -> str:
    if not _ENABLED:
        return text
    b = Style.BRIGHT if bright else ""
    # Find the color in Fore and apply it to the text, then reset the style at the end
    if hasattr(Fore, color.upper()):
        color = getattr(Fore, color.upper())
    else:
        color = ""
    return f"{color}{b}{text}{Style.RESET_ALL}"


def ok(text: str) -> str:
    return c(text, Fore.GREEN)


def warn(text: str) -> str:
    return c(text, Fore.YELLOW, bright=True)


def err(text: str) -> str:
    return c(text, Fore.RED, bright=True)


def dim(text: str) -> str:
    return c(text, Fore.WHITE, bright=False)
