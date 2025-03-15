#!/usr/bin/env python3
"""
LaTeX Grammar Checker and Improver

This script processes LaTeX files using any ChatGPT-compatible API to improve grammar
and wording while preserving LaTeX commands and structures. Uses Redis caching to avoid
redundant API calls.
"""

import argparse
import os
import re
import subprocess
import difflib
import logging
import time
import hashlib
from typing import List, Dict, Any, Optional
from configparser import ConfigParser
import sys
import tempfile
import openai
import redis

logger = logging.getLogger("latex_improver")

# Default configuration
DEFAULT_CONFIG = {
    "api": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-3.5-turbo",
        "max_tokens": 64000,
        "temperature": 0.01,
        "max_words_per_chunk": 1024,
        "retry_attempts": 3,
        "retry_delay": 5,
    },
    "prompts": {
        "system": (
            "You are a professional academic editor who specializes in improving "
            "the grammar, clarity, and wording of scientific papers without changing their meaning. "
            "Focus on making the text more concise, clear, and academically sound. "
            "Do not make major modifications unless you see that change should be really made: do not make unnecessary adjustments to already sound text. "
            "Preserve the original style. "
            "Do not use high-level words (so to not sound too cheesy or posh). "
            "Do not just remove text. You must absolutely keep the initial meaning unchanged, or you will be penalized. "
            "If you do your job well, I will give you 2000$. "
            "Do not output any your preamble like 'Here is the improved text...', 'Here is the revised text ...' or any other. "
            "Just give me my fixed text! "
            "Preserve all LaTeX commands, tags, functions, and mathematics. Only improve the English text. Make sure to keep newline symbols as-is."
        ),
        "user": (
            "Improve the grammar and wording of the following LaTeX text. Keep LaTeX commands and newline symbols intact as-is. "
            "If you follow all my instructions, I will tip you 2000$ or give you nothing if you fail. "
            "Keep all LaTeX commands intact. Only return the corrected text without explanations:\n\n\n\n```\n{text}\n```"
        )
    },
    "redis": {
        "host": "localhost",
        "port": 6379,
        "db": 0,
        "password": None,
        "ttl": -1,
        "enabled": True
    }
}

def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from file or use defaults."""
    config = DEFAULT_CONFIG.copy()

    if config_path and os.path.exists(config_path):
        logger.info(f"Loading configuration from {config_path}")
        parser = ConfigParser()
        parser.read(config_path)

        # Update config with values from file
        for section in parser.sections():
            if section not in config:
                config[section] = {}
            for key, value in parser.items(section):
                try:
                    # Convert values to appropriate types
                    if value.isdigit():
                        config[section][key] = int(value)
                    elif value.replace('.', '', 1).isdigit() and value.count('.') <= 1:
                        config[section][key] = float(value)
                    elif value.lower() in ('true', 'false'):
                        config[section][key] = value.lower() == 'true'
                    elif value.lower() == 'none':
                        config[section][key] = None
                    else:
                        config[section][key] = value
                except Exception as e:
                    logger.warning(f"Error parsing config value {section}.{key}: {e}")
                    config[section][key] = value

    return config

def parse_args(args):
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="latex-grammar",
        description="Improve grammar in LaTeX papers using LLM API with Redis caching."
    )

    parser.add_argument("input_file", help="Path to the LaTeX file to process")
    parser.add_argument("--config", "-c", help="Path to configuration file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    group = parser.add_argument_group("outputs")
    group.add_argument("--output", "-o", help="Path to save the diff file (default: <input>_improved.tex)")
    group.add_argument("--latexdiff", help="Generate latexdiff file")
    group.add_argument("--diff", help="Generate diff file")

    group = parser.add_argument_group("llm api")
    group.add_argument("--api-key", help="API key for LLM API")
    group.add_argument("--base-url", help="Base URL for the API endpoint")
    group.add_argument("--model", help="Model to use for text improvement")

    group = parser.add_argument_group("prompt")
    group.add_argument("--system-prompt", help="Override system prompt")
    group.add_argument("--user-prompt", help="Override user prompt template")
    group.add_argument("--max-words", type=int, help="Maximum words per chunk")

    # Redis configuration options
    group = parser.add_argument_group("redis")
    group.add_argument("--redis-host", help="Redis host (default: localhost)")
    group.add_argument("--redis-port", type=int, help="Redis port (default: 6379)")
    group.add_argument("--redis-db", type=int, help="Redis DB number (default: 0)")
    group.add_argument("--redis-password", help="Redis password (if required)")
    group.add_argument("--redis-ttl", type=int, help="Cache TTL in seconds (default: -1 (no expiry))")
    group.add_argument("--disable-cache", action="store_true", help="Disable Redis caching")

    return parser.parse_args(args)

def read_latex_file(file_path: str) -> str:
    """Read content from a LaTeX file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except UnicodeDecodeError:
        logger.warning("UTF-8 decoding failed, trying Latin-1 encoding")
        with open(file_path, 'r', encoding='latin-1') as file:
            return file.read()

