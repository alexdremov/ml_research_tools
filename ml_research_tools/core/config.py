"""Configuration management for ML Research Tools.

This module handles loading configuration from both a file and command line arguments.
The configuration file is stored at ~/.config/ml_research_tools/config.yaml by default.
"""

import argparse
import os
import pathlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

import yaml

from ml_research_tools.core.logging_tools import get_logger

logger = get_logger(__name__)

# Default config location
DEFAULT_CONFIG_DIR = pathlib.Path.home() / ".config" / "ml_research_tools"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"

# Default configuration values
DEFAULT_CONFIG = {
    "logging": {
        "level": "INFO",
        "file": None,
    },
    "redis": {
        "host": "localhost",
        "port": 6379,
        "db": 0,
        "password": None,
    },
    "llm": {
        "default": "standard",  # Default preset to use
        "presets": {
            "standard": {
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-3.5-turbo",
                "max_tokens": 8000,
                "temperature": 0.01,
                "top_p": 1.0,
                "retry_attempts": 3,
                "retry_delay": 5,
                "api_key": None,
                "tier": "standard",
            },
            "premium": {
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o",
                "max_tokens": 8000,
                "temperature": 0.01,
                "top_p": 1.0,
                "retry_attempts": 3,
                "retry_delay": 5,
                "api_key": None,
                "tier": "premium",
            },
        },
    },
}


@dataclass
class LoggingConfig:
    """Logging configuration."""

    level: str = "INFO"
    file: Optional[str] = None


@dataclass
class RedisConfig:
    """Redis connection configuration."""

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    ttl: int = 60 * 60 * 24 * 7  # 7 days default TTL
    enabled: bool = False
    recache: bool = False


@dataclass
class LLMConfig:
    """LLM (Language Model) API configuration."""

    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-3.5-turbo"
    max_tokens: int | None = None
    temperature: float = 0.01
    top_p: float = 1.0
    retry_attempts: int = 3
    retry_delay: int = 5
    api_key: Optional[str] = None
    tier: str = "standard"


