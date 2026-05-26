"""
logger.py — Rich-enhanced logging for Instagram MCP Server.

Provides a pre-configured logger that writes structured output to both
the terminal (via Rich) and a rotating log file.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

from config import Config

# ─── Rich console theme ───────────────────────────────────────────────────────
_THEME = Theme(
    {
        "logging.level.debug": "dim cyan",
        "logging.level.info": "bold green",
        "logging.level.warning": "bold yellow",
        "logging.level.error": "bold red",
        "logging.level.critical": "bold white on red",
        "repr.url": "underline cyan",
        "repr.path": "bold magenta",
    }
)

console = Console(theme=_THEME, stderr=True)


def get_logger(name: str = "instagram-mcp") -> logging.Logger:
    """
    Return a configured logger.

    Usage:
        from logger import get_logger
        log = get_logger(__name__)
        log.info("Hello!")
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        # Already configured — return as-is (idempotent)
        return logger

    level = getattr(logging, Config.log_level, logging.INFO)
    logger.setLevel(level)

    # ── Rich console handler ──────────────────────────────────────────────
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=True,
        rich_tracebacks=True,
        tracebacks_show_locals=False,
        markup=True,
        log_time_format="[%H:%M:%S]",
    )
    rich_handler.setLevel(level)
    rich_handler.setFormatter(logging.Formatter("%(message)s", datefmt="[%X]"))
    logger.addHandler(rich_handler)

    # ── Rotating file handler ─────────────────────────────────────────────
    try:
        file_handler = RotatingFileHandler(
            Config.log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)  # Always verbose to file
        file_handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(file_handler)
    except OSError as exc:
        logger.warning(f"Could not open log file {Config.log_file}: {exc}")

    logger.propagate = False
    return logger


# Module-level default logger
log = get_logger("instagram-mcp")
