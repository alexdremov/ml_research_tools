LaTeX Grammar Tool
=================

The LaTeX Grammar Tool helps improve the grammar, clarity, and wording of LaTeX documents while preserving
LaTeX commands and mathematical expressions.

Description
----------

This tool processes LaTeX files using a ChatGPT-compatible API to improve grammar and phrasing while
maintaining all LaTeX formatting, commands, and structures.

Usage
-----

.. code-block:: bash

    ml_research_tools latex-grammar [options] input_file.tex

.. program-output:: ml_research_tools latex-grammar --help

Examples
--------

Basic usage:

.. code-block:: bash

    ml_research_tools latex-grammar paper.tex --output-file improved_paper.tex

Create a diff file to review changes:

.. code-block:: bash

    ml_research_tools latex-grammar paper.tex --diff-file paper.diff

Use latexdiff to generate a PDF highlighting changes:

.. code-block:: bash

    ml_research_tools latex-grammar paper.tex --latexdiff-file paper_diff.tex
    pdflatex paper_diff.tex

Configuration
------------

The tool can be customized using a configuration file with the following structure:

.. code-block:: ini

    [api]
    max_words_per_chunk = 1024

    [prompts]
    system = Your custom system prompt here
    user = Your custom user prompt template here

Configuration can be specified with the ``--config-file`` option.
