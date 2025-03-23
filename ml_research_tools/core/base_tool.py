#!/usr/bin/env python3
"""
Base class for all research tools in the ml_research_tools package.
Provides standard interface for argument parsing and execution.
"""

import argparse
import logging
import sys
from abc import ABC, abstractmethod
from typing import Any, List, Optional, Type, TypeVar, cast

# Import rich formatting
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

from ml_research_tools.core.config import Config, get_config
from ml_research_tools.core.service_factories import register_common_services
from ml_research_tools.core.service_provider import ServiceProvider

T = TypeVar("T", bound="BaseTool")


class BaseTool(ABC):
    """
    Base class for all research tools.

    This class defines a standard interface that all tools should implement,
    including methods for parsing arguments and executing the tool's functionality.
    """

    name: str = "base_tool"  # Tool name used for logging and help text
    description: str = "Base tool description"  # Tool description for help text

    def __init__(self, services: ServiceProvider) -> None:
        """Initialize the tool with default values."""
        self.logger = logging.getLogger(self.name)
        # Get a console from logging_tools
        from ml_research_tools.core.logging_tools import get_console

        self.console = get_console()
        self.services = services

    @classmethod
    @abstractmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """
        Add tool-specific arguments to the argument parser.

        Args:
            parser: The argument parser to add arguments to
        """
        pass

    @classmethod
    def add_subparser(cls, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """
        Add a subparser for this tool to a parent parser's subparsers.

        Args:
            subparsers: subparsers object from the parent parser

        Returns:
            The created subparser
        """
        parser = subparsers.add_parser(cls.name, description=cls.description, help=cls.description)
        cls.add_arguments(parser)
        return parser

    @abstractmethod
    def execute(self, config: Config, args: argparse.Namespace) -> int:
        """
        Execute the tool with the provided arguments.

        Args:
            config: Configuration object
            args: Parsed command-line arguments

        Returns:
            Exit code (0 for success, non-zero for error)
        """
        pass

    def execute_from_args(self, args: argparse.Namespace) -> int:
        """
        Execute the tool from parsed arguments.

        Args:
            args: Parsed command-line arguments

        Returns:
            Exit code (0 for success, non-zero for error)
        """
        try:
            config, _ = get_config(args)
            return self.execute(config, args)
        except KeyboardInterrupt:
            self.logger.info("Operation cancelled by user")
            return 130  # Standard exit code for Ctrl+C
        except Exception as e:
            if hasattr(args, "verbose") and args.verbose:
                self.logger.exception(f"Unexpected error: {e}")
            else:
                self.logger.error(f"Unexpected error: {e}")
                self.logger.info("Run with --verbose for full traceback")
            return 1

    def parse_and_execute(self, args: Optional[List[str]] = None) -> int:
        """
        Parse command-line arguments and execute the tool.

        Args:
            args: Command-line arguments (uses sys.argv if None)

        Returns:
            Exit code (0 for success, non-zero for error)
        """
        parser = argparse.ArgumentParser(prog=self.name, description=self.description)
        self.add_arguments(parser)
        parsed_args = parser.parse_args(args)
        return self.execute_from_args(parsed_args)

    # Helper methods for rich formatting

    def create_progress(self, **kwargs: Any) -> Progress:
        """Create a progress bar with rich formatting.

        Returns:
            Rich Progress object
        """
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            **kwargs,
        )
