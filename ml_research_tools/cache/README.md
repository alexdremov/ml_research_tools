# Redis Cache Utilities for ML Research Tools

This module provides simple, easy-to-use Redis caching utilities for the ML Research Tools package. It includes a high-level `RedisCache` class and decorators to simplify caching expensive computations.

## Features

- Simple key-value caching interface
- Automatic serialization/deserialization of Python objects
- Support for time-to-live (TTL) expiration
- Function result caching via decorators
- Graceful fallback when Redis is unavailable

## Usage

### Basic Key-Value Caching

```python
from ml_research_tools.config import get_config
from ml_research_tools.cache import RedisCache

# Get configuration and initialize cache
config = get_config()
cache = RedisCache(config.redis)

# Store a value
cache.set("my_key", "Hello, Redis!")

# Retrieve the value
value = cache.get("my_key")
print(value)  # Output: Hello, Redis!

# Store a complex object
data = {
    "name": "ML Research Tools",
    "features": ["caching", "latex", "wandb"],
    "metrics": {"awesomeness": 9.9}
}
cache.set("complex_key", data)

# Retrieve the complex object
retrieved = cache.get("complex_key")
print(retrieved["metrics"]["awesomeness"])  # Output: 9.9
```

### Caching Function Results with Decorators

```python
from ml_research_tools.cache.redis import cached

# Cache result for 1 hour (3600 seconds)
@cached(prefix="my_module", ttl=3600)
def expensive_calculation(a, b, c):
    # ... perform expensive calculation
    return result
    
# The function results will be cached based on the arguments
result1 = expensive_calculation(1, 2, 3)  # Calculated and cached
result2 = expensive_calculation(1, 2, 3)  # Retrieved from cache
result3 = expensive_calculation(4, 5, 6)  # Different args, calculated and cached
```

### Cache Management

```python
# Check if a key exists
if cache.exists("my_key"):
    print("Key exists!")
    
# Delete a key
cache.delete("my_key")

# Clear all keys with a specific pattern
cache.clear("my_prefix:*")
```

## Configuration

Redis caching can be configured through the standard ML Research Tools configuration system:

```yaml
# ~/.config/ml_research_tools/config.yaml
redis:
  enabled: true
  host: localhost
  port: 6379
  db: 0
  password: null
  ttl: 604800  # 7 days in seconds
  recache: false  # Set to true to ignore cached values but still cache results
```

Configuration can also be provided via command-line arguments when using the CLI tools.

## Example Script

For a complete working example, see the [example.py](example.py) script included in this package.

To run the example:

```bash
python -m ml_research_tools.cache.example
``` 