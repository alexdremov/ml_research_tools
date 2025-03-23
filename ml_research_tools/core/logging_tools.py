"""Logging configuration for ML Research Tools."""

import logging
import os
import sys
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

# Define a global console that can be reused
_console = None


def get_console(theme: Optional[dict] = None) -> Console:
    """Get a Rich console with optional theme.

    Args:
        theme: Optional theme dictionary for the console

    Returns:
        Rich Console object
    """
    global _console

    if _console is None:
        if theme:
            _console = Console(theme=Theme(theme))
        else:
            # Default theme for the application
            default_theme = {
                "info": "dim cyan",
                "user": "bold green",
                "assistant": "bold blue",
                "system": "yellow",
                "error": "bold red",
                "warning": "yellow",
                "success": "green",
                "tool": "magenta",
                "stats": "cyan",
                "cache": "bright_blue",
            }
            _console = Console(theme=Theme(default_theme))

    return _console


def setup_logging(log_level: str, log_file: Optional[str] = None) -> None:
    """Set up logging configuration.

    Args:
        log_level: Logging level.
        log_file: Path to log file. If None, only logs to console.
    """
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Use Rich for console logging
    console = get_console()
    rich_handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
        show_time=True,
        markup=True,
        log_time_format="[%X]",
    )
    rich_handler.setLevel(log_level.upper())
    root_logger.addHandler(rich_handler)

    # Add file handler if log_file is specified
    if log_file:
        # Create log directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name.

    Args:
        name: Name of the logger.

    Returns:
        Logger instance.
    """
    return logging.getLogger(name)
