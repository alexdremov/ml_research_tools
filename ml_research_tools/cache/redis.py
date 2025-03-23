"""Redis caching utilities for ML Research Tools.

This module provides utilities for Redis caching, including a Redis cache manager
class and functions for common caching operations.
"""

import hashlib
import itertools
import json
import pickle
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, cast

import redis

from ml_research_tools.core.config import RedisConfig
from ml_research_tools.core.logging_tools import get_logger

logger = get_logger(__name__)

T = TypeVar("T")
R = TypeVar("R")


def create_redis_client(config: RedisConfig) -> Optional[redis.Redis]:
    """Create and return a Redis client based on configuration.

    Args:
        config: Redis configuration from the Config object

    Returns:
        Redis client instance or None if disabled or connection failed
    """
    if not config.enabled:
        logger.info("Redis caching is disabled")
        return None

    try:
        client = redis.Redis(
            host=config.host,
            port=config.port,
            db=config.db,
            password=config.password,
            decode_responses=False,  # Keep binary for proper serialization
        )
        # Test connection
        client.ping()
        logger.info(f"Connected to Redis at {config.host}:{config.port} (db: {config.db})")
        return client
    except redis.ConnectionError as e:
        logger.warning(f"Failed to connect to Redis: {e}. Caching will be disabled.")
        return None
    except Exception as e:
        logger.warning(f"Unexpected error connecting to Redis: {e}. Caching will be disabled.")
        return None


def generate_cache_key(
    args: Any = None, kwargs: dict[str, Any] | None = None, prefix: str = ""
) -> str:
    """Generate a unique cache key based on input parameters.

    Args:
        *args: Arguments to include in the key generation
        prefix: Optional prefix for the key (e.g., function name)

    Returns:
        A string key suitable for Redis
    """
    args = args or []
    kwargs = kwargs or {}

    # Convert arguments to a consistent string representation
    key_parts = []
    for key, arg in itertools.chain(enumerate(args), kwargs.items()):
        if isinstance(arg, (str, int, float, bool, type(None))):
            key_parts.append(f"{key}:{arg}")
        else:
            try:
                # Try to convert to JSON for consistent string representation
                arg = json.dumps(arg, sort_keys=True)
            except (TypeError, ValueError):
                arg = repr(arg)
                logger.debug(f"Non-serializable argument {key}: {arg}. Using repr() instead.")
            key_parts.append(f"{key}:{arg}")

    # Create a combined string with prefix
    combined = f"{prefix}|{'|'.join(key_parts)}"

    # Hash it to create a fixed-length key that's safe for Redis
    return hashlib.md5(combined.encode("utf-8")).hexdigest()


def get_from_cache(redis_client: Optional[redis.Redis], cache_key: str) -> Optional[bytes]:
    """Retrieve data from Redis cache if available.

    Args:
        redis_client: Redis client instance or None
        cache_key: Unique cache key for the data

    Returns:
        Cached data as bytes or None if not found
    """
    if redis_client is None:
        return None

    try:
        cached_data = redis_client.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for key: {cache_key}")
            return cached_data
        logger.debug(f"Cache miss for key: {cache_key}")
        return None
    except Exception as e:
        logger.warning(f"Error retrieving from cache: {e}")
        return None


def save_to_cache(
    redis_client: Optional[redis.Redis], cache_key: str, data: bytes, ttl: int
) -> bool:
    """Save data to Redis cache with the specified TTL.

    Args:
        redis_client: Redis client instance or None
        cache_key: Unique cache key for the data
        data: Data to cache (as bytes)
        ttl: Time-to-live in seconds (0 for no expiration)

    Returns:
        True if successfully cached, False otherwise
    """
    if redis_client is None:
        return False

    try:
        if ttl > 0:
            redis_client.setex(cache_key, ttl, data)
            logger.debug(f"Saved data to cache key {cache_key} with TTL of {ttl} seconds")
        else:
            redis_client.set(cache_key, data)
            logger.debug(f"Saved data to cache key {cache_key} with no TTL")
        return True
    except Exception as e:
        logger.warning(f"Error saving to cache: {e}")
        return False


