Cache API
=========

The Cache API provides utilities for caching function calls and results, helping to improve performance
and reduce redundant operations especially for expensive computations or API calls.

Redis Cache
-----------

.. py:class:: ml_research_tools.cache.redis.RedisCache

   A caching implementation using Redis as the backend storage.

   .. py:method:: __init__(redis_client, ttl=604800, enabled=True)

      Initialize the Redis cache.

      :param redis_client: A Redis client instance
      :type redis_client: redis.Redis
      :param ttl: Time-to-live for cache entries in seconds (default: 7 days)
      :type ttl: int
      :param enabled: Whether caching is enabled
      :type enabled: bool

   .. py:method:: get(key)

      Get a value from the cache.

      :param key: Cache key
      :type key: str
      :return: The cached value or None if not found
      :rtype: Any

   .. py:method:: set(key, value)

      Store a value in the cache.

      :param key: Cache key
      :type key: str
      :param value: Value to cache
      :type value: Any
      :return: Success status
      :rtype: bool

   .. py:method:: delete(key)

      Remove a value from the cache.

      :param key: Cache key
      :type key: str
      :return: Success status
      :rtype: bool

   .. py:method:: clear()

      Clear all entries from the cache.

      :return: Success status
      :rtype: bool

Decorator
---------

.. py:function:: ml_research_tools.cache.cached(prefix=None, key_func=None)

   Decorator for caching function results in Redis.

   :param prefix: Prefix for cache keys
   :type prefix: str, optional
   :param key_func: Custom function to generate cache keys
   :type key_func: callable, optional
   :return: Decorated function
   :rtype: callable

Example
-------

Here's an example of how to use the caching system:

.. code-block:: python

   from ml_research_tools.cache import cached, RedisCache
   import redis

   # Setup Redis cache
   redis_client = redis.Redis(host='localhost', port=6379, db=0)
   cache = RedisCache(redis_client)

   # Apply caching decorator to an expensive function
   @cached(prefix="expensive_calculation")
   def expensive_function(x, cache=None):
       # The cache parameter is injected by the decorator
       # Expensive computation here
       return x * x

   # First call computes the result
   result1 = expensive_function(5, cache=cache)  # Computes 25

   # Second call returns cached result without recomputation
   result2 = expensive_function(5, cache=cache)  # Returns cached 25 