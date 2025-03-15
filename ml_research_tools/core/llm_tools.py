"""Language Model (LLM) Utilities for ML Research Tools.

This module provides a set of utilities for interacting with Large Language Models:

1. **LLMClient Class**: Complete client for LLM interactions with:
   - Configuration management (presets, tiers)
   - Automatic retries with exponential backoff
   - Result caching
   - Simple and chat-based interfaces
2. **Factory Function**: Easy client creation through `create_llm_client`

Example:
    ::

        # Create client with default preset
        client = create_llm_client()
        response = client.simple_call(
            text="Summarize the following paper: [paper text]",
            system_prompt="You are a helpful academic assistant."
        )

        # Use a specific preset
        client = create_llm_client(preset="premium")
        response = client.simple_call(
            text="Explain this complex concept...",
            system_prompt="You are a helpful academic assistant."
        )

        # Chat interface
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"},
            {"role": "assistant", "content": "I'm doing well, thank you! How can I help you today?"},
            {"role": "user", "content": "Can you explain quantum computing?"}
        ]
        client = create_llm_client(tier="premium")
        response = client.call(messages=messages)

        # For raw OpenAI client access
        openai_client = create_llm_client().get_openai_client()

        # Generate parameters for OpenAI API calls
        params = generate_completion_params(
            config=config,
            messages=messages,
            stream=True
        )

"""

import os
import time
from typing import Any, Dict, List, Literal, Optional, Protocol, TypedDict, Union

import openai
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ml_research_tools.cache import RedisCache, cached, generate_cache_key
from ml_research_tools.core.config import Config, LLMConfig, LLMPresets
from ml_research_tools.core.logging_tools import get_logger

logger = get_logger(__name__)

# Type definitions for chat messages
MessageRole = Literal["system", "user", "assistant", "tool"]


class Message(TypedDict):
    """Type definition for a chat message."""

    role: MessageRole
    content: str


# Define the retry conditions and exceptions to retry on
RETRY_EXCEPTIONS = (
    openai.APIError,  # General API errors
    openai.APIConnectionError,  # Network errors
    openai.RateLimitError,  # Rate limiting
)


def get_llm_config(
    *,
    preset: Optional[str] = None,
    tier: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
    retry_attempts: Optional[int] = None,
    retry_delay: Optional[int] = None,
    config: Optional[Union[Config, LLMConfig, LLMPresets]] = None,
) -> LLMConfig:
    """
    Get an LLM configuration by resolving preset/tier and applying overrides.

    This factory function selects the appropriate LLM configuration based on:
    1. Preset name or tier
    2. Individual parameter overrides
    3. Default configuration if nothing else is specified

    Args:
        preset: Name of the preset configuration to use
        tier: Tier of model to use (e.g., "standard", "premium")
        api_key: API key override
        base_url: Base URL override
        model: Model name override
        temperature: Temperature override
        top_p: Top-p value override
        max_tokens: Max tokens override
        retry_attempts: Retry attempts override
        retry_delay: Retry delay override
        config: Configuration object (Config, LLMConfig, or LLMPresets)

    Returns:
        LLMConfig object with all parameters resolved

    Raises:
        ValueError: If no valid configuration can be determined
    """
    # Step 1: Get the base configuration
    llm_config = None

    # If a direct LLMConfig is provided, use it as is
    if isinstance(config, LLMConfig):
        llm_config = config

    # If LLMPresets are provided, use them to select a config
    elif isinstance(config, LLMPresets):
        llm_config = config.get_config(preset_name=preset, tier=tier)

    # If global Config is provided, use its llm_presets property
    elif isinstance(config, Config):
        llm_config = config.llm_presets.get_config(preset_name=preset, tier=tier)

    # No config provided, create a default one
    else:
        # This will use the defaults defined in the LLMConfig class
        llm_config = LLMConfig()

    # Step 2: Apply parameter overrides
    # Each parameter is only overridden if explicitly provided
    overrides = {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "retry_attempts": retry_attempts,
        "retry_delay": retry_delay,
    }

    # Only apply overrides for non-None values
    for param, value in overrides.items():
        if value is not None:
            setattr(llm_config, param, value)

    # Step 3: Ensure API key is available
    # Check environment variable if not explicitly provided
    if not llm_config.api_key:
        llm_config.api_key = os.environ.get("OPENAI_API_KEY")

    return llm_config