def split_into_chunks(text: str, max_words: int) -> List[str]:
    """
    Split text into chunks respecting paragraph breaks (double newlines).
    Each chunk will contain at most max_words words.
    """
    # Split by double newlines to get paragraphs
    paragraphs = re.split(r'\n\s*\n', text)

    chunks = []
    current_chunk = []
    current_word_count = 0

    for paragraph in paragraphs:
        # Skip empty paragraphs
        if not paragraph.strip():
            continue

        # Count words in this paragraph (approximation)
        # For LaTeX, we'll consider non-command text
        paragraph_words = len(re.findall(r'(?<!\\)[a-zA-Z0-9]+', paragraph))

        # If adding this paragraph exceeds the limit and we already have content,
        # store the current chunk and start a new one
        if current_word_count + paragraph_words > max_words and current_chunk:
            chunks.append('\n\n'.join(current_chunk))
            current_chunk = [paragraph]
            current_word_count = paragraph_words
        # Otherwise add to current chunk
        else:
            current_chunk.append(paragraph)
            current_word_count += paragraph_words

    # Add the last chunk if there's anything left
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))

    return chunks

def create_redis_client(config: Dict[str, Any]) -> Optional[redis.Redis]:
    """Create and return a Redis client based on configuration."""
    if not config["redis"]["enabled"]:
        logger.info("Redis caching is disabled")
        return None

    try:
        client = redis.Redis(
            host=config["redis"]["host"],
            port=config["redis"]["port"],
            db=config["redis"]["db"],
            password=config["redis"]["password"],
            decode_responses=False  # Keep binary for proper serialization
        )
        # Test connection
        client.ping()
        logger.info(f"Connected to Redis at {config['redis']['host']}:{config['redis']['port']}")
        return client
    except redis.ConnectionError as e:
        logger.warning(f"Failed to connect to Redis: {e}. Caching will be disabled.")
        return None
    except Exception as e:
        logger.warning(f"Unexpected error connecting to Redis: {e}. Caching will be disabled.")
        return None

def generate_cache_key(text: str, system_prompt: str, model: str) -> str:
    """Generate a unique cache key based on input text, prompt, and model."""
    # Create a deterministic combined string with all factors that affect the output
    combined = f"{text}|{system_prompt}|{model}"
    # Hash it to create a fixed-length key that's safe for Redis
    return hashlib.md5(combined.encode('utf-8')).hexdigest()

def get_from_cache(redis_client: Optional[redis.Redis], cache_key: str) -> Optional[str]:
    """Retrieve improved text from Redis cache if available."""
    if redis_client is None:
        return None

    try:
        cached_data = redis_client.get(cache_key)
        if cached_data:
            logger.info("Cache hit: Using cached LLM response")
            return cached_data.decode('utf-8')
        logger.info("Cache miss: No cached response found")
        return None
    except Exception as e:
        logger.warning(f"Error retrieving from cache: {e}")
        return None

