#!/usr/bin/env python3
"""
LaTeX Grammar Checker and Improver Tool

This tool processes LaTeX files using any ChatGPT-compatible API to improve grammar
and wording while preserving LaTeX commands and structures.
"""

import argparse
import difflib
import logging
import os
import re
import subprocess
import tempfile
import textwrap
from configparser import ConfigParser
from typing import Any, Dict, List, Optional

from ml_research_tools.cache import RedisCache
from ml_research_tools.core.base_tool import BaseTool
from ml_research_tools.core.config import Config
from ml_research_tools.core.llm_tools import LLMClient, create_llm_client

DEFAULT_CONFIG = {
    "api": {
        "max_words_per_chunk": 1024,
    },
    "prompts": {
        "system": textwrap.dedent(
            """\
            You are a professional academic editor specializing in scientific papers. Your task is to:

            1. IMPROVE: Enhance english grammar, clarity, and wording while preserving the original meaning
            2. MAINTAIN: Keep the original style, tone, and technical accuracy
            3. PRIORITIZE: Focus on clarity and conciseness without changing sound text unnecessarily
            4. PRESERVE EXACTLY: Keep all LaTeX commands, tags, functions, mathematics, and newline symbols even if they are syntactically incorrect

            DO NOT:
            - DO NOT add explanatory text or preambles before your response
            - DO NOT use unnecessarily complex vocabulary
            - DO NOT remove content or alter the meaning
            - DO NOT change or add any LaTeX elements

            FORMAT: Respond only with the improved text, maintaining all original formatting and structure.

            """
        ),
        "user": textwrap.dedent(
            """\
            Edit the following scientific text to improve grammar and clarity while preserving meaning.

            IMPORTANT:
            - All LaTeX commands, syntax, and mathematics must remain exactly as written
            - Do not add any new LaTeX commands at all costs, even if syntax or structure are incorrect
            - All newline characters must be preserved in their original positions
            - Return only the edited text without any explanations or comments

            Text to edit:

            ```
            {text}
            ```
            """
        ),
    },
}


