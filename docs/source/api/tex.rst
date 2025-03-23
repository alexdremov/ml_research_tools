LaTeX Tools Module
================

.. py:currentmodule:: ml_research_tools.tex

The tex module provides tools for working with LaTeX documents, particularly for improving grammar and style.

LaTeX Grammar Tool
----------------

.. automodule:: ml_research_tools.tex.latex_grammar_tool
   :members:
   :undoc-members:
   :show-inheritance:

Usage Examples
-------------

Command Line
~~~~~~~~~~~

.. code-block:: bash

    # Basic usage
    ml_research_tools latex-grammar paper.tex --output paper_improved.tex

    # Customize prompt
    ml_research_tools latex-grammar paper.tex --system-prompt "Your custom prompt"

    # Generate a diff file
    ml_research_tools latex-grammar paper.tex --diff diff.txt

    # Generate a latexdiff file
    ml_research_tools latex-grammar paper.tex --latexdiff diff.tex

Python API
~~~~~~~~~

.. code-block:: python

    from ml_research_tools.core import Config, setup_services
    from ml_research_tools.tex import LatexGrammarTool
    import argparse

    # Create configuration
    config = Config.from_dict({
        "llm": {
            "model": "gpt-3.5-turbo",
            "api_key": "your-api-key"
        }
    })

    # Set up services
    services = setup_services(config)

    # Create tool instance
    tool = LatexGrammarTool(services)

    # Set up arguments
    args = argparse.Namespace(
        input_file="paper.tex",
        output="paper_improved.tex",
        diff=None,
        latexdiff=None,
        system_prompt=None,
        user_prompt=None,
        max_words=1024,
        config=None,
    )

    # Execute the tool
    exit_code = tool.execute(config, args) 