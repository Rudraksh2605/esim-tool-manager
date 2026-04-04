"""
Centralized logging configuration for the eSim Tool Manager.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


_LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
_LOG_FILE = _LOG_DIR / "tool_manager.log"
_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_MAX_LOG_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 3

_initialized = False


def setup_logging(verbose: bool = False) -> logging.Logger:
    """
    Initialize the shared application logger.

    File logging always captures DEBUG details. Console logging stays quiet by
    default and only emits DEBUG output when verbose mode is enabled.
    """

    global _initialized

    logger = logging.getLogger("esim_tool_manager")

    if _initialized:
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(
                handler, RotatingFileHandler
            ):
                handler.setLevel(logging.DEBUG if verbose else logging.WARNING)
        return logger

    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT)

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

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if verbose else logging.WARNING)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    _initialized = True
    logger.debug("Logging system initialized (verbose=%s)", verbose)
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child logger within the application namespace."""

    return logging.getLogger(f"esim_tool_manager.{name}")
