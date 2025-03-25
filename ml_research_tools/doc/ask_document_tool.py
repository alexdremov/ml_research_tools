#!/usr/bin/env python3
"""
Ask Document Tool - Interactive chat with document content using LLMs.

This tool allows users to have a conversational interface with various document types
(PDF, TXT, TEX, etc.) by leveraging large language models. It maintains conversation
context and provides streaming responses for a smooth experience.
"""

import argparse
import os
import re
import tempfile
import textwrap
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from openai.types.chat.chat_completion import ChatCompletion
from rich.console import Console
from rich.highlighter import ReprHighlighter
from rich.panel import Panel
from rich.prompt import Prompt
from rich.theme import Theme

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from bs4 import BeautifulSoup

    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

try:
    import PyPDF2

    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

from ml_research_tools.cache import RedisCache, cached, generate_cache_key
from ml_research_tools.core.base_tool import BaseTool
from ml_research_tools.core.config import Config, get_config
from ml_research_tools.core.llm_tools import (
    LLMClient,
    create_llm_client,
    generate_completion_params,
)
from ml_research_tools.core.logging_tools import get_logger

# Initialize logger
logger = get_logger(__name__)

# Document type handlers will be added here
# For now, we'll implement a simple text handler and add others later


class DocumentParser:
    """Base class for document content extractors."""

    @classmethod
    def can_handle(cls, file_path: str) -> bool:
        """Check if this parser can handle the given file type."""
        raise NotImplementedError("Subclasses must implement this method")

    @classmethod
    def extract_content(cls, file_path: str) -> str:
        """Extract text content from the document."""
        raise NotImplementedError("Subclasses must implement this method")

    @classmethod
    def should_cache(cls) -> bool:
        """
        Determine if this parser's results should be cached.

        By default, local document parsers don't need caching as they're
        typically fast to access. URL parsers should override this.
        """
        return False


