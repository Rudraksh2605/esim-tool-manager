"""
Centralized Logging Configuration.

Configures a dual-output logging system that writes to both a rotating log file
and the console. All modules in the application share this logger instance.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


_LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
_LOG_FILE = _LOG_DIR / "tool_manager.log"
_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_MAX_LOG_BYTES = 5 * 1024 * 1024  # 5 MB
_BACKUP_COUNT = 3

_initialized = False


def setup_logging(verbose: bool = False) -> logging.Logger:
    """
    Initialize and configure the application-wide logger.

    Creates a rotating file handler (5 MB max, 3 backups) and a console
    handler. The file handler always logs at DEBUG level; the console handler
    respects the verbose flag.

    Args:
        verbose: If True, set console output to DEBUG. Otherwise INFO.

    Returns:
        logging.Logger: The configured root application logger.
    """
    global _initialized

    logger = logging.getLogger("esim_tool_manager")

    if _initialized:
        # Update console handler level if verbose changes
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(
                handler, RotatingFileHandler
            ):
                handler.setLevel(logging.DEBUG if verbose else logging.INFO)
        return logger

    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT)

    # --- File Handler (rotating) ---
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        _LOG_FILE,
        maxBytes=_MAX_LOG_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # --- Console Handler ---
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    _initialized = True
    logger.debug("Logging system initialized (verbose=%s)", verbose)
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a child logger under the application namespace.

    Args:
        name: Module or component name (e.g., 'core.installer').

    Returns:
        logging.Logger: A child logger instance.
    """
    return logging.getLogger(f"esim_tool_manager.{name}")
