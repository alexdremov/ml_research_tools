Usage
=====

ML Research Tools provides a command-line interface for accessing various tools. This guide covers basic usage patterns and common examples.

Command-Line Interface
---------------------

The package provides a single command-line entry point ``ml_research_tools`` with subcommands for each tool:

.. code-block:: bash

    ml_research_tools [global options] <tool-name> [tool options]


.. program-output:: ml_research_tools --help

Available Tools
--------------

The toolkit includes the following tools:

LaTeX Grammar Tool
~~~~~~~~~~~~~~~~~

Check and improve grammar in LaTeX documents:

.. code-block:: bash

    ml_research_tools latex-grammar paper.tex --output-file improved_paper.tex

Ask Document Tool
~~~~~~~~~~~~~~~

Chat with document content using LLMs:

.. code-block:: bash

    ml_research_tools ask-document research_paper.pdf

W&B Downloader Tool
~~~~~~~~~~~~~~~~~

Download Weights & Biases run logs:

.. code-block:: bash

    ml_research_tools wandb-downloader --entity myuser --project myproject

Kubernetes Pod Forward Tool
~~~~~~~~~~~~~~~~~~~~~~~~~

Forward ports to Kubernetes pods:

.. code-block:: bash

    ml_research_tools kube-pod-forward --namespace default web-app


Scripting
~~~~~~~~~

ML Research Tools can be used programmatically in Python scripts:

.. code-block:: python

    from ml_research_tools.tex import LatexGrammarTool
    from ml_research_tools.core.config import Config
    from ml_research_tools.core.service_provider import ServiceProvider
    from ml_research_tools.core.service_factories import register_common_services

    # Create configuration
    config = Config.from_dict({
        "llm": {
            "default": "standard",
            "presets": {
                "standard": {
                    "api_key": "your-api-key",
                    "model": "gpt-3.5-turbo",
                    "tier": "standard"
                }
            }
        }
    })

    # Create service provider
    services = ServiceProvider(config)
    register_common_services(services)

    # Initialize the tool
    tool = LatexGrammarTool(services)

    # Create args object with required parameters
    class Args:
        pass

    args = Args()
    args.input_file = "paper.tex"
    args.output_file = "improved_paper.tex"

    # Execute the tool
    tool.execute(config, args)

Getting Help
-----------

To see a list of available tools:

.. code-block:: bash

    ml_research_tools --list-tools

To get help for a specific tool:

.. code-block:: bash

    ml_research_tools TOOL --help

    # For example:
    ml_research_tools latex-grammar --help

LLM Features
-----------

The tools that use LLM capabilities support selecting different models:

.. code-block:: bash

    # Use a specific preset
    ml_research_tools --llm-preset=premium latex-grammar paper.tex

    # Use a specific tier
    ml_research_tools  --llm-tier=standard latex-grammar paper.tex

To list available LLM presets:

.. code-block:: bash

    ml_research_tools --list-presets

Using Redis Caching
------------------

Many tools support Redis caching to speed up repeated operations:

.. code-block:: bash

    # Enable Redis caching
    ml_research_tools --redis-host=localhost --redis-port=6379 latex-grammar paper.tex

    # Disable Redis caching
    ml_research_tools --redis-disable latex-grammar paper.tex

Python API
---------

You can also use ML Research Tools directly in your Python code:

.. code-block:: python

    from ml_research_tools.core.config import Config
    from ml_research_tools.core.service_provider import ServiceProvider
    from ml_research_tools.core.service_factories import register_common_services
    from ml_research_tools.tex import LatexGrammarTool

    # Load configuration
    config = Config.from_dict({
        "llm": {
            "default": "standard",
            "presets": {
                "standard": {
                    "model": "gpt-3.5-turbo",
                    "api_key": "your-api-key",
                    "tier": "standard"
                }
            }
        }
    })

    # Set up services
    services = ServiceProvider(config)
    register_common_services(services)

    # Create tool instance
    tool = LatexGrammarTool(services)

    # Execute the tool
    exit_code = tool.execute(config, args)

For more detailed examples, see the individual tool documentation pages.