class RedisCache:
    """Redis cache manager for ML Research Tools.

    This class provides a simple interface for Redis caching operations,
    including serialization and deserialization of complex Python objects.

    Example:
        ```python
        from ml_research_tools.config import get_config
        from ml_research_tools.cache import RedisCache

        config = get_config()
        cache = RedisCache(config.redis)

        # Cache a Python object
        data = {"results": [1, 2, 3]}
        cache.set("my_key", data)

        # Get it back
        retrieved = cache.get("my_key")
        ```
    """

    def __init__(self, config: RedisConfig):
        """Initialize Redis cache manager.

        Args:
            config: Redis configuration from Config object
        """
        self.config = config
        self.client = create_redis_client(config)
        self._enabled = config.enabled and self.client is not None
        self._recache = config.recache
        self.ttl = config.ttl

    @property
    def enabled(self) -> bool:
        """Return whether caching is enabled."""
        return self._enabled

    @property
    def recache(self) -> bool:
        """Return whether recaching is enabled (don't use cached values)."""
        return self._recache

    def get(self, key: str, default: Optional[T] = None) -> Optional[T]:
        """Get value from cache by key.

        Args:
            key: Cache key
            default: Default value to return if key not found

        Returns:
            Cached value or default
        """
        if not self.enabled or self.recache:
            return default

        cached = get_from_cache(self.client, key)
        if cached is None:
            return default

        try:
            return pickle.loads(cached)  # type: ignore
        except (pickle.PickleError, EOFError) as e:
            logger.warning(f"Failed to deserialize cached value: {e}")
            return default

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL.

        Args:
            key: Cache key
            value: Value to cache (can be any pickle-serializable object)
            ttl: Time-to-live in seconds (None uses config default)

        Returns:
            True if successfully cached, False otherwise
        """
        if not self.enabled:
            return False

        ttl_value = ttl if ttl is not None else self.ttl

        try:
            serialized = pickle.dumps(value)
            return save_to_cache(self.client, key, serialized, ttl_value)
        except (pickle.PickleError, TypeError) as e:
            logger.warning(f"Failed to serialize value for caching: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from cache.

        Args:
            key: Cache key to delete

        Returns:
            True if key was deleted, False otherwise
        """
        if not self.enabled:
            return False

        try:
            return bool(self.client.delete(key))  # type: ignore
        except Exception as e:
            logger.warning(f"Error deleting key from cache: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key to check

        Returns:
            True if key exists, False otherwise
        """
        if not self.enabled:
            return False

        try:
            return bool(self.client.exists(key))  # type: ignore
        except Exception as e:
            logger.warning(f"Error checking key existence in cache: {e}")
            return False

    def clear(self, pattern: str = "*") -> bool:
        """Clear cache keys matching pattern.

        Args:
            pattern: Redis key pattern to match (default: all keys)

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            pipeline = self.client.pipeline()  # type: ignore

            # Get keys matching pattern
            keys = self.client.keys(pattern)  # type: ignore

            if keys:
                # Use pipeline to delete all keys at once
                pipeline.delete(*keys)
                pipeline.execute()
                logger.info(f"Cleared {len(keys)} keys from cache")
            else:
                logger.info(f"No keys found matching pattern: {pattern}")

            return True
        except Exception as e:
            logger.warning(f"Error clearing cache: {e}")
            return False


def cached(
    prefix: str = "",
    ttl: Optional[int] = None,
    key_fn: Optional[Callable[..., str]] = None,
) -> Callable[[Callable[..., R]], Callable[..., R]]:
    """Decorator to cache function results in Redis.

    Args:
        prefix: Prefix for cache keys
        ttl: Time-to-live in seconds (None uses config default)
        key_fn: Custom function to generate cache key (if None, uses generate_cache_key)

    Returns:
        Decorator function

    Example:
        ```python
        from ml_research_tools.cache.redis import cached
        from ml_research_tools.config import get_config

        config = get_config()

        @cached(prefix="expensive_computation", ttl=3600)
        def expensive_computation(a, b, c):
            # ... some expensive calculation
            return result
        ```
    """

    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> R:
            cache_instance = None
            for arg in itertools.chain(args, kwargs.values()):
                if isinstance(arg, RedisCache):
                    cache_instance = arg
                    break
            else:
                assert False, "RedisCache instance not found in arguments"

            if not cache_instance.enabled:
                return func(*args, **kwargs)

            key_args = [arg for arg in args if not isinstance(arg, RedisCache)]
            key_kwargs = {k: v for k, v in kwargs.items() if not isinstance(v, RedisCache)}
            # Generate key
            if key_fn:
                key = key_fn(*key_args, **key_kwargs)
                assert prefix == "", "Prefix should be empty when using key_fn"
            else:
                func_prefix = f"{func.__module__}.{func.__name__}"
                if prefix:
                    func_prefix = f"{prefix}:{func_prefix}"
                key = generate_cache_key(key_args, key_kwargs, prefix=func_prefix)

            # Check cache
            cached_result = cache_instance.get(key)
            if cached_result is not None:
                return cast(R, cached_result)

            # Call the function
            result = func(*args, **kwargs)

            # Cache the result
            cache_instance.set(key, result, ttl)

            return result

        return wrapper

    return decorator
