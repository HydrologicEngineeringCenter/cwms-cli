import logging
from logging.handlers import RotatingFileHandler

logger = logging.getLogger("scada_ts")


def setup_logger(
    log_path, max_log_size_mb=5, backup_count=3, show_console=True, verbose=False
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
    # Setup the logger if it has not already been configured
    if not logger.hasHandlers():
        # Configure logger
        logger.setLevel(logging.DEBUG if verbose else logging.INFO)

        # Create rotating file handler
        file_handler = RotatingFileHandler(
            log_path, maxBytes=max_log_size_mb * 1024 * 1024, backupCount=backup_count
        )
        file_handler.setLevel(logging.DEBUG)

        # Create formatter and attach to handler
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Log to console as well
        if show_console:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
    logger.debug(f"Logger configured with log file: {log_path}")
    return logger