@dataclass
class LLMPresets:
    """Collection of LLM configurations with presets and tiering."""

    default: str = "standard"
    presets: Dict[str, LLMConfig] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize with default presets if empty."""
        if not self.presets:
            self.presets = {
                "standard": LLMConfig(tier="standard"),
                "premium": LLMConfig(model="gpt-4o", tier="premium"),
            }

    def get_config(
        self, preset_name: Optional[str] = None, tier: Optional[str] = None
    ) -> LLMConfig:
        """Get an LLM configuration by name or tier.

        Args:
            preset_name: Name of the preset to use (takes precedence over tier)
            tier: Tier of model to use (e.g., "standard", "premium")

        Returns:
            LLMConfig object

        Raises:
            ValueError: If no matching preset is found
        """
        # If preset name is provided, use it directly
        if preset_name:
            if preset_name in self.presets:
                return self.presets[preset_name]
            else:
                raise ValueError(f"LLM preset '{preset_name}' not found in configuration")

        # If tier is provided, find the first preset matching that tier
        if tier:
            for name, preset in self.presets.items():
                if preset.tier == tier:
                    return preset
            raise ValueError(f"No LLM preset found for tier '{tier}'")

        # If neither is provided, use the default preset
        if self.default in self.presets:
            return self.presets[self.default]

        # If no default can be found, use the first available preset
        if self.presets:
            return next(iter(self.presets.values()))

        # No presets available
        raise ValueError("No LLM presets available in configuration")


@dataclass
class Config:
    """Global application configuration."""

    logging: LoggingConfig = field(default_factory=LoggingConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    llm_presets: LLMPresets = field(default_factory=LLMPresets)

    @property
    def llm(self) -> LLMConfig:
        """Backward compatibility property to get the default LLM config."""
        return self.llm_presets.get_config()

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "Config":
        """Create a Config object from a dictionary.

        Args:
            config_dict: Dictionary containing configuration values.

        Returns:
            Config object.
        """
        logging_config = LoggingConfig(**config_dict.get("logging", {}))
        redis_config = RedisConfig(**config_dict.get("redis", {}))

        # Handle LLM presets
        llm_dict = config_dict.get("llm", {})

        # Check if the config follows the new preset format
        if "presets" in llm_dict:
            # Process presets
            presets = {}
            for preset_name, preset_dict in llm_dict.get("presets", {}).items():
                presets[preset_name] = LLMConfig(**preset_dict)

            llm_presets = LLMPresets(default=llm_dict.get("default", "standard"), presets=presets)
        else:
            # Legacy format - convert to preset format
            # Create a single "standard" preset with the provided config
            llm_config = LLMConfig(**llm_dict)
            llm_presets = LLMPresets(default="standard", presets={"standard": llm_config})

        return cls(
            logging=logging_config,
            redis=redis_config,
            llm_presets=llm_presets,
        )


def load_config_file(config_file: Optional[pathlib.Path] = None) -> Dict[str, Any]:
    """Load configuration from file.

    Args:
        config_file: Path to configuration file. If None, uses the default.

    Returns:
        Dictionary containing configuration values.
    """
    if config_file is None:
        config_file = DEFAULT_CONFIG_FILE

    try:
        # Create config directory if it doesn't exist
        config_file.parent.mkdir(parents=True, exist_ok=True)

        # If config file doesn't exist, create it with default values
        if not config_file.exists():
            try:
                logger.info(f"Creating default config file at {config_file}")
                with open(config_file, "w") as f:
                    yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False)
            except (PermissionError, OSError) as e:
                logger.warning(f"Could not create config file at {config_file}: {e}")
                logger.info("Using default configuration instead")
                return DEFAULT_CONFIG

        # Load config from file
        try:
            with open(config_file, "r") as f:
                loaded_config = yaml.safe_load(f)
                if loaded_config is None:
                    logger.warning(f"Empty config file at {config_file}, using defaults")
                    return DEFAULT_CONFIG

                # Validate structure of loaded config
                merged_config = DEFAULT_CONFIG.copy()
                for section, values in loaded_config.items():
                    if section in merged_config and isinstance(values, dict):
                        merged_config[section].update(values)
                    else:
                        merged_config[section] = values

                return merged_config
        except (PermissionError, FileNotFoundError) as e:
            logger.warning(f"Could not read config file {config_file}: {e}")
            logger.info("Using default configuration instead")
            return DEFAULT_CONFIG
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in config file {config_file}: {e}")
            logger.info("Using default configuration instead")
            return DEFAULT_CONFIG
    except Exception as e:
        logger.error(f"Unexpected error loading config file: {e}")
        logger.info("Using default configuration instead")
        return DEFAULT_CONFIG


def add_config_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Add configuration-related arguments to an argument parser.

    Args:
        parser: Argument parser to add arguments to.

    Returns:
        Updated argument parser.
    """
    config_group = parser.add_argument_group("Configuration")
    config_group.add_argument(
        "--config",
        type=str,
        help=f"Path to configuration file (default: {DEFAULT_CONFIG_FILE})",
    )

    config_group = parser.add_argument_group("Logging")
    config_group.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level",
    )
    config_group.add_argument(
        "--log-file",
        type=str,
        help="Path to log file",
    )
    config_group.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    config_group = parser.add_argument_group("Redis")
    config_group.add_argument(
        "--redis-host",
        type=str,
        help="Redis host",
    )
    config_group.add_argument(
        "--redis-port",
        type=int,
        help="Redis port",
    )
    config_group.add_argument(
        "--redis-db",
        type=int,
        help="Redis database number",
    )
    config_group.add_argument(
        "--redis-password",
        type=str,
        help="Redis password",
    )
    config_group.add_argument("--redis-disable", action="store_false", help="Disable Redis caching")
    config_group.add_argument(
        "--redis-recache",
        action="store_true",
        help="Disable Redis caching retrieval, but allow saving",
    )

    config_group = parser.add_argument_group("LLM")
    config_group.add_argument(
        "--llm-preset",
        type=str,
        help="LLM preset name to use (e.g., 'standard', 'premium')",
    )
    config_group.add_argument(
        "--llm-tier",
        type=str,
        help="LLM tier to use (e.g., 'standard', 'premium')",
    )
    config_group.add_argument(
        "--llm-api-key",
        type=str,
        help="API key for LLM service",
    )
    config_group.add_argument(
        "--llm-base-url",
        type=str,
        help="Base URL for the LLM API endpoint",
    )
    config_group.add_argument(
        "--llm-model",
        type=str,
        help="LLM model to use",
    )
    config_group.add_argument(
        "--llm-max-tokens",
        type=int,
        help="Maximum tokens for LLM response",
    )
    config_group.add_argument(
        "--llm-temperature",
        type=float,
        help="Temperature for LLM sampling",
    )
    config_group.add_argument(
        "--llm-top-p",
        type=float,
        help="Top-p value for LLM sampling",
    )
    config_group.add_argument(
        "--llm-retry-attempts",
        type=int,
        help="Number of retry attempts for LLM API calls",
    )
    config_group.add_argument(
        "--llm-retry-delay",
        type=int,
        help="Delay between retry attempts for LLM API calls (seconds)",
    )

    return parser