class LLMClient:
    """Client for interacting with Language Models with preset configurations and caching.

    This class provides a unified interface for making LLM API calls with:
    - Configuration management (presets, tiers, parameter overrides)
    - Automatic retries with exponential backoff
    - Result caching
    - Simple and chat-based interfaces

    Attributes:
        config: The LLM configuration to use for API calls
    """

    def __init__(
        self,
        *,
        preset: Optional[str] = None,
        tier: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        retry_attempts: Optional[int] = None,
        retry_delay: Optional[int] = None,
        config: Optional[Union[Config, LLMConfig, LLMPresets]] = None,
        redis_cache: Optional[RedisCache] = None,
    ):
        """Initialize an LLM client with the specified configuration.

        Args:
            preset: Name of the preset configuration to use
            tier: Tier of model to use (e.g., "standard", "premium")
            api_key: API key override
            base_url: Base URL override
            model: Model name override
            temperature: Temperature override
            top_p: Top-p value override
            max_tokens: Max tokens override
            retry_attempts: Retry attempts override
            retry_delay: Retry delay override
            config: Configuration object (Config, LLMConfig, or LLMPresets)
            redis_cache: Redis cache instance for caching results
        """
        self.config = get_llm_config(
            preset=preset,
            tier=tier,
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            retry_attempts=retry_attempts,
            retry_delay=retry_delay,
            config=config,
        )
        self.redis_cache = redis_cache

        # Validate the API key
        if not self.config.api_key:
            raise ValueError(
                "API key not provided. Set it with api_key parameter, in the preset config, "
                "or with the OPENAI_API_KEY environment variable."
            )

        # Create the OpenAI client
        self.client = openai.OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
        )

    @property
    def model(self):
        """Get the model name from the configuration."""
        return self.config.model

    def get_openai_client(self) -> openai.OpenAI:
        """Get the raw OpenAI client.

        Returns:
            The underlying OpenAI client instance
        """
        return self.client

    def _generate_simple_cache_key(self, text: str, system_prompt: str, prefix: str = "llm") -> str:
        """Generate a cache key for simple LLM requests.

        Args:
            text: The user text to process
            system_prompt: The system instructions
            prefix: A prefix for the cache key for namespace separation

        Returns:
            A stable cache key string
        """
        return generate_cache_key(
            kwargs=dict(
                text=text,
                system_prompt=system_prompt,
                model=self.config.model,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
            ),
            prefix=prefix,
        )

    def _generate_chat_cache_key(self, messages: List[Message], prefix: str = "llm_chat") -> str:
        """Generate a cache key for chat history LLM requests.

        Args:
            messages: List of chat messages
            prefix: A prefix for the cache key for namespace separation

        Returns:
            A stable cache key string
        """
        return generate_cache_key(
            kwargs=dict(
                messages=messages,
                model=self.config.model,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
            ),
            prefix=prefix,
        )

    def simple_call(
        self,
        text: str,
        system_prompt: str,
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        prefix: str = "llm",
        use_cache: bool = True,
    ) -> str:
        """Call an LLM with a simple system prompt + user text pattern.

        Args:
            text: The user text to process
            system_prompt: Instructions for the LLM (system message)
            model: Model name override
            temperature: Temperature override
            top_p: Top-p override
            max_tokens: Max tokens override
            prefix: Prefix for cache keys
            use_cache: Whether to use caching for this call

        Returns:
            The LLM response text
        """
        # Create the messages list for a simple conversation
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": text}]

        # Call the more general chat function
        return self.call(
            messages=messages,
            model=model,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            prefix=prefix,
            use_cache=use_cache,
        )

    def call(
        self,
        messages: List[Message],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        prefix: str = "llm_chat",
        use_cache: bool = True,
    ) -> str:
        """Call an LLM API with a complete chat history.

        Args:
            messages: List of chat messages
            model: Model name override
            temperature: Temperature override
            top_p: Top-p override
            max_tokens: Max tokens override
            prefix: Prefix for cache keys
            use_cache: Whether to use caching for this call

        Returns:
            The LLM response text
        """
        # Apply parameter overrides for this specific call
        call_config = LLMConfig(
            model=model if model is not None else self.config.model,
            temperature=temperature if temperature is not None else self.config.temperature,
            top_p=top_p if top_p is not None else self.config.top_p,
            max_tokens=max_tokens if max_tokens is not None else self.config.max_tokens,
            retry_attempts=self.config.retry_attempts,
            retry_delay=self.config.retry_delay,
            api_key=self.config.api_key,
            base_url=self.config.base_url,
        )

        # Check cache if enabled
        if use_cache and self.redis_cache:
            cache_key = self._generate_chat_cache_key(messages, prefix)
            cached_result = self.redis_cache.get(cache_key)
            if cached_result:
                logger.info(f"Retrieved result from cache for key: {cache_key}")
                return cached_result

        # Make the API call with retry logic
        result = self._call_with_retry(
            messages=messages,
            model=call_config.model,
            max_tokens=call_config.max_tokens,
            temperature=call_config.temperature,
            top_p=call_config.top_p,
            retry_attempts=call_config.retry_attempts,
            retry_delay=call_config.retry_delay,
        )

        # Store in cache if enabled
        if use_cache and self.redis_cache:
            cache_key = self._generate_chat_cache_key(messages, prefix)
            self.redis_cache.set(cache_key, result)
            logger.info(f"Stored result in cache for key: {cache_key}")

        return result

    def _before_retry_log(self, retry_state):
        """Log information before a retry attempt."""
        if retry_state.outcome is None:
            return

        exception = retry_state.outcome.exception()
        if exception:
            wait_time = retry_state.next_action.sleep
            attempt_number = retry_state.attempt_number
            logger.warning(
                f"Attempt {attempt_number} failed with error: {exception}. "
                f"Retrying in {wait_time:.2f} seconds..."
            )

    def _after_retry_log(self, retry_state):
        """Log information after a retry sequence completes."""
        if retry_state.outcome.failed:
            logger.error("All retry attempts failed.")
        else:
            logger.info(f"Succeeded after {retry_state.attempt_number} attempts")

    def _call_with_retry(
        self,
        messages: List[Message],
        model: str,
        max_tokens: int,
        temperature: float,
        top_p: float,
        retry_attempts: int,
        retry_delay: int,
    ) -> str:
        """Call LLM API with automatic retries for transient errors."""
        # Create a decorator that configures the retry behavior
        retry_decorator = retry(
            stop=stop_after_attempt(retry_attempts),
            wait=wait_exponential(multiplier=retry_delay, min=retry_delay, max=retry_delay * 10),
            retry=retry_if_exception_type(RETRY_EXCEPTIONS),
            before=self._before_retry_log,
            after=self._after_retry_log,
            reraise=True,
        )

        # Define the function that makes the actual API call
        @retry_decorator
        def _make_api_call_with_retry():
            """Make the API call with the configured retry behavior."""
            return self._make_chat_api_call(
                messages=messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
            )

        # Execute the API call with retries
        return _make_api_call_with_retry()

    def _make_chat_api_call(
        self, messages: List[Message], model: str, max_tokens: int, temperature: float, top_p: float
    ) -> str:
        """Make the actual chat API call and return the response."""
        # Time the API call
        time_start = time.perf_counter()

        # Make the API call
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
        )

        # Calculate elapsed time
        time_end = time.perf_counter()
        elapsed = time_end - time_start

        # Extract and log usage statistics
        usage = response.usage
        completion_speed = "N/A tokens/sec"
        tokens_desc = []

        completion_tokens, prompt_tokens, total_tokens = None, None, None
        if hasattr(usage, "completion_tokens"):
            completion_tokens = usage.completion_tokens
            if completion_tokens > 0 and elapsed > 0:
                if completion_tokens / elapsed > 1:
                    completion_speed = f"{completion_tokens / elapsed:.2f} tokens/sec"
                else:
                    completion_speed = f"{elapsed / completion_tokens:.2f} sec/token"
            tokens_desc.append(f"completion tokens: {completion_tokens}")
        if hasattr(usage, "prompt_tokens"):
            prompt_tokens = usage.prompt_tokens
            tokens_desc.append(f"prompt tokens: {prompt_tokens}")

        if hasattr(usage, "total_tokens"):
            total_tokens = usage.total_tokens
            tokens_desc.append(f"total tokens: {total_tokens}")

        logger.info(
            f"API call to {model} took {elapsed:.2f} seconds ({completion_speed} | {', '.join(tokens_desc)})"
        )

        # Extract and return the response content
        return response.choices[0].message.content


