ML Research Tools
===============

A comprehensive toolkit for machine learning research workflows, designed to streamline common tasks in experimentation, documentation, and deployment processes.

.. image:: https://img.shields.io/badge/python-3.11+-blue.svg
   :target: https://www.python.org/downloads/
   :alt: Python 3.11+

.. image:: https://img.shields.io/badge/License-MIT-yellow.svg
   :target: https://opensource.org/licenses/MIT
   :alt: License: MIT

.. image:: https://github.com/alexdremov/ml_research_tools/actions/workflows/docs.yml/badge.svg
   :target: https://github.com/alexdremov/ml_research_tools/actions/workflows/docs.yml
   :alt: Documentation

.. image:: https://img.shields.io/badge/docs-latest-brightgreen.svg
   :target: https://alexdremov.github.io/ml_research_tools/
   :alt: Documentation Status

.. image:: https://github.com/alexdremov/ml_research_tools/actions/workflows/test.yml/badge.svg
   :target: https://github.com/alexdremov/ml_research_tools/actions/workflows/test.yml
   :alt: Tests

Key Features
-----------

- **LaTeX Tools**: Grammar and style checker for LaTeX documents
- **Document Interaction**: Interactive chat with document content
- **Experiment Management**: Weights & Biases run logs downloader
- **Kubernetes Tools**: Pod port forwarding with automatic reconnection
- **LLM Integration**: Easy interaction with OpenAI and compatible LLMs
- **Caching System**: Redis-based function result caching

.. toctree::
   :maxdepth: 1
   :caption: Getting Started

   installation
   configuration
   usage

.. toctree::
   :maxdepth: 1
   :caption: Tools

   tools/latex_grammar
   tools/ask_document
   tools/wandb_downloader
   tools/kube_pod_forward

.. toctree::
   :maxdepth: 2
   :caption: API Reference
   :glob:

   api/overview
   api/modules

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
