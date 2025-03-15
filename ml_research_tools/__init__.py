"""ML Research Tools Package.

A collection of tools for machine learning research, including experiment management,
Kubernetes utilities, and LaTeX processing.
"""

from importlib.metadata import version

from ml_research_tools.core.base_tool import BaseTool

# Re-export main components for easier imports
from ml_research_tools.core.config import Config, get_config
from ml_research_tools.core.logging_tools import get_logger, setup_logging
from ml_research_tools.doc import ask_document_tool

# Explicitly import tool classes for discovery
from ml_research_tools.exp import wandb_downloader_tool
from ml_research_tools.kube import pod_forward_tool
from ml_research_tools.tex import latex_grammar_tool

__version__ = version("ml_research_tools")

__all__ = [
    "Config",
    "get_config",
    "BaseTool",
    "get_logger",
    "setup_logging",
]
