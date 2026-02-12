from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from typing import Optional

from colorama import Fore, Style
from colorama import init as colorama_init

from cwmscli.utils import colors


@dataclass(frozen=True)
class LoggingConfig:
    level: int = logging.INFO
    log_file: Optional[str] = None
    color: bool = True


class ColorLevelFormatter(logging.Formatter):
    def __init__(self, fmt: str, datefmt: str, enable_color: bool) -> None:
        super().__init__(fmt=fmt, datefmt=datefmt)
        self._enable_color = enable_color

    def format(self, record: logging.LogRecord) -> str:
        original = record.levelname
        try:
            if self._enable_color:
                record.levelname = self._color_levelname(
                    record.levelname, record.levelno
                )
            # Make a copy of the record to avoid mutating the original, since format() can be called multiple times for the same record by multiple handlers
            return super().format(record)
        finally:
            record.levelname = original

    @staticmethod
    def _color_datetime(dt_str: str) -> str:
        return f"{Fore.CYAN}{dt_str}{Style.RESET_ALL}"

    @staticmethod
    def _color_levelname(levelname: str, levelno: int) -> str:
        # Color the LOG LEVEL
        if levelno >= logging.CRITICAL:
            return f"{Fore.MAGENTA}{Style.BRIGHT}{levelname}{Style.RESET_ALL}"
        if levelno >= logging.ERROR:
            return f"{Fore.RED}{Style.BRIGHT}{levelname}{Style.RESET_ALL}"
        if levelno >= logging.WARNING:
            return f"{Fore.YELLOW}{Style.BRIGHT}{levelname}{Style.RESET_ALL}"
        if levelno >= logging.INFO:
            return f"{Fore.GREEN}{levelname}{Style.RESET_ALL}"
        return f"{Fore.CYAN}{levelname}{Style.RESET_ALL}"


def setup_logging(cfg: LoggingConfig) -> None:
    root = logging.getLogger()
    # Clear existing handlers
    if root.hasHandlers():
        root.handlers.clear()

    root.setLevel(cfg.level)
    root.propagate = False

    # If a log file is specified, disable color completely
    color_enabled = False if cfg.log_file else cfg.color

    # Initialize colorama once. If color is disabled, strip ANSI if any slips through.
    # convert=True helps on Windows terminals that need conversion.
    colorama_init(autoreset=True, strip=not color_enabled)
    colors.set_enabled(color_enabled)

    base_fmt = "%(asctime)s;%(levelname)s;%(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(ColorLevelFormatter(base_fmt, date_fmt, color_enabled))
    root.addHandler(stream_handler)

    if cfg.log_file:
        file_handler = logging.FileHandler(cfg.log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(base_fmt, date_fmt))
        root.addHandler(file_handler)
    logging.getLogger().info("logger configured")
