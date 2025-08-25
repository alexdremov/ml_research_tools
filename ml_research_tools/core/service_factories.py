#!/usr/bin/env python3
"""
Service factory functions for common dependencies.

This module provides factory functions for creating common services
like Redis cache and LLM clients.
"""

import logging
from argparse import Namespace
from typing import Optional

from ml_research_tools.cache import RedisCache
from ml_research_tools.core.config import Config
from ml_research_tools.core.llm_tools import LLMClient, create_llm_client
from ml_research_tools.core.service_provider import ServiceProvider

logger = logging.getLogger(__name__)


def register_common_services(
    service_provider: ServiceProvider,
    default_llm_preset=None,
    default_llm_tier=None,
) -> None:
    """Register common services with the service provider.

    Args:
        service_provider: The service provider to register services with
    """
    config = service_provider.get_config()

    # Register Redis cache factory
    service_provider.register_factory("redis_cache", lambda: create_redis_cache(config))

    # Register LLM client factory with default preset
    service_provider.register_factory(
        "llm_client",
        lambda: create_llm_client(
            config=config,
            preset=default_llm_preset,
            tier=default_llm_tier,
            redis_cache=service_provider.get("redis_cache"),
        ),
    )

    # Register factories for each LLM preset
    for preset_name in config.llm_presets.presets:
        service_provider.register_factory(
            f"llm_client.{preset_name}",
            lambda name=preset_name: create_llm_client(
                config=config,
                preset=name,
                redis_cache=service_provider.get("redis_cache"),
            ),
        )

    # Register factories for each LLM tier
    tiers = set(preset.tier for preset in config.llm_presets.presets.values())
    for tier in tiers:
        service_provider.register_factory(
            f"llm_client_tier.{tier}",
            lambda t=tier: create_llm_client(
                config=config,
                tier=t,
                redis_cache=service_provider.get("redis_cache"),
            )
        )


def create_redis_cache(config: Config) -> Optional[RedisCache]:
    """Create a Redis cache instance from configuration.

    Args:
        config: Application configuration

    Returns:
        Redis cache instance or None if Redis is disabled
    """
    if not config.redis.enabled:
        logger.debug("Redis caching is disabled")
        return None

    logger.debug(f"Creating Redis cache with host {config.redis.host}")
    return RedisCache(config.redis)


def create_default_llm_client(
    config: Config, redis_cache: Optional[RedisCache] = None
) -> LLMClient:
    """Create a default LLM client from configuration.

    Args:
        config: Application configuration
        redis_cache: Optional Redis cache for caching results

    Returns:
        LLM client instance
    """
    return create_llm_client(config=config, redis_cache=redis_cache)


def setup_services(
    config: Config,
    default_llm_preset=None,
    default_llm_tier=None,
) -> ServiceProvider:
    """Set up a service provider with common services.

    Args:
        config: Application configuration

    Returns:
        Configured service provider
    """
    services = ServiceProvider(config)
    register_common_services(
        service_provider=services,
        default_llm_preset=default_llm_preset,
        default_llm_tier=default_llm_tier,
    )
    return services
