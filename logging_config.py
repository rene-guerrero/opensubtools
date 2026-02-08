#!/usr/bin/env python3
"""Logging configuration for subtitle tools.

Provides centralized logging setup with console and file output.
Supports emoji output and configurable log levels.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

from config import get_config


def setup_logging(log_file: Optional[str | Path] = None,
                 level: str = "INFO",
                 use_emoji: bool = True) -> logging.Logger:
    """Setup logging with console and optional file handlers.

    Args:
        log_file: Optional path to log file. If None, logs to console only.
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        use_emoji: Whether to include emoji in output

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("subtitles")
    logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Console handler with emoji support
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))

    if use_emoji:
        formatter = EmojiFormatter(
            '%(emoji)s %(message)s'
        )
    else:
        formatter = logging.Formatter(
            '[%(levelname)s] %(message)s'
        )

    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        try:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_path, encoding='utf-8')
            file_handler.setLevel(getattr(logging, level.upper()))
            file_formatter = logging.Formatter(
                '%(asctime)s [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"Could not setup file logging: {e}")

    return logger


class EmojiFormatter(logging.Formatter):
    """Custom formatter that adds emoji based on log level."""

    EMOJI_MAP = {
        logging.DEBUG: "🔍",
        logging.INFO: "ℹ️ ",
        logging.WARNING: "⚠️ ",
        logging.ERROR: "❌",
        logging.CRITICAL: "🔴",
    }

    def format(self, record):
        record.emoji = self.EMOJI_MAP.get(record.levelno, "")
        return super().format(record)


def get_logger(name: str = "subtitles") -> logging.Logger:
    """Get logger instance. Setup if not already configured."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        # Auto-setup with config defaults
        config = get_config()
        setup_logging(
            log_file=config.log_file,
            use_emoji=config.use_emoji,
            level="DEBUG" if config.verbose else "INFO"
        )
    return logger
