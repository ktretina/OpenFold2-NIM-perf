"""Structured logging setup."""

import logging
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler


def setup_logging(
    log_file: Optional[Path] = None,
    level: int = logging.INFO,
    verbose: bool = False,
) -> logging.Logger:
    """
    Setup structured logging with rich console output.

    Args:
        log_file: Optional file path for log output
        level: Logging level
        verbose: If True, set level to DEBUG

    Returns:
        Configured logger
    """
    if verbose:
        level = logging.DEBUG

    # Create logger
    logger = logging.getLogger("bench")
    logger.setLevel(level)
    logger.handlers = []  # Clear any existing handlers

    # Console handler with rich formatting
    console_handler = RichHandler(
        console=Console(stderr=True),
        show_time=True,
        show_path=False,
        markup=True,
        rich_tracebacks=True,
    )
    console_handler.setLevel(level)
    console_formatter = logging.Formatter("%(message)s", datefmt="[%X]")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler with detailed formatting
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)  # Always log everything to file
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


# Global logger instance
logger = setup_logging()
