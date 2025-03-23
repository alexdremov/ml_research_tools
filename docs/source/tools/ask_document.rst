Ask Document Tool
================

The Ask Document Tool enables interactive chat with document content using large language models.

Description
----------

This tool creates a conversational interface to various document types (PDF, TXT, LaTeX, and URLs), 
allowing users to ask questions about the content and receive natural language responses. 
It leverages large language models to interpret document content while maintaining conversation context.

Supported Document Types
-----------------------

* Text files (``.txt``, ``.md``, etc.)
* Source code files (``.py``, ``.js``, ``.c``, etc.)
* LaTeX documents (``.tex``)
* PDF documents (requires ``PyPDF2``)
* Web URLs (requires ``requests`` and ``beautifulsoup4``)

Usage
-----

.. code-block:: bash

    ml_research_tools ask-document [options] document_path

Options
-------

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Option
     - Default
     - Description
   * - ``--non-interactive``
     - ``False``
     - Run in non-interactive mode with a single query
   * - ``--query``
     - ``None``
     - Query to use in non-interactive mode
   * - ``--verbose``
     - ``False``
     - Show verbose output, including document content

Examples
--------

Interactive chat with a PDF document:

.. code-block:: bash

    ml_research_tools ask-document paper.pdf

Ask a specific question about a LaTeX file:

.. code-block:: bash

    ml_research_tools ask-document thesis.tex --non-interactive --query "What is the main contribution in this paper?"

Chat with content from a website:

.. code-block:: bash

    ml_research_tools ask-document https://example.com/article

Requirements
-----------

For full functionality, the following optional dependencies are recommended:

* ``PyPDF2`` - For PDF document support
* ``requests`` and ``beautifulsoup4`` - For web URL support

Install these dependencies with:

.. code-block:: bash

    pip install PyPDF2 requests beautifulsoup4 