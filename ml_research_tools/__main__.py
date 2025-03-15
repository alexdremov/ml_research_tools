"""Command-line interface for ML Research Tools."""

import argparse
import importlib
import inspect
import os
import pathlib
import pkgutil
import sys
from typing import Dict, List, Optional, Type

# Import Rich for formatted output
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme
from rich.traceback import install as install_rich_traceback
from rich_argparse import HelpPreviewAction, RichHelpFormatter

# Install rich traceback handler for better error display
install_rich_traceback(show_locals=True)

from ml_research_tools.core.base_tool import BaseTool
from ml_research_tools.core.config import add_config_args, get_config
from ml_research_tools.core.logging_tools import get_console, get_logger
from ml_research_tools.core.service_factories import setup_services
from ml_research_tools.core.service_provider import ServiceProvider

logger = get_logger("ml_research_tools")

# Get console for rich output
console = get_console()


def discover_tools() -> Dict[str, Type[BaseTool]]:
    """
    Discover all available tools by finding BaseTool subclasses.

    Returns:
        A dictionary mapping tool names to tool classes
    """
    tools = {}

    # Import all modules in the ml_research_tools package
    package_dir = os.path.dirname(os.path.abspath(__file__))
    for _, module_name, is_pkg in pkgutil.iter_modules([package_dir]):
        if is_pkg:
            # Recurse into subpackages
            try:
                module = importlib.import_module(f"ml_research_tools.{module_name}")
                package_path = os.path.dirname(inspect.getfile(module))

                for _, submodule_name, _ in pkgutil.iter_modules([package_path]):
                    try:
                        full_module_name = f"ml_research_tools.{module_name}.{submodule_name}"
                        importlib.import_module(full_module_name)
                    except ImportError:
                        logger.debug(f"Failed to import {full_module_name}")
                        pass
            except ImportError:
                logger.debug(f"Failed to import ml_research_tools.{module_name}")
                pass

    # Find all BaseTool subclasses
    for tool_class in BaseTool.__subclasses__():
        tools[tool_class.name] = tool_class

    return tools


def display_llm_presets(config):
    """Display available LLM presets in a formatted table.

    Args:
        config: Configuration object containing LLM presets
    """
    table = Table(title="Available LLM Presets")

    # Add columns
    table.add_column("Preset Name", style="cyan")
    table.add_column("Model", style="green")
    table.add_column("Tier", style="blue")
    table.add_column("Default", style="yellow")

    # Add rows for each preset
    default_preset = config.llm_presets.default
    for name, preset in config.llm_presets.presets.items():
        is_default = "✓" if name == default_preset else ""
        table.add_row(name, preset.model, preset.tier, is_default)

    console.print(table)
    console.print(
        "\n[info]Use [bold]--llm-preset=NAME[/bold] or [bold]--llm-tier=TIER[/bold] to select a specific preset.[/info]"
    )


def display_available_tools(tools):
    """Display available tools in a formatted table.

    Args:
        tools: Dictionary of tool names to tool classes
    """
    table = Table(title="Available Tools")
    table.add_column("Tool", style="cyan")
    table.add_column("Description", style="green")

    for name, tool_class in sorted(tools.items()):
        table.add_row(name, tool_class.description)

    console.print(table)
    console.print(
        "\n[info]Use [bold]ml_research_tools TOOL --help[/bold] for more information about a specific tool.[/info]"
    )


def main(args: Optional[List[str]] = None) -> int:
    """Execute the main CLI interface.

    Args:
        args: Command line arguments. If None, sys.argv[1:] is used.

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    parser = argparse.ArgumentParser(
        "ml_research_tools",
        description="ML Research Tools - A collection of utilities for ML research",
        formatter_class=RichHelpFormatter,
    )

    # Add configuration arguments
    add_config_args(parser)

    # Add global arguments
    parser.add_argument(
        "--list-presets", action="store_true", help="List available LLM presets and exit"
    )

    parser.add_argument("--list-tools", action="store_true", help="List available tools and exit")

    parser.add_argument(
        "--generate-help-preview",
        action=HelpPreviewAction,
    )

    parser.add_argument(
        "--rich-capture-output",
        default=None,
        help="Capture output in a rich format to this file",
    )

    # Add subparsers for each tool
    subparsers = parser.add_subparsers(
        dest="tool",
        title="tools",
        help="Available tools",
    )

    # Add help command
    subparsers.add_parser(
        "help",
        help="Display help information about available tools",
    )

    # Add tool subparsers
    tools = discover_tools()
    for tool_name, tool_class in tools.items():
        tool_parser = tool_class.add_subparser(subparsers)
        tool_parser.add_argument(
            "--generate-tool-help-preview",
            action=HelpPreviewAction,
        )

    parsed_args = parser.parse_args(args)
    main_with_args(parser, parsed_args)
    if parsed_args.rich_capture_output:
        # Capture output in a rich format
        console.save_svg(parsed_args.rich_capture_output, title="ML Research Tools Output")


def main_with_args(parser, parsed_args):
    # Load configuration
    tools = discover_tools()
    config, config_file = get_config(parsed_args)

    # Create application-wide service provider
    app_services = setup_services(
        config=config,
        default_llm_preset=parsed_args.llm_preset,
        default_llm_tier=parsed_args.llm_tier,
    )

    try:
        # List tools if requested
        if parsed_args.list_tools:
            display_available_tools(tools)
            return 0

        # List presets if requested (before setting up logging to avoid unnecessary output)
        if parsed_args.list_presets:
            display_llm_presets(config)
            return 0

        # Set up logging
        log_level = "DEBUG" if parsed_args.verbose else config.logging.level
        setup_logging = importlib.import_module(
            "ml_research_tools.core.logging_tools"
        ).setup_logging
        setup_logging(
            log_level=log_level,
            log_file=config.logging.file,
        )

        logger.info(f"Using configuration file: {config_file}")
        logger.debug(f"Using configuration: {config}")

        # If no tool is specified, print help and exit
        if not parsed_args.tool or parsed_args.tool == "help":
            # Print a welcome message
            console.print(
                Panel(
                    "[bold]ML Research Tools[/bold]\nA collection of utilities for ML research",
                    border_style="green",
                )
            )
            display_available_tools(tools)
            parser.print_help()
            return 0

        elif parsed_args.tool in tools:
            tool_instance = tools[parsed_args.tool](app_services)
            # Call the execute method
            return tool_instance.execute(config, parsed_args)
        elif hasattr(parsed_args, "func"):
            return parsed_args.func(config, parsed_args)
        else:
            logger.error(f"Unknown tool or missing execute function: {parsed_args.tool}")
            return 1

    except Exception as e:
        if "parsed_args" in locals() and hasattr(parsed_args, "verbose") and parsed_args.verbose:
            console.print_exception(show_locals=True)
            raise
        else:
            logger.error(f"Error running tool: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