# Factory function to create LLMClient instances


def create_llm_client(
    *,
    preset: Optional[str] = None,
    tier: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
    retry_attempts: Optional[int] = None,
    retry_delay: Optional[int] = None,
    config: Optional[Union[Config, LLMConfig, LLMPresets]] = None,
    redis_cache: Optional[RedisCache] = None,
) -> LLMClient:
    """
    Create an LLMClient instance with the specified configuration.

    This is a factory function that creates an LLMClient with the appropriate configuration.

    Args:
        preset: Name of the preset configuration to use
        tier: Tier of model to use (e.g., "standard", "premium")
        api_key: API key override
        base_url: Base URL override
        model: Model name override
        temperature: Temperature override
        top_p: Top-p value override
        max_tokens: Max tokens override
        retry_attempts: Retry attempts override
        retry_delay: Retry delay override
        config: Configuration object (Config, LLMConfig, or LLMPresets)
        redis_cache: Redis cache instance

    Returns:
        An initialized LLMClient instance
    """
    return LLMClient(
        preset=preset,
        tier=tier,
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        retry_attempts=retry_attempts,
        retry_delay=retry_delay,
        config=config,
        redis_cache=redis_cache,
    )


def generate_completion_params(
    *,
    llm_client: LLMClient,
    **additional_params: Any,
) -> Dict[str, Any]:
    """
    Generate parameters for completion API calls based on configuration.

    This function resolves LLM configuration based on presets/tiers and
    returns a dictionary of parameters suitable for passing to the OpenAI
    completion API calls.

    Returns:
        Dictionary of parameters for OpenAI API calls
    """

    # Extract the config
    llm_config = llm_client.config

    # Create parameter dictionary with standard parameters
    params = {
        "model": llm_config.model,
        "temperature": llm_config.temperature,
        "top_p": llm_config.top_p,
        "max_tokens": llm_config.max_tokens,
    }

    # Add any additional parameters
    params.update(additional_params)

    return params
