import logging
from logging.handlers import RotatingFileHandler

from .terminal import colorize

logger = logging.getLogger("csv2cwms")


class ColorFormatter(logging.Formatter):
    """Logging Formatter that colorizes the level name."""

    LEVEL_COLORS = {
        logging.DEBUG: "cyan",
        logging.INFO: "blue",
        logging.WARNING: "yellow",
        logging.ERROR: "red",
        logging.CRITICAL: "magenta",
    }

    def formatTime(self, record, datefmt=None):
        """Override to colorize asctime in gray."""
        timestr = super().formatTime(record, datefmt)
        return colorize(timestr, "gray")

    def format(self, record):
        level_color = self.LEVEL_COLORS.get(record.levelno, "reset")
        record.levelname = colorize(record.levelname, level_color)
        return super().format(record)


def setup_logger(
    log_path: str = "",
    max_log_size_mb: int = 5,
    backup_count: int = 3,
    show_console: bool = True,
    verbose: bool = False,
):
    """Set up logger with rotating file handler

    Args:
        log_path (str): Path to the log file
        max_log_size_mb (int): Maximum log file size in MB before rotating
        backup_count (int): Number of backup log files to keep
        show_console (bool): Log to console as well as file

    # Example usage
    logger.info("This is an info message")
    logger.error("This is an error message")

    Returns:
        logger: logging.Logger
    """

    # Remove the default logger handlers from cwms-cli so we can set up our own
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
    # Create formatter and attach to handler
    formatter = ColorFormatter(
        "[%(asctime)s] [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    # Setup the logger if it has not already been configured
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    if log_path:
        # Create rotating file handler
        file_handler = RotatingFileHandler(
            log_path, maxBytes=max_log_size_mb * 1024 * 1024, backupCount=backup_count
        )
        file_handler.setLevel(logging.DEBUG)

        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Setup console handler if needed
    if not logger.hasHandlers() or show_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    logger.debug(f"Logger configured with log file: {log_path}")
    return logger