class LatexGrammarTool(BaseTool):
    """Tool for checking and improving grammar in LaTeX documents."""

    name = "latex-grammar"
    description = "Check and improve LaTeX grammar and style with LLM"

    def __init__(self, services) -> None:
        """Initialize the LaTeX grammar tool."""
        super().__init__(services)
        self.logger = logging.getLogger(__name__)
        self.tool_config: Dict[str, Any] = {}

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add tool-specific arguments to the parser."""
        parser.add_argument("input_file", help="Path to the LaTeX file to process")
        parser.add_argument("--config", "-c", help="Path to configuration file")

        group = parser.add_argument_group("outputs")
        group.add_argument(
            "--output",
            "-o",
            help="Path to save the diff file (default: <input>_improved.tex)",
        )
        group.add_argument("--latexdiff", help="Generate latexdiff file")
        group.add_argument("--diff", help="Generate diff file")

        group = parser.add_argument_group("prompt")
        group.add_argument("--system-prompt", help="Override system prompt")
        group.add_argument("--user-prompt", help="Override user prompt template")
        group.add_argument("--max-words", type=int, help="Maximum words per chunk")

        # Note: The global parser already adds --llm-preset and --llm-tier options
        # These values will be used automatically by the LLM functions

    def execute(self, config: Config, args: argparse.Namespace) -> int:
        """
        Execute the grammar improvement with the provided arguments.

        Args:
            config: Global configuration
            args: Parsed command-line arguments

        Returns:
            Exit code (0 for success, non-zero for error)
        """
        # Load tool-specific configuration
        self.tool_config = self.load_config(args.config)

        # Override config with command line arguments
        if args.system_prompt:
            self.tool_config["prompts"]["system"] = args.system_prompt

        if args.user_prompt:
            self.tool_config["prompts"]["user"] = args.user_prompt

        if args.max_words:
            self.tool_config["api"]["max_words_per_chunk"] = args.max_words

        # Get Redis cache from service provider
        redis_cache = self.services.get_typed("redis_cache", RedisCache)

        # Determine output file path
        input_file = args.input_file
        if not os.path.exists(input_file):
            self.logger.error(f"Input file {input_file} does not exist.")
            return 1

        output_file = args.output
        if not output_file:
            base, ext = os.path.splitext(input_file)
            output_file = f"{base}_improved{ext}"

        # Read the input file
        self.logger.info(f"Reading LaTeX file: {input_file}")
        latex_content = self.read_latex_file(input_file)

        # Split into chunks
        self.logger.info(
            f"Splitting content into chunks of max {self.tool_config['api']['max_words_per_chunk']} words"
        )
        chunks = self.split_into_chunks(
            latex_content, self.tool_config["api"]["max_words_per_chunk"]
        )
        self.logger.info(f"Split content into {len(chunks)} chunks")

        # Log which LLM is being used
        llm_client = self.services.get_typed("llm_client", LLMClient)
        llm_info = llm_client.config.model

        self.logger.info(f"Processing with LLM {llm_info}")

        # Process each chunk with rich progress indicator
        improved_chunks = []

        # Create a progress bar using rich
        with self.create_progress(console=self.console) as progress:
            task_id = progress.add_task("[cyan]Processing LaTeX chunks...", total=len(chunks))

            for i, chunk in enumerate(chunks, 1):
                chunk_desc = f"Chunk {i}/{len(chunks)} ({len(chunk)} characters)"
                progress.update(task_id, description=f"[cyan]Processing {chunk_desc}")

                # Use the LLM client to process the chunk
                improved_chunk = llm_client.simple_call(
                    text=self.tool_config["prompts"]["user"].format(text=chunk),
                    system_prompt=self.tool_config["prompts"]["system"],
                    prefix="latex_grammar",
                )

                improved_chunk = self.post_process_chunk(improved_chunk)
                improved_chunks.append(improved_chunk)
                progress.update(task_id, advance=1)

        # Combine improved chunks
        improved_text = "\n\n".join(improved_chunks)

        # Save improved text
        with open(output_file, "w") as file:
            file.write(improved_text)

        self.logger.info(f"Improved text saved to {output_file}")

        # Show summary of changes
        summary = (
            f"Processing summary:\n"
            f"- Input file: {input_file}\n"
            f"- Output file: {output_file}\n"
            f"- Processed: {len(chunks)} chunks\n"
            f"- Characters: {len(latex_content):,} → {len(improved_text):,}"
        )
        self.logger.info(summary)

        # Create diff file
        if args.diff:
            self.logger.info("Creating diff file")
            self.create_diff_file(latex_content, improved_text, args.diff)
            self.logger.info(f"Diff file saved to {args.diff}")

        if args.latexdiff:
            self.logger.info("Creating latexdiff file")
            success = self.create_latexdiff_file(latex_content, improved_text, args.latexdiff)
            if success:
                self.logger.info(f"LaTeXDiff file saved to {args.latexdiff}")

        return 0

    def load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """Load configuration from file or use defaults."""
        config = DEFAULT_CONFIG.copy()

        if config_path and os.path.exists(config_path):
            self.logger.info(f"Loading configuration from {config_path}")
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
                        elif value.replace(".", "", 1).isdigit() and value.count(".") <= 1:
                            config[section][key] = float(value)
                        elif value.lower() in ("true", "false"):
                            config[section][key] = value.lower() == "true"
                        elif value.lower() == "none":
                            config[section][key] = None
                        else:
                            config[section][key] = value
                    except Exception as e:
                        self.logger.warning(f"Error parsing config value {section}.{key}: {e}")
                        config[section][key] = value

        return config

    def read_latex_file(self, file_path: str) -> str:
        """Read content from a LaTeX file."""
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                return file.read()
        except UnicodeDecodeError:
            self.logger.warning("UTF-8 decoding failed, trying Latin-1 encoding")
            with open(file_path, "r", encoding="latin-1") as file:
                return file.read()

    @staticmethod
    def split_into_chunks(text: str, max_words: int) -> List[str]:
        """
        Split text into chunks respecting paragraph breaks (double newlines).
        Each chunk will contain at most max_words words.
        """
        # Split by double newlines to get paragraphs
        paragraphs = re.split(r"\n\s*\n", text)

        chunks = []
        current_chunk = []
        current_word_count = 0

        for paragraph in paragraphs:
            # Skip empty paragraphs
            if not paragraph.strip():
                continue

            # Count words in this paragraph (approximation)
            # For LaTeX, we'll consider non-command text
            paragraph_words = len(re.findall(r"(?<!\\)[a-zA-Z0-9]+", paragraph))

            # If adding this paragraph exceeds the limit and we already have content,
            # store the current chunk and start a new one
            if current_word_count + paragraph_words > max_words and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [paragraph]
                current_word_count = paragraph_words
            # Otherwise add to current chunk
            else:
                current_chunk.append(paragraph)
                current_word_count += paragraph_words

        # Add the last chunk if there's anything left
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

    def create_diff_file(self, original: str, improved: str, output_path: str):
        """Create a file showing differences in standard unified diff format for VSCode highlighting."""
        # Split both texts into lines
        original_lines = original.splitlines()
        improved_lines = improved.splitlines()

        # Get the diff in unified format
        diff = list(
            difflib.unified_diff(
                original_lines,
                improved_lines,
                fromfile="original",
                tofile="improved",
                lineterm="",
            )
        )

        # Write the diff to file
        with open(output_path, "w", encoding="utf-8") as file:
            file.write("\n".join(diff))

    def create_latexdiff_file(self, original: str, improved: str, output_path: str) -> bool:
        """Create a diff file using latexdiff for better LaTeX-aware diff."""
        # Write improved text to temporary file
        with (
            tempfile.NamedTemporaryFile("w", suffix=".tex") as improved_file,
            tempfile.NamedTemporaryFile("w", suffix=".tex", delete=False) as original_file,
        ):
            improved_file.write(improved)
            improved_file.flush()

            original_file.write(original)
            original_file.flush()

            # Run latexdiff
            try:
                command = [
                    "latexdiff",
                    original_file.name,
                    improved_file.name,
                ]

                # Show command being run
                self.logger.info(f"Running: {' '.join(command)}")

                run = subprocess.run(
                    command, check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE
                )
                with open(output_path, "wb") as output:
                    output.write(run.stdout)
                return True
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Error running latexdiff: {e}")
                self.logger.error(" ".join(command))
                self.logger.error(e.stderr.decode("utf-8"))
                return False

    @staticmethod
    def remove_think_tags(text):
        """
        Removes all <think>...</think> tags and their content from the input text.

        Args:
            text (str): Text potentially containing <think> tags

        Returns:
            str: Cleaned text with all <think> tags and their content removed
        """
        # Pattern matches <think> tags and everything between them (including newlines)
        pattern = r"<think>.*?</think>"

        # Remove the tags and their content
        # re.DOTALL flag ensures . matches newlines as well
        cleaned_text = re.sub(pattern, "", text, flags=re.DOTALL)

        return cleaned_text

    def post_process_chunk(self, text):
        markers = (
            "Here is the improved",
            "After careful consideration and adjustments",
        )
        for marker in markers:
            if text.startswith(marker):
                text = "\n".join(text.split("\n")[1:]).strip()

        text = self.remove_think_tags(text).strip()
        if text.count("```") == 2:
            text = text.split("```")[1].strip()

        text = text.strip("`")
        if text.startswith("latex"):
            text = text[len("latex") :]

        return text.strip()