class TextDocumentParser(DocumentParser):
    """Parser for plain text files (txt, md, etc.)."""

    @classmethod
    def can_handle(cls, file_path: str) -> bool:
        """Check if this parser can handle the given file type."""
        ext = Path(file_path).suffix.lower()
        return ext in [".txt", ".md", ".text"]

    @classmethod
    def extract_content(cls, file_path: str) -> str:
        """Extract text content from text files."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            # Try with different encoding
            try:
                with open(file_path, "r", encoding="latin-1") as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Failed to read text file with latin-1 encoding: {e}")
                raise


class CodeDocumentParser(TextDocumentParser):
    """Parser for code."""

    @classmethod
    def can_handle(cls, file_path: str) -> bool:
        """Check if this parser can handle the given file type."""
        ext = Path(file_path).suffix.lower()
        return ext in [".py", ".cpp"]

    @classmethod
    def extract_content(cls, file_path: str) -> str:
        content = TextDocumentParser.extract_content(file_path)
        return f"```\n{content}\n```\n"


class LatexDocumentParser(TextDocumentParser):
    """Parser for LaTeX files."""

    @classmethod
    def can_handle(cls, file_path: str) -> bool:
        """Check if this parser can handle the given file type."""
        ext = Path(file_path).suffix.lower()
        return ext in [".tex", ".latex", ".bib"]


class PDFDocumentParser(DocumentParser):
    """Parser for PDF files."""

    @classmethod
    def can_handle(cls, file_path: str) -> bool:
        """Check if this parser can handle the given file type."""
        if not PDF_SUPPORT:
            return False
        ext = Path(file_path).suffix.lower()
        return ext == ".pdf"

    @classmethod
    def extract_content(cls, file_path: str) -> str:
        """Extract text content from PDF files."""
        if not PDF_SUPPORT:
            raise RuntimeError("PDF support is not available. Install PyPDF2 package.")

        try:
            text = ""
            with open(file_path, "rb") as file:
                reader = PyPDF2.PdfReader(file)
                for page_num in range(len(reader.pages)):
                    page = reader.pages[page_num]
                    text += page.extract_text() + "\n\n"
            return text
        except Exception as e:
            logger.error(f"Failed to extract text from PDF: {e}")
            raise


class URLParser(DocumentParser):
    """Parser for URLs (web pages and downloadable files)."""

    @classmethod
    def can_handle(cls, file_path: str) -> bool:
        """Check if this parser can handle the given URL."""
        if not REQUESTS_AVAILABLE:
            return False

        # Check if the input looks like a URL
        try:
            parsed = urlparse(file_path)
            return parsed.scheme in ["http", "https"] and parsed.netloc
        except Exception:
            return False

    @classmethod
    def extract_content(cls, url: str) -> str:
        """Extract content from a URL (webpage or downloadable file)."""
        if not REQUESTS_AVAILABLE:
            raise RuntimeError(
                "URL support requires the 'requests' package. Please install it first."
            )

        logger.info(f"Fetching content from URL: {url}")

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()  # Raise exception for non-200 status codes

            content_type = response.headers.get("Content-Type", "").lower()

            # Handle PDF files
            if "application/pdf" in content_type:
                if not PDF_SUPPORT:
                    raise RuntimeError(
                        "PDF parsing requires the PyPDF2 package. Please install it first."
                    )

                # Save the PDF to a temporary file
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
                    temp_file.write(response.content)
                    temp_path = temp_file.name

                # Extract text from the temporary PDF file
                try:
                    return cls._extract_pdf_content(temp_path)
                finally:
                    # Clean up the temporary file
                    try:
                        os.unlink(temp_path)
                    except Exception as e:
                        logger.warning(f"Failed to delete temporary PDF file: {e}")

            # Handle HTML content
            elif "text/html" in content_type:
                return cls._extract_html_content(response.text, url)

            # Handle plain text
            elif "text/plain" in content_type:
                return response.text

            # Handle other types as plain text with a warning
            else:
                logger.warning(f"Unknown content type: {content_type}, treating as plain text")
                return response.text

        except Exception as e:
            logger.error(f"Failed to fetch URL: {e}")
            if isinstance(e, requests.RequestException):
                raise RuntimeError(f"Failed to fetch URL: {str(e)}")
            raise

    @classmethod
    def _extract_pdf_content(cls, file_path: str) -> str:
        """Extract text from a PDF file."""
        text = ""
        with open(file_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                text += page.extract_text() + "\n\n"
        return text

    @classmethod
    def _extract_html_content(cls, html_content: str, url: str) -> str:
        """Extract text content from HTML."""
        if BS4_AVAILABLE:
            # Use BeautifulSoup for better HTML parsing if available
            soup = BeautifulSoup(html_content, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style", "header", "footer", "nav"]):
                script.extract()

            # Extract text
            text = soup.get_text(separator="\n", strip=True)

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = "\n".join(chunk for chunk in chunks if chunk)

            return f"URL: {url}\n\n{text}"
        else:
            # Basic HTML cleaning if BeautifulSoup is not available
            # This is not very effective but better than raw HTML
            text = re.sub(r"<script.*?>.*?</script>", "", html_content, flags=re.DOTALL)
            text = re.sub(r"<style.*?>.*?</style>", "", text, flags=re.DOTALL)
            text = re.sub(r"<.*?>", " ", text)
            text = re.sub(r"\s+", " ", text)

            return f"URL: {url}\n\n{text}"

    @classmethod
    def should_cache(cls) -> bool:
        """
        URLs should be cached as they're slow to fetch and might change over time.
        """
        return True


# Registry of document parsers
DOCUMENT_PARSERS = [
    URLParser,  # Try URL parser first
    TextDocumentParser,
    LatexDocumentParser,
    PDFDocumentParser,
    CodeDocumentParser,
    # Add more parsers here as they are implemented
]


def get_parser_for_document(file_path: str) -> Optional[DocumentParser]:
    """Get the appropriate parser for the given document."""
    for parser in DOCUMENT_PARSERS:
        if parser.can_handle(file_path):
            return parser
    return None


def generate_document_cache_key(document_path: str, prefix: str = "document") -> str:
    """
    Generate a cache key for a document.

    Args:
        document_path: Path or URL to the document
        prefix: Cache key prefix

    Returns:
        A unique cache key for the document
    """
    return generate_cache_key(kwargs={"path": document_path}, prefix=prefix)


@cached(prefix="document_content")
def load_document_with_cache(
    document_path: str,
    parser: DocumentParser,
    redis_cache: RedisCache,
) -> str:
    """
    Load document content with caching support.

    Args:
        document_path: Path or URL to the document
        parser: Document parser instance

    Returns:
        The document content
    """
    return parser.extract_content(document_path)


@cached(prefix="token_count")
def estimate_token_count_with_cache(
    text: str, redis_cache: RedisCache, model: str = "gpt-3.5-turbo"
) -> int:
    """
    Estimate the number of tokens in the given text with caching support.

    Args:
        text: The text to estimate tokens for
        model: The model name to use for token counting

    Returns:
        Estimated token count
    """
    if TIKTOKEN_AVAILABLE:
        # Use tiktoken for accurate token estimation if available
        try:
            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(text))
        except Exception as e:
            logger.warning(f"Error using tiktoken: {e}. Falling back to heuristic estimation.")

    # Fall back to a simple heuristic if tiktoken is not available
    # This is a very rough approximation
    words = text.split()
    # Approximately 0.75 tokens per word for English text
    return int(len(words) * 0.75)


class DocumentChat:
    """Interactive chat with document content."""

    def __init__(
        self,
        document_path: str,
        llm_client: LLMClient,
        verbose: bool = False,
        max_context_messages: int = 20,
        redis_cache: Optional[RedisCache] = None,
    ):
        """
        Initialize the document chat.

        Args:
            document_path: Path to the document file
            config: Application configuration
            verbose: Enable verbose output
            max_context_messages: Maximum number of messages to keep in context
            redis_cache: Optional Redis cache instance
            llm_preset: Optional LLM preset to use
            llm_tier: Optional LLM tier to use
        """
        self.document_path = document_path
        self.verbose = verbose
        self.max_context_messages = max_context_messages

        # Initialize or use provided Redis cache
        self.redis_cache = redis_cache
        self.llm_client = llm_client

        # Set up rich console
        custom_theme = Theme(
            {
                "info": "dim cyan",
                "user": "bold green",
                "assistant": "bold blue",
                "system": "yellow",
                "error": "bold red",
                "document": "magenta",
                "stats": "cyan",
                "cache": "bright_blue",
            }
        )
        self.console = Console(theme=custom_theme)
        self.highlighter = ReprHighlighter()

        # Show loading message for document
        is_url = URLParser.can_handle(document_path)
        doc_type = "URL" if is_url else "document"

        # Indicate if caching is enabled for this type of content
        parser = get_parser_for_document(document_path)
        if parser and parser.should_cache() and self.redis_cache and self.redis_cache.enabled:
            cache_indicator = " (with caching)"
        else:
            cache_indicator = ""

        logger.info(f"Loading {doc_type}{cache_indicator}...")

        # Extract document content
        self.document_content = self._load_document()

        # Indicate if the document was loaded from cache
        cache_status = (
            "[cache](from cache)"
            if hasattr(self, "_cache_hit") and self._cache_hit
            else "[cache](no cache)"
        )

        # Estimate token count
        self.token_count = self._estimate_tokens()

        # Calculate document size statistics
        char_count = len(self.document_content)
        word_count = len(self.document_content.split())

        # Format document sizes with appropriate units
        if char_count < 1024:
            char_size = f"{char_count} chars"
        elif char_count < 1024 * 1024:
            char_size = f"{char_count / 1024:.1f} KB"
        else:
            char_size = f"{char_count / (1024 * 1024):.1f} MB"

        # Get LLM info to display
        llm_info = f"[bold]{self.llm_client.config.model}[/bold]"

        # Show success message with token statistics and LLM info
        logger.info(f"Done! {cache_status}")
        logger.info(
            f"Document statistics: {word_count:,} words, {char_size}, approximately {self.token_count:,} tokens"
        )
        if llm_info:
            logger.info(f"Using LLM {llm_info}")

        # Warn if document is very large
        if self.token_count > 50000:
            logger.error(
                f"Warning: Document is very large ({self.token_count:,} tokens). Only the first part will be used for context."
            )

        # Document has been added to conversation yet
        self.document_added = False

        # Initialize conversation with just the system prompt (no document content)
        self.messages = [
            {
                "role": "system",
                "content": textwrap.dedent(
                    """\
                    You are a helpful assistant that answers questions about documents.
                    Please base your answers only on the information provided in the document context.
                    If the information is not in the document, say so. If the user requests,
                    you may provide information that is not in the document (only after explicit request),
                    but make it clear that it is not based on the document.
                    """
                ),
            }
        ]

    def _load_document(self) -> str:
        """Load and parse document content with caching."""
        if not os.path.exists(self.document_path) and not URLParser.can_handle(self.document_path):
            raise FileNotFoundError(f"Document not found: {self.document_path}")

        parser = get_parser_for_document(self.document_path)
        if parser is None:
            raise ValueError(f"Unsupported document type: {self.document_path}")

        try:
            # Check if this parser type should use caching
            should_use_cache = parser.should_cache()

            # Try to load from cache first if this parser type uses caching
            if (
                should_use_cache
                and self.redis_cache
                and self.redis_cache.enabled
                and not self.redis_cache.recache
            ):
                cache_key = generate_document_cache_key(self.document_path)
                cached_content = self.redis_cache.get(cache_key)
                if cached_content is not None:
                    self._cache_hit = True
                    return cached_content

            # If parser doesn't use caching or content not in cache, extract directly
            if not should_use_cache:
                content = parser.extract_content(self.document_path)
                self._cache_hit = False
                return content

            # If parser uses caching but content not found in cache, use cached function
            content = load_document_with_cache(
                document_path=self.document_path,
                parser=parser,
                redis_cache=self.redis_cache,
            )

            self._cache_hit = False
            return content

        except Exception as e:
            logger.error(f"Failed to parse document: {e}")
            if self.verbose:
                logger.exception("Document parsing error")
            raise

    def _estimate_tokens(self) -> int:
        """Estimate token count for document content with caching."""
        return estimate_token_count_with_cache(
            text=self.document_content,
            model=self.llm_client.config.model,
            redis_cache=self.redis_cache,
        )

    def _ensure_document_in_context(self):
        """Make sure document content is added to the conversation before any user questions."""
        if not self.document_added:
            # Display a message to the user
            logger.info("Adding document to conversation context...")

            # Calculate the maximum token count to include based on model limits
            # Use 80% of max_tokens for the document to leave room for conversation
            max_context_size = getattr(self.llm_client.config, "max_tokens", 4000)
            if max_context_size is not None:
                max_safe_tokens = int(
                    max_context_size * 0.8
                )  # Cap at 100k tokens as a safety limit
            else:
                max_safe_tokens = 1000000

            # If document exceeds safe token count, truncate and notify
            document_content = self.document_content
            if self.token_count > max_safe_tokens:
                # Estimate roughly how many characters to include based on token ratio
                # This is approximate and won't be perfectly accurate
                chars_per_token = len(document_content) / self.token_count
                approx_chars = int(max_safe_tokens * chars_per_token * 0.9)  # 10% safety margin

                document_content = document_content[:approx_chars]
                logger.warning(
                    f"Document truncated to approximately {max_safe_tokens:,} tokens due to model context limits."
                )

            # Add document content as context before the first user question
            document_message = {
                "role": "user",
                "content": f"Here is the document I want to ask about:\n\n{document_content}",
            }
            self.messages.append(document_message)

            context_message = {
                "role": "assistant",
                "content": "I have received the document. What would you like to know about it?",
            }
            self.messages.append(context_message)

            self.document_added = True

            # Calculate actual tokens used for the truncated document if needed
            if self.token_count > max_safe_tokens:
                truncated_tokens = estimate_token_count_with_cache(
                    document_content, self.llm_client.config.model
                )
                logger.info(
                    f"Document added to conversation (truncated to ~{truncated_tokens:,} tokens)."
                )
            else:
                logger.info(f"Document added to conversation ({self.token_count:,} tokens).")

    def add_user_message(self, content: str) -> None:
        """Add a user message to the conversation."""
        # Ensure document is in context before adding user message
        self._ensure_document_in_context()

        # Add the user's message
        self.messages.append({"role": "user", "content": content})

        # Trim context if needed
        if len(self.messages) > self.max_context_messages + 1:  # +1 for system message
            # Always keep the system message, document content, and response
            # System message (index 0)
            # Document content (index 1)
            # Assistant acknowledgment (index 2)
            # Then keep the most recent messages after that
            self.messages = [self.messages[0], self.messages[1], self.messages[2]] + self.messages[
                -(self.max_context_messages - 3) :
            ]

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to the conversation."""
        self.messages.append({"role": "assistant", "content": content})

    def stream_llm_response(self) -> str:
        """Stream the LLM response and return the complete response."""
        try:
            # Generate API parameters with the appropriate preset/tier
            params = generate_completion_params(
                llm_client=self.llm_client,
                messages=[{"role": m["role"], "content": m["content"]} for m in self.messages],
                stream=True,
            )

            # Get the raw OpenAI client from our LLMClient instance
            openai_client = self.llm_client.get_openai_client()

            # Make streaming request
            response = openai_client.chat.completions.create(**params)

            # Stream response
            collected_chunks = []
            collected_message = ""

            # Simply print each chunk as it comes in without the panel to prevent truncation
            self.console.print("\n[bold blue]Assistant:[/bold blue] ", end="")

            if not isinstance(response, ChatCompletion):
                for chunk in response:
                    content = chunk.choices[0].delta.content or ""
                    collected_chunks.append(content)
                    collected_message += content

                    # Print each chunk directly to console
                    self.console.print(content, end="", highlight=False)
            elif isinstance(response, ChatCompletion):
                collected_message = response.choices[0].message.content
                self.console.print(collected_message)
            else:
                assert False

            # Print a newline at the end
            self.console.print()

            return collected_message

        except Exception as e:
            logger.error(f"Error calling LLM API: {e}")
            if self.verbose:
                logger.exception("LLM API error")
            return f"Error: {str(e)}"

    def run_interactive_chat(self) -> None:
        """Run the interactive chat session."""
        # If it's a URL, use the URL as the title, otherwise use the filename
        if URLParser.can_handle(self.document_path):
            title = self.document_path
        else:
            title = os.path.basename(self.document_path)

        # This is a proper display element, so keeping it as console.print
        self.console.print(
            Panel(
                f"[bold]Ask Document: {title}[/bold]\n"
                "Type your questions about the document. Press Ctrl+C to exit.",
                title="Document Chat",
                border_style="green",
            )
        )

        try:
            while True:
                # Get user question
                question = Prompt.ask("\n[user]You")
                if not question.strip():
                    continue

                # Add user message to history
                self.add_user_message(question)

                # Stream LLM response
                response = self.stream_llm_response()

                # Add assistant response to history
                self.add_assistant_message(response)

        except KeyboardInterrupt:
            logger.info("Chat session ended.")
            return


