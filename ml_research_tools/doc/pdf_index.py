#!/usr/bin/env python3
"""
PDF Index Tool - Extract text from PDFs and build searchable index
"""

import argparse
import logging
import pathlib
import re
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Generator, List, Optional, Tuple

import joblib
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from ml_research_tools.core.base_tool import BaseTool
from ml_research_tools.core.config import Config

logger = logging.getLogger(__name__)


@dataclass
class PDFDocument:
    """Represents a PDF document in the index."""

    pdf_path: str
    file_mtime: float
    file_size: int


@dataclass
class SearchResult:
    """Represents a search result."""

    pdf_path: str
    page_num: int
    snippet: str
    rank: float


class PDFIndexDB:
    """Handles SQLite FTS5 database operations."""

    def __init__(self, index_path: pathlib.Path):
        self.db_path = index_path / "index.db"
        self.conn: Optional[sqlite3.Connection] = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def connect(self):
        """Connect to database and initialize schema."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

        # Enable WAL mode for better concurrent access
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA cache_size=10000")
        self.conn.execute("PRAGMA temp_store=MEMORY")

        self._create_schema()

    def _create_schema(self):
        """Create database schema if not exists."""
        # Documents table
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pdf_path TEXT UNIQUE NOT NULL,
                file_mtime REAL NOT NULL,
                file_size INTEGER NOT NULL,
                indexed_at REAL NOT NULL
            )
        """
        )

        # Create index on pdf_path for faster lookups
        self.conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_pdf_path ON documents(pdf_path)
        """
        )

        # FTS5 virtual table for full-text search
        self.conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS pdf_content USING fts5(
                doc_id UNINDEXED,
                page_num UNINDEXED,
                content,
                tokenize='porter unicode61'
            )
        """
        )

        self.conn.commit()

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def document_exists(self, pdf_path: str, file_mtime: float) -> bool:
        """Check if document is already indexed with same mtime."""
        cursor = self.conn.execute(
            "SELECT id FROM documents WHERE pdf_path = ? AND file_mtime = ?", (pdf_path, file_mtime)
        )
        return cursor.fetchone() is not None

    def get_indexed_count(self) -> int:
        """Get total number of indexed documents."""
        cursor = self.conn.execute("SELECT COUNT(*) FROM documents")
        return cursor.fetchone()[0]

    def get_page_count(self) -> int:
        """Get total number of indexed pages."""
        cursor = self.conn.execute("SELECT COUNT(*) FROM pdf_content")
        return cursor.fetchone()[0]

    def remove_document(self, pdf_path: str):
        """Remove document and its content from index."""
        cursor = self.conn.execute("SELECT id FROM documents WHERE pdf_path = ?", (pdf_path,))
        row = cursor.fetchone()
        if row:
            doc_id = row[0]
            self.conn.execute("DELETE FROM pdf_content WHERE doc_id = ?", (doc_id,))
            self.conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))

    def add_document(self, doc: PDFDocument, pages_text: List[Tuple[int, str]]):
        """Add document and its pages to index."""
        # Insert document
        cursor = self.conn.execute(
            """INSERT INTO documents (pdf_path, file_mtime, file_size, indexed_at)
               VALUES (?, ?, ?, ?)""",
            (doc.pdf_path, doc.file_mtime, doc.file_size, time.time()),
        )
        doc_id = cursor.lastrowid

        # Insert pages in batch
        self.conn.executemany(
            "INSERT INTO pdf_content (doc_id, page_num, content) VALUES (?, ?, ?)",
            [(doc_id, page_num, text) for page_num, text in pages_text],
        )

    def search(self, query: str, limit: int) -> List[SearchResult]:
        """Search index with FTS5 query."""
        try:
            cursor = self.conn.execute(
                """
                SELECT
                    d.pdf_path,
                    c.page_num,
                    snippet(pdf_content, 2, '[HIGHLIGHT]', '[/HIGHLIGHT]', '...', 32) as snippet,
                    rank
                FROM pdf_content c
                JOIN documents d ON d.id = c.doc_id
                WHERE pdf_content MATCH ?
                ORDER BY rank
                LIMIT ?
            """,
                (query, limit),
            )

            results = []
            for row in cursor:
                results.append(
                    SearchResult(
                        pdf_path=row["pdf_path"],
                        page_num=row["page_num"],
                        snippet=row["snippet"],
                        rank=row["rank"],
                    )
                )
            return results
        except sqlite3.OperationalError as e:
            logger.error(f"Search error: {e}")
            return []

    def regex_search(self, pattern: str, limit: int) -> List[SearchResult]:
        """Search using regex pattern (slower, scans all content)."""
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            logger.error(f"Invalid regex pattern: {e}")
            return []

        cursor = self.conn.execute(
            """
            SELECT d.pdf_path, c.page_num, c.content
            FROM pdf_content c
            JOIN documents d ON d.id = c.doc_id
        """
        )

        results = []
        for row in cursor:
            content = row["content"]
            match = compiled.search(content)
            if match:
                # Create snippet around match
                start = max(0, match.start() - 100)
                end = min(len(content), match.end() + 100)
                snippet = content[start:end]

                results.append(
                    SearchResult(
                        pdf_path=row["pdf_path"],
                        page_num=row["page_num"],
                        snippet=f"...{snippet}...",
                        rank=0.0,
                    )
                )

                if len(results) >= limit:
                    break

        return results


