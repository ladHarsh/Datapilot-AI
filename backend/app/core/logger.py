"""
core/logger.py
──────────────
Centralised logging configuration.

Creates three named loggers:
  • app_logger      — general application events
  • db_logger       — database connection / engine events
  • query_logger    — SQL query execution events

All loggers write to both the console and a rotating file.
"""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import settings

# ── Directories ───────────────────────────────────────────────────────────────
LOG_DIR = Path(settings.LOG_FOLDER)
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "app.log"

# ── Format ────────────────────────────────────────────────────────────────────
_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)

# ── Handlers ──────────────────────────────────────────────────────────────────
def _build_file_handler() -> RotatingFileHandler:
    handler = RotatingFileHandler(
        filename=LOG_FILE,
        maxBytes=10 * 1024 * 1024,   # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(_formatter)
    return handler


def _build_console_handler() -> logging.StreamHandler:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_formatter)
    return handler


def _create_logger(name: str) -> logging.Logger:
    """Build and return a named logger with rotating file + console handlers."""
    logger = logging.getLogger(name)
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)

    if not logger.handlers:
        logger.addHandler(_build_file_handler())
        logger.addHandler(_build_console_handler())

    # Prevent propagation to root logger to avoid duplicate messages
    logger.propagate = False
    return logger


# ── Public loggers ────────────────────────────────────────────────────────────
app_logger: logging.Logger = _create_logger("app")
db_logger: logging.Logger = _create_logger("database")
query_logger: logging.Logger = _create_logger("query")