class AskDocumentTool(BaseTool):
    """Tool for interactive chat with document content."""

    name = "ask-document"
    description = "Interactive chat with document content using LLMs"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add tool-specific arguments to the argument parser."""
        parser.add_argument(
            "document_path", type=str, help="Path to the document file or URL to chat with"
        )
        parser.add_argument("-q", "--question", type=str, help="Initial question to ask (optional)")
        parser.add_argument(
            "--max-context",
            type=int,
            default=20,
            help="Maximum number of messages to keep in context (default: 20)",
        )
        parser.add_argument(
            "--no-cache",
            action="store_true",
            help="Disable Redis caching for URL content (local files are not cached by default)",
        )

        # Note: LLM preset and tier options are already added globally in the main parser

    def execute(self, config: Config, args: argparse.Namespace) -> int:
        """Execute the tool with the provided arguments."""
        try:
            # List presets functionality is now handled at the global level
            document_path = args.document_path

            # Check if file exists or is a URL
            is_url = URLParser.can_handle(document_path)
            if not is_url and not os.path.exists(document_path):
                logger.error(f"Document not found: {document_path}")
                return 1

            # Configure Redis cache
            redis_config = config.redis
            if args.no_cache:
                redis_config.enabled = False

            redis_cache = self.services.get_typed("redis_cache", RedisCache)
            llm_client = self.services.get_typed("llm_client", LLMClient)

            # Create chat instance
            chat = DocumentChat(
                document_path=document_path,
                llm_client=llm_client,
                verbose=args.verbose if hasattr(args, "verbose") else False,
                max_context_messages=args.max_context,
                redis_cache=redis_cache,
            )

            # If initial question is provided, add it and get response
            if args.question:
                # This will automatically add the document to the context first
                chat.add_user_message(args.question)
                response = chat.stream_llm_response()
                chat.add_assistant_message(response)

            # Start interactive chat (document will be added on first question if not already)
            chat.run_interactive_chat()

            return 0

        except KeyboardInterrupt:
            logger.info("Operation cancelled by user")
            return 130
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            if hasattr(args, "verbose") and args.verbose:
                logger.exception("Detailed error:")
            return 1