class PDFIndexTool(BaseTool):
    name = "pdf-index"
    description = "Build searchable index of PDF documents"

    def __init__(self, services) -> None:
        """Initialize the PDF index tool."""
        super().__init__(services)
        self.logger = logging.getLogger(__name__)

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add tool-specific arguments to the parser."""
        parser.add_argument(
            "--input-dir",
            type=pathlib.Path,
            default=".",
            help="Directory containing PDF files to index",
        )
        parser.add_argument(
            "--index-dir",
            type=pathlib.Path,
            help="Directory to store index (default: <input_dir>/pdf_index)",
        )
        parser.add_argument("--rebuild", action="store_true", help="Rebuild index from scratch")
        parser.add_argument(
            "--n-jobs",
            "-n",
            type=int,
            default=-1,
            help="Number of parallel jobs (default: all CPUs)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Number of documents to commit at once (default: 100)",
        )
        parser.add_argument(
            "--no-search", action="store_true", help="Only build index, skip interactive search"
        )
        parser.add_argument(
            "--only-search", action="store_true", help="Only build index, skip interactive search"
        )
        parser.add_argument("--limit", default=100, help="Results limit")

    def execute(self, config: Config, args: argparse.Namespace) -> int:
        """Execute the PDF indexing tool."""
        # Setup paths
        input_dir = args.input_dir.resolve()
        if not input_dir.exists():
            self.console.print(f"[red]Error: Directory not found: {input_dir}[/red]")
            return 1

        index_dir = args.index_dir or (input_dir / "pdf_index")
        index_dir.mkdir(exist_ok=True, parents=True)

        # Build/update index
        self.console.print(
            Panel.fit(
                f"[bold cyan]PDF Indexer[/bold cyan]\n"
                f"Input: {input_dir}\n"
                f"Index: {index_dir}",
                border_style="cyan",
            )
        )

        if not args.only_search:
            success = self._build_index(input_dir, index_dir, args)
            if not success:
                return 1

        # Interactive search
        if not args.no_search:
            self._interactive_search(index_dir, limit=args.limit)

        return 0

    def _build_index(self, input_dir: pathlib.Path, index_dir: pathlib.Path, args) -> bool:
        """Build or update the PDF index."""
        # Find all PDF files
        pdf_files = list(input_dir.rglob("*.pdf"))

        if not pdf_files:
            self.console.print("[yellow]No PDF files found[/yellow]")
            return False

        self.console.print(f"Found [cyan]{len(pdf_files)}[/cyan] PDF files")

        with PDFIndexDB(index_dir) as db:
            if args.rebuild:
                self.console.print("[yellow]Rebuilding index from scratch...[/yellow]")
                db.conn.execute("DELETE FROM pdf_content")
                db.conn.execute("DELETE FROM documents")
                db.conn.commit()

            # Filter files that need indexing
            files_to_index = []
            for pdf_path in pdf_files:
                try:
                    stat = pdf_path.stat()
                    rel_path = str(pdf_path.relative_to(input_dir))

                    if not db.document_exists(rel_path, stat.st_mtime):
                        files_to_index.append((pdf_path, rel_path, stat))
                    else:
                        self.logger.debug(f"Skipping already indexed: {rel_path}")
                except Exception as e:
                    self.logger.warning(f"Error checking {pdf_path}: {e}")

            if not files_to_index:
                self.console.print("[green]Index is up to date[/green]")
                self._print_index_stats(db)
                return True

            self.console.print(f"Indexing [cyan]{len(files_to_index)}[/cyan] files...")

            # Extract text in parallel
            results = joblib.Parallel(n_jobs=args.n_jobs, return_as="generator")(
                joblib.delayed(self._extract_pdf_text)(pdf_path, rel_path, stat)
                for pdf_path, rel_path, stat in files_to_index
            )

            # Insert into database with progress
            indexed_count = 0
            batch = []

            with self.create_progress(console=self.console) as progress:
                task = progress.add_task("Indexing PDFs", total=len(files_to_index))

                for result in results:
                    progress.update(task, advance=1)

                    if result is None:
                        continue

                    doc, pages_text = result
                    if not pages_text:
                        self.logger.warning(f"No text extracted from {doc.pdf_path}")
                        continue

                    batch.append((doc, pages_text))

                    # Commit in batches
                    if len(batch) >= args.batch_size:
                        self._commit_batch(db, batch)
                        indexed_count += len(batch)
                        batch = []

                # Commit remaining
                if batch:
                    self._commit_batch(db, batch)
                    indexed_count += len(batch)

            self.console.print(f"[green]Successfully indexed {indexed_count} documents[/green]")
            self._print_index_stats(db)

        return True

    @staticmethod
    def _extract_pdf_text(
        pdf_path: pathlib.Path, rel_path: str, stat
    ) -> Optional[Tuple[PDFDocument, List[Tuple[int, str]]]]:
        """Extract text from PDF file."""
        import fitz

        try:
            doc = PDFDocument(pdf_path=rel_path, file_mtime=stat.st_mtime, file_size=stat.st_size)

            pages_text = []

            with fitz.open(pdf_path) as pdf_doc:
                for page_num, page in enumerate(pdf_doc):
                    text = page.get_text()
                    text = text.replace("-\n", "")
                    pages_text.append((page_num + 1, text))

            return doc, pages_text

        except Exception as e:
            logger.warning(f"Failed to extract text from {rel_path}: {e}")
            return None

    def _commit_batch(self, db: PDFIndexDB, batch: List[Tuple[PDFDocument, List[Tuple[int, str]]]]):
        """Commit a batch of documents to database."""
        for doc, pages_text in batch:
            try:
                # Remove old version if exists
                db.remove_document(doc.pdf_path)
                db.add_document(doc, pages_text)
            except Exception as e:
                self.logger.error(f"Error indexing {doc.pdf_path}: {e}")

        db.conn.commit()

    def _print_index_stats(self, db: PDFIndexDB):
        """Print index statistics."""
        doc_count = db.get_indexed_count()
        page_count = db.get_page_count()

        table = Table(show_header=False, box=None)
        table.add_row("Documents:", f"[cyan]{doc_count:,}[/cyan]")
        table.add_row("Pages:", f"[cyan]{page_count:,}[/cyan]")

        self.console.print(Panel(table, title="Index Statistics", border_style="green"))

    def _interactive_search(self, index_dir: pathlib.Path, limit):
        """Interactive search interface."""
        self.console.print("\n" + "=" * 70)
        self.console.print(
            Panel.fit(
                "[bold green]Interactive Search[/bold green]\n\n"
                "Search modes:\n"
                "  • [cyan]text query[/cyan] - Full-text search\n"
                "  • [cyan]regex:pattern[/cyan] - Regular expression search\n"
                '  • [cyan]"exact phrase"[/cyan] - Phrase search\n'
                "  • [cyan]term1 AND term2[/cyan] - Boolean search\n"
                "  • [cyan]exit[/cyan] or [cyan]quit[/cyan] - Exit\n",
                border_style="green",
            )
        )

        with PDFIndexDB(index_dir) as db:
            while True:
                try:
                    query = Prompt.ask("\n[bold cyan]Query[/bold cyan]", default="")

                    if not query or query.lower() in ["exit", "quit", "q"]:
                        self.console.print("[yellow]Goodbye![/yellow]")
                        break

                    # Execute search
                    start_time = time.time()

                    if query.startswith("regex:"):
                        pattern = query[6:].strip()
                        results = db.regex_search(pattern, limit=limit)
                    else:
                        results = db.search(query, limit=limit)

                    elapsed = time.time() - start_time

                    # Display results
                    self._display_results(results, elapsed)

                except KeyboardInterrupt:
                    self.console.print("\n[yellow]Search cancelled[/yellow]")
                    break
                except Exception as e:
                    self.console.print(f"[red]Error: {e}[/red]")

    def _display_results(self, results: List[SearchResult], elapsed: float):
        """Display search results."""
        if not results:
            self.console.print("[yellow]No results found[/yellow]")
            return

        self.console.print(f"\n[green]Found {len(results)} results in {elapsed:.3f}s[/green]\n")

        groupped = defaultdict(list)
        for result in results:
            groupped[result.pdf_path].append(result)

        for i, (doc, entries) in enumerate(groupped.items(), 1):  # Show top 20
            # Format snippet with highlighting
            entries = sorted(entries, key=lambda x: x.page_num)
            content = ""
            last_page = None
            for result in entries:
                snippet = result.snippet
                if "[HIGHLIGHT]" in snippet and "[/HIGHLIGHT]" in snippet:
                    snippet = result.snippet.replace("[HIGHLIGHT]", "[bold yellow]")
                    snippet = snippet.replace("[/HIGHLIGHT]", "[/bold yellow]")
                if last_page == result.page_num:
                    content += f"\n{snippet}\n"
                else:
                    content += f"[dim]Page {result.page_num}[/dim]\n{snippet}\n"

                last_page = result.page_num

            content = content.strip()
            # Create result panel
            try:
                self.console.print(
                    Panel(
                        content, title=f"[bold]{i}. {doc}[/bold]", border_style="blue", expand=False
                    )
                )
            except:
                self.console.print("{i}. {doc}")
                print(content)

        self.console.print(f"[dim]{len(results)} entries ({len(groupped)} documents)[/dim]")
