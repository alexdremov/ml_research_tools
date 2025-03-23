#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ML Research Tools documentation build configuration file.
"""

import importlib.metadata
import os
import sys

# Add project root to path for proper imports
sys.path.insert(0, os.path.abspath("../.."))

# Project information
project = "ML Research Tools"
copyright = "2023-2024, Project Contributors"
author = "Project Contributors"

# The full version, including alpha/beta/rc tags
try:
    release = importlib.metadata.version("ml_research_tools")
except importlib.metadata.PackageNotFoundError:
    release = "dev"
version = ".".join(release.split(".")[:2])

# General configuration
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.autosummary",
    "sphinx_book_theme",
    "sphinx_autodoc_typehints",
    "sphinxcontrib.programoutput",
]

templates_path = ["_templates"]
exclude_patterns = []

# Options for HTML output
html_theme = "sphinx_book_theme"
html_static_path = ["_static"]
html_title = f"{project} {version}"
html_logo = None  # Add logo path if available
html_favicon = None  # Add favicon path if available
html_css_files = [
    "css/custom.css",
]

# Theme options for sphinx-book-theme
html_theme_options = {
    "repository_url": "https://github.com/alexdremov/ml_research_tools",
    "use_repository_button": True,
    "use_issues_button": True,
    "use_edit_page_button": False,
    "use_download_button": True,
    "use_fullscreen_button": True,
    "use_source_button": True,
    "path_to_docs": "docs",
    "show_navbar_depth": 2,
    "show_toc_level": 2,
    "announcement": None,
    "extra_navbar": "",
    "extra_footer": "",
    # Light, minimalistic style
    "light_css_variables": {
        "font-stack": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif",
        "font-stack--monospace": "SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace",
        "color-brand-primary": "#0969da",
        "color-brand-content": "#0969da",
        "color-background-primary": "#ffffff",
        "color-background-secondary": "#f6f8fa",
        "color-background-hover": "#f3f4f6",
        "color-background-border": "#e5e7eb",
        "color-link": "#0969da",
        "color-link--hover": "#014ced",
    },
}

# Napoleon settings
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_use_keyword = True

# Autodoc settings
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
    "member-order": "bysource",
}
autodoc_typehints = "description"
autodoc_member_order = "bysource"
autoclass_content = "both"
autosummary_generate = True

# Intersphinx mapping
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable", None),
    "pandas": ("https://pandas.pydata.org/pandas-docs/stable", None),
    "requests": ("https://requests.readthedocs.io/en/latest/", None),
}
