Usage
=====

ML Research Tools provides a command-line interface for accessing various tools. This guide covers basic usage patterns and common examples.

Command-Line Interface
---------------------

The package provides a single command-line entry point ``ml_research_tools`` with subcommands for each tool:

.. code-block:: bash

    ml_research_tools [global options] <tool-name> [tool options]

Global Options
-------------

These options apply to all tools:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Option
     - Description
   * - ``--config FILE``
     - Path to configuration file (default: ~/.config/ml_research_tools/config.yaml)
   * - ``--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}``
     - Set logging level (default: INFO)
   * - ``--log-file FILE``
     - Log to file instead of stderr
   * - ``--redis-host HOST``
     - Redis host (default: localhost)
   * - ``--redis-port PORT``
     - Redis port (default: 6379)
   * - ``--redis-db DB``
     - Redis database number (default: 0)
   * - ``--redis-disable``
     - Disable Redis caching
   * - ``--llm-api-key KEY``
     - API key for LLM service
   * - ``--llm-model MODEL``
     - LLM model to use (default: gpt-3.5-turbo)
   * - ``--help``
     - Show help message and exit

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

Common Usage Patterns
-------------------

Using Configuration Files
~~~~~~~~~~~~~~~~~~~~~~~~

Create a configuration file to save common settings:

.. code-block:: yaml

    # ~/.config/ml_research_tools/config.yaml
    logging:
      level: INFO
    redis:
      host: localhost
      port: 6379
      enabled: true
    llm:
      model: gpt-4
      api_key: your-api-key-here

Using Environment Variables
~~~~~~~~~~~~~~~~~~~~~~~~~~

You can also use environment variables for configuration:

.. code-block:: bash

    export OPENAI_API_KEY=your-api-key-here
    export WANDB_ENTITY=your-wandb-username
    ml_research_tools wandb-downloader --project myproject

Scripting
~~~~~~~~~

ML Research Tools can be used programmatically in Python scripts:

.. code-block:: python

    from ml_research_tools.tex import LatexGrammarTool
    from ml_research_tools.core.config import Config
    
    # Create configuration
    config = Config(llm={"api_key": "your-api-key"})
    
    # Initialize the tool
    tool = LatexGrammarTool({})
    
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

    from ml_research_tools.core import Config, setup_services
    from ml_research_tools.tex import LatexGrammarTool

    # Load configuration
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

    # Execute the tool
    exit_code = tool.execute(config, args)

For more detailed examples, see the individual tool documentation pages. 