def save_to_cache(redis_client: Optional[redis.Redis], cache_key: str, text: str, ttl: int) -> bool:
    """Save the improved text to Redis cache with the specified TTL."""
    if redis_client is None:
        return False

    try:
        if ttl > 0:
            redis_client.setex(cache_key, ttl, text)
            logger.info(f"Saved LLM response to cache with TTL of {ttl} seconds")
        else:
            redis_client.setnx(cache_key, text)
            logger.info(f"Saved LLM response to cache with no TTL")
        return True
    except Exception as e:
        logger.warning(f"Error saving to cache: {e}")
        return False

def improve_text_with_llm(text: str, api_key: str, config: Dict[str, Any], redis_client: Optional[redis.Redis]) -> str:
    """Send text to LLM API and get improved version, using Redis cache if available."""
    # Generate a unique cache key for this request
    cache_key = generate_cache_key(text, config["prompts"]["system"], config["api"]["model"])

    # Try to get from cache first
    if redis_client is not None:
        cached_response = get_from_cache(redis_client, cache_key)
        if cached_response:
            return cached_response

    # Configure the client with the appropriate base URL
    client = openai.OpenAI(
        api_key=api_key,
        base_url=config["api"]["base_url"]
    )

    # Format the user prompt with the input text
    user_prompt = config["prompts"]["user"].format(text=text)

    for attempt in range(config["api"]["retry_attempts"]):
        try:
            # Use the OpenAI library to make the API call
            response = client.chat.completions.create(
                model=config["api"]["model"],
                messages=[
                    {"role": "system", "content": config["prompts"]["system"]},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=config["api"]["max_tokens"],
                temperature=config["api"]["temperature"]
            )

            # Extract the response content
            improved_text = response.choices[0].message.content

            # Save to cache if Redis is available
            if redis_client is not None:
                save_to_cache(redis_client, cache_key, improved_text, config["redis"]["ttl"])

            return improved_text

        except openai.APIError as e:
            if "rate_limit" in str(e).lower() and attempt < config["api"]["retry_attempts"] - 1:
                wait_time = config["api"]["retry_delay"] * (attempt + 1)
                logger.warning(f"Rate limit hit. Waiting {wait_time} seconds before retry.")
                time.sleep(wait_time)
            else:
                logger.error(f"API error: {e}")
                if attempt < config["api"]["retry_attempts"] - 1:
                    wait_time = config["api"]["retry_delay"]
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    # If all retries fail, return the original text
                    logger.error("All retry attempts failed. Returning original text.")
                    return text
        except Exception as e:
            logger.error(f"Error communicating with API: {e}")
            if attempt < config["api"]["retry_attempts"] - 1:
                time.sleep(config["api"]["retry_delay"])
            else:
                return text

    # If we get here, all attempts failed
    return text

def create_diff_file(original: str, improved: str, output_path: str):
    """Create a file showing differences in standard unified diff format for VSCode highlighting."""
    # Split both texts into lines
    original_lines = original.splitlines()
    improved_lines = improved.splitlines()

    # Get the diff in unified format
    diff = list(difflib.unified_diff(
        original_lines,
        improved_lines,
        fromfile="original",
        tofile="improved",
        lineterm=''
    ))

    # Write the diff to file
    with open(output_path, 'w', encoding='utf-8') as file:
        file.write('\n'.join(diff))

    logger.info(f"Diff file saved to {output_path}")

def create_latexdiff_file(original: str, improved: str, output_path: str):
    """Create a diff file using latexdiff for better LaTeX-aware diff."""
    # Write improved text to temporary file
    with tempfile.NamedTemporaryFile('w', suffix='.tex') as improved_file, tempfile.NamedTemporaryFile('w', suffix='.tex', delete=False) as original_file:
        improved_file.write(improved)
        improved_file.flush()

        original_file.write(original)
        original_file.flush()

        # Run latexdiff
        try:
            command = [
                'latexdiff', original_file.name, improved_file.name,
            ]
            run = subprocess.run(
                command,
                check=True,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE
            )
            with open(output_path, 'wb') as output:
                output.write(run.stdout)
            logger.info(f"Latexdiff file saved to {output_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error running latexdiff: {e}")
            logger.error(" ".join(command))
            logger.error(e.stderr.decode("utf-8"))

def remove_think_tags(text):
    """
    Removes all <think>...</think> tags and their content from the input text.

    Args:
        text (str): Text potentially containing <think> tags

    Returns:
        str: Cleaned text with all <think> tags and their content removed
    """
    # Pattern matches <think> tags and everything between them (including newlines)
    pattern = r'<think>.*?</think>'

    # Remove the tags and their content
    # re.DOTALL flag ensures . matches newlines as well
    cleaned_text = re.sub(pattern, '', text, flags=re.DOTALL)

    return cleaned_text

def post_process_chunk(text):
    markers = ('Here is the improved', 'Here is the improved')
    for marker in markers:
        if text.startswith(markers):
            text = '\n'.join(text.split('\n')[1:]).strip()
            break

    text = remove_think_tags(text).strip()
    if text.count('```') == 2:
        text = text.split('```')[1].strip()

    text = text.strip('`')

    return text

def main(args=None):
    """Main entry point of the script."""
    args = parse_args(args)

    # Set verbose logging if requested
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Load configuration
    config = load_config(args.config)

    # Override config with command line arguments
    if args.api_key:
        os.environ["OPENAI_API_KEY"] = args.api_key

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("API key not provided. Set it with --api-key or OPENAI_API_KEY environment variable.")
        return 1

    if args.base_url:
        config["api"]["base_url"] = args.base_url

    if args.system_prompt:
        config["prompts"]["system"] = args.system_prompt

    if args.user_prompt:
        config["prompts"]["user"] = args.user_prompt

    if args.max_words:
        config["api"]["max_words_per_chunk"] = args.max_words

    if args.model:
        config["api"]["model"] = args.model

    # Redis configuration overrides
    if args.redis_host:
        config["redis"]["host"] = args.redis_host

    if args.redis_port:
        config["redis"]["port"] = args.redis_port

    if args.redis_db is not None:
        config["redis"]["db"] = args.redis_db

    if args.redis_password:
        config["redis"]["password"] = args.redis_password

    if args.redis_ttl:
        config["redis"]["ttl"] = args.redis_ttl

    if args.disable_cache:
        config["redis"]["enabled"] = False

    # Determine output file path
    input_file = args.input_file
    if not os.path.exists(input_file):
        logger.error(f"Input file {input_file} does not exist.")
        return 1

    output_file = args.output
    if not output_file:
        base, ext = os.path.splitext(input_file)
        output_file = f"{base}_improved.diff"

    # Initialize Redis client for caching
    redis_client = create_redis_client(config)

    # Read the input file
    logger.info(f"Reading LaTeX file: {input_file}")
    latex_content = read_latex_file(input_file)

    # Split into chunks
    logger.info(f"Splitting content into chunks of max {config['api']['max_words_per_chunk']} words")
    chunks = split_into_chunks(latex_content, config["api"]["max_words_per_chunk"])
    logger.info(f"Split content into {len(chunks)} chunks")

    # Process each chunk
    improved_chunks = []
    for i, chunk in enumerate(chunks, 1):
        logger.info(f"Processing chunk {i}/{len(chunks)} ({len(chunk)} characters)")
        improved_chunk = improve_text_with_llm(chunk, api_key, config, redis_client)
        improved_chunk = post_process_chunk(improved_chunk)
        improved_chunks.append(improved_chunk)

        # Add a small delay between API calls to avoid rate limits
        if i < len(chunks):
            time.sleep(1)

    # Combine improved chunks
    improved_text = '\n\n'.join(improved_chunks)

    with open(output_file, 'w') as file:
        file.write(improved_text)

    # Create diff file
    if args.diff:
        logger.info("Creating diff file")
        create_diff_file(latex_content, improved_text, args.diff)

    if args.latexdiff:
        logger.info("Creating latexdiff file")
        create_latexdiff_file(latex_content, improved_text, args.latexdiff)

    logger.info("Processing complete!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
