Configuration
=============

ML Research Tools can be configured through multiple methods with a cascading priority system.

Configuration Priority
---------------------

Configuration values are determined with the following priority (highest to lowest):

1. Command-line arguments
2. Environment variables
3. Configuration file
4. Default values

Configuration File
-----------------

By default, the configuration is stored in ``~/.config/ml_research_tools/config.yaml``.
If this file doesn't exist, it will be created with default values when the tool is first run.

Example Configuration
~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

    logging:
      level: INFO
      file: /path/to/log/file.log
    
    redis:
      host: localhost
      port: 6379
      db: 0
      password: optional_password
      enabled: true
      ttl: 604800  # 7 days in seconds
    
    llm:
      base_url: https://api.openai.com/v1
      model: gpt-3.5-turbo
      max_tokens: 8000
      temperature: 0.01
      top_p: 1.0
      retry_attempts: 3
      retry_delay: 5
      api_key: null  # Will be overridden by OPENAI_API_KEY env var if available

Environment Variables
--------------------

Several environment variables are recognized:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Environment Variable
     - Description
   * - ``OPENAI_API_KEY``
     - API key for OpenAI services
   * - ``ANTHROPIC_API_KEY``
     - API key for Anthropic services
   * - ``ML_RESEARCH_TOOLS_CONFIG``
     - Path to configuration file
   * - ``WANDB_ENTITY``
     - W&B entity for wandb-downloader
   * - ``WANDB_PROJECT``
     - W&B project for wandb-downloader

Command-line Arguments
---------------------

Configuration can be overridden using command-line arguments. Global options apply to all tools:

.. code-block:: bash

    ml_research_tools --log-level DEBUG --redis-host redis.example.com --llm-model gpt-4-turbo

Configuration Reference
---------------------

Logging
~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 20 55

   * - Option
     - Default
     - Description
   * - ``level``
     - ``INFO``
     - Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
   * - ``file``
     - ``None``
     - Path to log file (logs to stderr if not specified)

Redis Cache
~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 20 55

   * - Option
     - Default
     - Description
   * - ``host``
     - ``localhost``
     - Redis server hostname
   * - ``port``
     - ``6379``
     - Redis server port
   * - ``db``
     - ``0``
     - Redis database number
   * - ``password``
     - ``None``
     - Redis password (if authentication is required)
   * - ``enabled``
     - ``true``
     - Enable/disable Redis caching
   * - ``ttl``
     - ``604800``
     - Time-to-live for cache entries (in seconds)

LLM Configuration
~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 20 55

   * - Option
     - Default
     - Description
   * - ``base_url``
     - ``https://api.openai.com/v1``
     - API base URL
   * - ``model``
     - ``gpt-3.5-turbo``
     - Model identifier
   * - ``max_tokens``
     - ``8000``
     - Maximum tokens for response
   * - ``temperature``
     - ``0.01``
     - Sampling temperature (0.0 to 2.0)
   * - ``top_p``
     - ``1.0``
     - Top-p sampling parameter
   * - ``retry_attempts``
     - ``3``
     - Number of retry attempts for failed requests
   * - ``retry_delay``
     - ``5``
     - Base delay between retries (in seconds)
   * - ``api_key``
     - ``None``
     - API key for authentication

Tool-Specific Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~

Some tools have additional configuration options that can be specified in the configuration file or as command-line arguments. See the documentation for each tool for details. ¸