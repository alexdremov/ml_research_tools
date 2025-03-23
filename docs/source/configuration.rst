Configuration
=============

ML Research Tools can be configured through multiple methods with a cascading priority system.

Configuration Priority
---------------------

Configuration values are determined with the following priority (highest to lowest):

1. Command-line arguments
2. Configuration file
3. Default values

Configuration File
-----------------

By default, the configuration is stored in ``~/.config/ml_research_tools/config.yaml``.
If this file doesn't exist, it will be created with default values when the tool is first run.

Example Configuration
~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

    logging:
      level: INFO
    redis:
      host: localhost
      port: 6379
      db: 0
      enabled: true
      ttl: 604800  # 7 days in seconds
    llm:
      default: "openai"  # Default preset to use
      presets:
        openai:
          base_url: https://api.openai.com/v1
          model: gpt-3.5-turbo
          max_tokens: 8000
          temperature: 0.01
          top_p: 1.0
          retry_attempts: 3
          retry_delay: 5
          api_key: null
          tier: standard

        ollama:
          model: gemma3
          base_url: http://127.0.0.1:3333/v1/

        perplexity:
          base_url: https://api.perplexity.ai/
          model: sonar-pro
          max_tokens: 128000
          temperature: 0.01
          api_key: null
          tier: premium

Command-line Arguments
---------------------

Configuration can be overridden using command-line arguments. Global options apply to all tools:

.. code-block:: bash

    ml_research_tools --log-level DEBUG --redis-host redis.example.com --llm-preset premium

Configuration Reference
---------------------

.. program-output:: ml_research_tools --help


Tool-Specific Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~

Some tools have additional configuration options that can be specified in the configuration file or as command-line arguments. See the documentation for each tool for details.
