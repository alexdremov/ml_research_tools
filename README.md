# ML Research Tools

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Documentation](https://github.com/alexdremov/ml_research_tools/actions/workflows/docs.yml/badge.svg)](https://github.com/alexdremov/ml_research_tools/actions/workflows/docs.yml)
[![Documentation Status](https://img.shields.io/badge/docs-latest-brightgreen.svg)](https://alexdremov.github.io/ml_research_tools/)
[![Tests](https://github.com/alexdremov/ml_research_tools/actions/workflows/test.yml/badge.svg)](https://github.com/alexdremov/ml_research_tools/actions/workflows/test.yml)

A comprehensive toolkit for machine learning research workflows, designed to streamline common tasks in experimentation, documentation, and deployment processes.

## Key Features

- **LaTeX Tools**
  - Grammar and style checker for LaTeX documents
  - Automatic suggestions for improving technical writing

- **LLM Integration**
  - Easy interaction with OpenAI and compatible LLMs
  - Chat and completion interfaces with robust error handling
  - Automatic retries and caching to reduce API costs

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
  api_key: null
```

### Command-line Arguments

Configuration can be overridden using command-line arguments:

```bash
ml_research_tools --log-level DEBUG --redis-host redis.example.com --llm-model gpt-4-turbo paper.tex latex-grammar paper.tex
```

Available configuration options:

| Option           | Description                   | Default      |
|------------------|-------------------------------|--------------|
| `--config`       | Path to configuration file    | ~/.config/ml_research_tools/config.yaml |
| `--log-level`    | Logging level                 | INFO         |
| `--log-file`     | Path to log file              | None         |
| `--redis-host`   | Redis host                    | localhost    |
| `--redis-port`   | Redis port                    | 6379         |
| `--redis-db`     | Redis database number         | 0            |
| `--redis-password` | Redis password              | None         |
| `--redis-disable` | Disable Redis caching   | Enabled      |
| `--redis-recache` | Recache results               | False        |
| `--llm-api-key`  | API key for LLM service       | None         |
| `--llm-base-url` | Base URL for LLM API          | https://api.openai.com/v1 |
| `--llm-model`    | LLM model to use              | gpt-3.5-turbo |
| `--llm-max-tokens` | Maximum tokens for response | 8000         |
| `--llm-temperature` | Sampling temperature      | 0.01         |
| `--llm-top-p`    | Top-p sampling parameter      | 1.0          |
| `--llm-retry-attempts` | Retry attempts      | 3            |
| `--llm-retry-delay` | Base delay between retries | 5           |

## Development

### Project Structure

```
ml_research_tools/
├── __init__.py        # Package initialization
├── __main__.py        # CLI entry point
├── core/              # Core functionality
│   ├── __init__.py
│   ├── base_tool.py   # Base class for tools
│   ├── config.py      # Configuration system
│   ├── llm_tools.py   # LLM integration utilities
│   └── logging_tools.py # Logging utilities
├── cache/             # Caching system
│   ├── __init__.py
│   └── redis.py       # Redis caching implementation
├── exp/               # Experiment management
│   ├── __init__.py
│   └── wandb_downloader_tool.py # W&B run logs downloader
├── kube/              # Kubernetes utilities
│   ├── __init__.py
│   └── pod_forward_tool.py # Pod port forwarding
└── tex/               # LaTeX utilities
    ├── __init__.py
    └── latex_grammar_tool.py # LaTeX grammar checker
```

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

    def add_arguments(self, parser):
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

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## LLM Disclosure

This project is wildly LLM-written (though, widely reviewed by me)
