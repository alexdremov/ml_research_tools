# ML Research Tools

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Documentation](https://github.com/alexdremov/ml_research_tools/actions/workflows/docs.yml/badge.svg)](https://github.com/alexdremov/ml_research_tools/actions/workflows/docs.yml)
[![Documentation Status](https://img.shields.io/badge/docs-latest-brightgreen.svg)](https://alexdremov.github.io/ml_research_tools/)
[![Tests](https://github.com/alexdremov/ml_research_tools/actions/workflows/test.yml/badge.svg)](https://github.com/alexdremov/ml_research_tools/actions/workflows/test.yml)

A collection of tools for machine learning research, including experiment management, Kubernetes utilities, and LaTeX processing.

## Key Features

![](assets/tools.svg)

- **LaTeX Tools**
  - Grammar and style checker for LaTeX documents
  - Automatic suggestions for improving technical writing

- **LLM Integration**
  - Easy interaction with OpenAI API compatible LLMs
  - Support for multiple model presets and tiers

- **Document Tools**
  - Ask questions and get answers about documentation

- **Experiment Management**
  - Weights & Biases run logs downloader

- **Kubernetes Tools**
  - Pod port forwarding with automatic reconnection

- **Caching System**
  - Redis-based function result caching
  - Transparent caching with decorators

## Installation

### From PyPI (Recommended)

```bash
pip install ml_research_tools
```

### From Source

```bash
git clone https://github.com/alexdremov/ml_research_tools.git
cd ml_research_tools
poetry install
```

## Configuration

The toolkit can be configured through multiple methods, with a cascading priority:

1. Command-line arguments (highest priority)
2. Configuration file
3. Default values (lowest priority)

### Configuration File

By default, the configuration is stored in `~/.config/ml_research_tools/config.yaml`.
If this file doesn't exist, it will be created with default values when the tool is first run.

Example configuration file:

```yaml
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
```

### Command-line Arguments

Configuration can be overridden using command-line arguments:

```bash
ml_research_tools --log-level DEBUG --redis-host redis.example.com --llm-preset premium paper.tex latex-grammar paper.tex
```

```
Usage: ml_research_tools [-h] [--config CONFIG]
                         [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                         [--log-file LOG_FILE] [-v] [--redis-host REDIS_HOST]
                         [--redis-port REDIS_PORT] [--redis-db REDIS_DB]
                         [--redis-password REDIS_PASSWORD] [--redis-disable]
                         [--redis-recache] [--llm-preset LLM_PRESET]
                         [--llm-tier LLM_TIER] [--llm-api-key LLM_API_KEY]
                         [--llm-base-url LLM_BASE_URL] [--llm-model LLM_MODEL]
                         [--llm-max-tokens LLM_MAX_TOKENS]
                         [--llm-temperature LLM_TEMPERATURE]
                         [--llm-top-p LLM_TOP_P]
                         [--llm-retry-attempts LLM_RETRY_ATTEMPTS]
                         [--llm-retry-delay LLM_RETRY_DELAY] [--list-presets]
                         [--list-tools]
                         {help,ask-document,wandb-downloader,kube-pod-forward,latex-grammar}
                         ...

ML Research Tools - A collection of utilities for ML research

Options:
  -h, --help            show this help message and exit
  --list-presets        List available LLM presets and exit
  --list-tools          List available tools and exit

Configuration:
  --config CONFIG       Path to configuration file (default:
                        ~/.config/ml_research_tools/config.yaml)

Logging:
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Logging level
  --log-file LOG_FILE   Path to log file
  -v, --verbose         Enable verbose logging

Redis:
  --redis-host REDIS_HOST
                        Redis host
  --redis-port REDIS_PORT
                        Redis port
  --redis-db REDIS_DB   Redis database number
  --redis-password REDIS_PASSWORD
                        Redis password
  --redis-disable       Disable Redis caching
  --redis-recache       Disable Redis caching retrieval, but allow saving

Llm:
  --llm-preset LLM_PRESET
                        LLM preset name to use (e.g., 'standard', 'premium')
  --llm-tier LLM_TIER   LLM tier to use (e.g., 'standard', 'premium')
  --llm-api-key LLM_API_KEY
                        API key for LLM service
  --llm-base-url LLM_BASE_URL
                        Base URL for the LLM API endpoint
  --llm-model LLM_MODEL
                        LLM model to use
  --llm-max-tokens LLM_MAX_TOKENS
                        Maximum tokens for LLM response
  --llm-temperature LLM_TEMPERATURE
                        Temperature for LLM sampling
  --llm-top-p LLM_TOP_P
                        Top-p value for LLM sampling
  --llm-retry-attempts LLM_RETRY_ATTEMPTS
                        Number of retry attempts for LLM API calls
  --llm-retry-delay LLM_RETRY_DELAY
                        Delay between retry attempts for LLM API calls
                        (seconds)
```


## Development

### Development Workflow

1. Clone the repository
2. Install development dependencies:
   ```bash
   poetry install --with dev
   ```
3. Run tests:
   ```bash
   poetry run pytest
   ```
4. Code quality tools:
   ```bash
   # Format code
   poetry run black .
   poetry run isort .

   # Check typing
   poetry run mypy .

   # Run linter
   poetry run ruff .
   ```

### Adding a New Tool

1. Create a new module in the appropriate directory
2. Implement a class that inherits from `BaseTool`
3. Register arguments in the `add_arguments` method
4. Implement the `execute` method
5. Import the module in `__init__.py` to ensure discovery

Example:

```python
from ml_research_tools.core.base_tool import BaseTool

class MyNewTool(BaseTool):
    name = "my-tool"
    description = "Description of my new tool"

    @classmethod
    def add_arguments(cls, parser):
        parser.add_argument("--option", help="An option for my tool")

    def execute(self, config, args):
        # Implementation
        return 0  # Success
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Documentation

The full documentation is available at [https://alexdremov.github.io/ml_research_tools/](https://alexdremov.github.io/ml_research_tools/).

To build the documentation locally:

```bash
poetry install --with docs
cd docs
poetry run make html
```

Then open `docs/build/html/index.html` in your browser.

## LLM Disclosure

This project is wildly LLM-written (though, widely reviewed by me)
