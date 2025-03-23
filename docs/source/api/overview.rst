API Overview
===========

ML Research Tools provides a Python API for all functionality available through the command line.
This section documents the important classes and functions available for use in your own Python code.

Key Components
------------

Core
~~~~

.. py:currentmodule:: ml_research_tools.core

The core module provides the foundation of the ML Research Tools package:

* :class:`Config` - Configuration management
* :class:`ServiceProvider` - Service dependency injection system
* :class:`BaseTool` - Base class for all tools
* :class:`LLMClient` - Client for LLM API interaction

Cache
~~~~~

.. py:currentmodule:: ml_research_tools.cache

The cache module provides utilities for caching function results:

* :class:`RedisCache` - Redis-based caching implementation
* :func:`cached` - Decorator for caching function results

Tools
~~~~~

Various tool implementations for specific tasks:

* :class:`ml_research_tools.tex.LatexGrammarTool` - LaTeX grammar checking
* :class:`ml_research_tools.doc.AskDocumentTool` - Document question answering
* :class:`ml_research_tools.exp.WandbDownloaderTool` - Weights & Biases run logs downloader
* :class:`ml_research_tools.kube.PodForwardTool` - Kubernetes pod port forwarding

Service Locator Pattern
---------------------

ML Research Tools uses a service locator pattern for dependency injection. The typical usage flow is:

1. Create a configuration object:

   .. code-block:: python

       from ml_research_tools.core import Config
       config = Config.from_dict({"redis": {"enabled": True}})

2. Set up the service provider:

   .. code-block:: python

       from ml_research_tools.core import setup_services
       services = setup_services(config)

3. Create a tool instance with the service provider:

   .. code-block:: python

       from ml_research_tools.tex import LatexGrammarTool
       tool = LatexGrammarTool(services)

4. Execute the tool:

   .. code-block:: python

       import argparse
       args = argparse.Namespace(input_file="paper.tex", output="improved.tex")
       tool.execute(config, args)

Package Structure
---------------

The package is organized into several modules:

- ``ml_research_tools.core`` - Core functionality
- ``ml_research_tools.cache`` - Caching system
- ``ml_research_tools.tex`` - LaTeX processing tools
- ``ml_research_tools.doc`` - Document processing tools
- ``ml_research_tools.exp`` - Experiment management tools
- ``ml_research_tools.kube`` - Kubernetes tools