def get_config(args: Optional[argparse.Namespace] = None) -> Tuple[Config, pathlib.Path]:
    """Get configuration from file and command line arguments.

    Args:
        args: Parsed command line arguments. If None, only uses the config file.

    Returns:
        Config object.
    """
    # Load config from file
    config_file = DEFAULT_CONFIG_FILE
    if args and hasattr(args, "config") and args.config:
        config_file = pathlib.Path(args.config)

    config_dict = load_config_file(config_file)

    # Override with command line arguments if provided
    if args:
        # Initialize config sections
        config_dict.setdefault("logging", {})
        config_dict.setdefault("redis", {})
        config_dict.setdefault("llm", {})

        # Map argument names to config sections and keys
        arg_mappings = {
            "log_level": ("logging", "level"),
            "log_file": ("logging", "file"),
            "redis_host": ("redis", "host"),
            "redis_port": ("redis", "port"),
            "redis_db": ("redis", "db"),
            "redis_password": ("redis", "password"),
            "redis_disable": ("redis", "enabled"),
            "redis_recache": ("redis", "recache"),
            "llm_preset": ("llm", "default"),
            "llm_api_key": ("llm", "_api_key_override"),
            "llm_base_url": ("llm", "_base_url_override"),
            "llm_model": ("llm", "_model_override"),
            "llm_max_tokens": ("llm", "_max_tokens_override"),
            "llm_temperature": ("llm", "_temperature_override"),
            "llm_top_p": ("llm", "_top_p_override"),
            "llm_retry_attempts": ("llm", "_retry_attempts_override"),
            "llm_retry_delay": ("llm", "_retry_delay_override"),
        }

        # Update config from arguments
        for arg_name, (section, key) in arg_mappings.items():
            value = getattr(args, arg_name, None)
            if value is not None:
                config_dict[section][key] = value

        # Handle LLM-specific overrides from command line
        # These will be applied to the selected preset after the Config object is created
        config_obj = Config.from_dict(config_dict)

        # Determine which preset to use
        preset_name = getattr(args, "llm_preset", None)
        tier = getattr(args, "llm_tier", None)

        try:
            # Get the specific LLM config to modify
            llm_config = config_obj.llm_presets.get_config(preset_name, tier)

            # Apply overrides
            for attr, override_key in [
                ("api_key", "_api_key_override"),
                ("base_url", "_base_url_override"),
                ("model", "_model_override"),
                ("max_tokens", "_max_tokens_override"),
                ("temperature", "_temperature_override"),
                ("top_p", "_top_p_override"),
                ("retry_attempts", "_retry_attempts_override"),
                ("retry_delay", "_retry_delay_override"),
            ]:
                override_value = config_dict["llm"].get(override_key)
                if override_value is not None:
                    setattr(llm_config, attr, override_value)

        except ValueError as e:
            logger.warning(f"Could not apply LLM overrides: {e}")

        return config_obj, config_file

    return Config.from_dict(config_dict), config_file
