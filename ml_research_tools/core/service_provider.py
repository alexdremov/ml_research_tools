#!/usr/bin/env python3
"""
Service provider implementation for dependency injection.

This module provides a centralized service provider that manages
dependencies and services used throughout the application.
"""

import logging
from typing import Any, Callable, Dict, Optional, Type, TypeVar

from ml_research_tools.core.config import Config

T = TypeVar("T")
logger = logging.getLogger(__name__)


class ServiceProvider:
    """
    A service provider that manages dependencies and services.

    This class implements the service locator pattern, allowing services
    to be registered and retrieved. It supports lazy initialization of
    services and singleton instances.
    """

    def __init__(self, config: Config):
        """
        Initialize the service provider with a configuration.

        Args:
            config: The application configuration
        """
        self._config = config
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable[[], Any]] = {}

    def register(self, name: str, instance: Any) -> None:
        """
        Register a service instance with the provider.

        Args:
            name: The name to register the service under
            instance: The service instance
        """
        self._services[name] = instance
        logger.debug(f"Registered service: {name}")

    def register_factory(self, name: str, factory: Callable[[], Any]) -> None:
        """
        Register a factory function for lazy initialization of a service.

        Args:
            name: The name to register the service under
            factory: A callable that creates the service when needed
        """
        self._factories[name] = factory
        logger.debug(f"Registered factory: {name}")

    def get(self, name: str) -> Any:
        """
        Get a service by name.

        Args:
            name: The name of the service to retrieve

        Returns:
            The service instance

        Raises:
            KeyError: If the service is not registered
        """
        # Return existing instance if it exists
        if name in self._services:
            return self._services[name]

        # Use factory to create instance if available
        if name in self._factories:
            logger.debug(f"Lazy-loading service: {name}")
            instance = self._factories[name]()
            self._services[name] = instance
            return instance

        raise KeyError(f"Service not registered: {name}")

    def has(self, name: str) -> bool:
        """
        Check if a service is registered.

        Args:
            name: The name of the service to check

        Returns:
            True if the service is registered, False otherwise
        """
        return name in self._services or name in self._factories

    def get_config(self) -> Config:
        """
        Get the configuration object.

        Returns:
            The configuration object
        """
        return self._config

    def get_or_create(self, name: str, factory: Callable[[], T]) -> T:
        """
        Get a service by name, or create it if it doesn't exist.

        Args:
            name: The name of the service to retrieve
            factory: A callable that creates the service if needed

        Returns:
            The service instance
        """
        if not self.has(name):
            instance = factory()
            self.register(name, instance)
        return self.get(name)

    # Type-safe getter with casting
    def get_typed(self, name: str, expected_type: Type[T]) -> T:
        """
        Get a service by name with type checking.

        Args:
            name: The name of the service to retrieve
            expected_type: The expected type of the service

        Returns:
            The service instance

        Raises:
            TypeError: If the service is not of the expected type
        """
        service = self.get(name)
        if not isinstance(service, expected_type):
            raise TypeError(f"Service {name} is of type {type(service)}, expected {expected_type}")
        return service
