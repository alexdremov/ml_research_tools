#!/usr/bin/env python3
"""
Tool to download Weights & Biases (W&B) run logs to local JSON files.
"""

import argparse
import json
import logging
import os
import re
from typing import Set

import wandb
from rich.panel import Panel
from wandb.apis.public.runs import Run as WandbRun
from wandb.apis.public.runs import Runs as WandbRuns

from ml_research_tools.core.base_tool import BaseTool


class WandbDownloaderTool(BaseTool):
    """Tool for downloading W&B run logs to local JSON files."""

    name = "wandb-downloader"
    description = "Download artifacts and runs from Weights & Biases"

    def __init__(self, services) -> None:
        """Initialize the W&B downloader tool."""
        super().__init__(services)
        self.logger = logging.getLogger(__name__)

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add tool-specific arguments to the parser."""
        parser.add_argument(
            "--entity",
            "-e",
            default=os.environ.get("WANDB_ENTITY"),
            help="W&B entity (username or team name). Can also use WANDB_ENTITY env variable.",
        )

        parser.add_argument(
            "--project",
            "-p",
            default=os.environ.get("WANDB_PROJECT"),
            help="W&B project name. Can also use WANDB_PROJECT env variable.",
        )

        parser.add_argument(
            "--output-dir",
            "-o",
            default="wandb_logs",
            help="Directory to save log files (default: wandb_logs)",
        )

        parser.add_argument(
            "--timeout",
            "-t",
            type=int,
            default=30,
            help="API timeout in seconds (default: 30)",
        )

        parser.add_argument(
            "--quiet",
            "-q",
            action="store_true",
            help="Suppress progress bar and detailed logging",
        )

        parser.add_argument(
            "--no-delete",
            action="store_true",
            help="Don't delete logs for runs that no longer exist",
        )

    def download_wandb_logs(
        self,
        entity: str,
        project: str,
        output_dir: str = "wandb_logs",
        timeout: int = 30,
        quiet: bool = False,
        delete_outdated: bool = True,
    ) -> int:
        """
        Download W&B logs for a specified project to local JSON files.

        Args:
            entity: The W&B entity (username or team name)
            project: The W&B project name
            output_dir: Directory where log files will be saved
            timeout: API timeout in seconds
            quiet: If True, suppress progress bar
            delete_outdated: If True, delete logs for runs that no longer exist
        """
        # Initialize the W&B API
        self.logger.info(f"Initializing W&B API for {entity}/{project}")
        try:
            api = wandb.Api(timeout=timeout)
        except Exception as e:
            self.logger.exception(f"Failed to initialize W&B API")
            return 1

        # Ensure the output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Retrieve all runs from the specified project
        self.logger.info("Retrieving runs from W&B...")
        try:
            runs: WandbRuns = api.runs(
                path=f"{entity}/{project}",
                per_page=32,
                order="-created_at",
            )
        except Exception as e:
            self.logger.exception(f"Failed to retrieve runs for {entity}/{project}")
            return 1

        # Use Rich Progress for loading metadata
        self.logger.info(f"Found {len(runs)} runs, loading metadata...")

        # Create a set of current run IDs from W&B
        current_run_ids = set()

        # Use rich progress if not in quiet mode
        if not quiet:
            with self.create_progress() as progress:
                meta_task = progress.add_task("[cyan]Loading run metadata...", total=len(runs))

                for run in runs:
                    current_run_ids.add(run.id)
                    progress.update(
                        meta_task, advance=1, description=f"[cyan]Loading run {run.id}..."
                    )
        else:
            # Simple operation if quiet mode
            current_run_ids = set(run.id for run in runs)

        # Display summary of runs
        if not quiet:
            self.console.print(
                Panel(
                    f"[bold]W&B Project Summary[/bold]\n"
                    f"🔹 Entity: [cyan]{entity}[/cyan]\n"
                    f"🔹 Project: [green]{project}[/green]\n"
                    f"🔹 Total runs: [yellow]{len(current_run_ids)}[/yellow]\n"
                    f"🔹 Output directory: [cyan]{output_dir}[/cyan]",
                    title="W&B Downloader",
                    border_style="blue",
                )
            )

        if delete_outdated:
            # Handle deletion of outdated logs
            try:
                self.logger.info("Checking for outdated logs...")
                deleted_count = self.delete_outdated_logs(output_dir, current_run_ids)
                if deleted_count > 0:
                    self.logger.info(f"Deleted {deleted_count} outdated log file(s)")
            except Exception as e:
                self.logger.warning(f"Error during deletion of outdated logs: {e}")

        # Use rich progress for run processing
        if not quiet:
            with self.create_progress() as progress:
                task = progress.add_task("[cyan]Processing runs...", total=len(runs))

                for run in runs:
                    run_name = self.sanitize_filename(run.name)
                    progress.update(
                        task, description=f"[cyan]Processing run [bold]{run_name}[/bold]..."
                    )

                    try:
                        self.process_run(run, output_dir)
                    except Exception as e:
                        self.logger.warning(f"Error processing run {run.name}/{run.id}: {e}")

                    progress.update(task, advance=1)
        else:
            # Process runs without progress display
            for run in runs:
                try:
                    self.process_run(run, output_dir)
                except Exception as e:
                    self.logger.warning(f"Error processing run {run.name}/{run.id}: {e}")

        self.logger.info(f"Successfully downloaded {len(runs)} run(s) to {output_dir}")
        return 0

    def execute(self, config, args: argparse.Namespace) -> int:
        """
        Execute the W&B log download with the provided arguments.

        Args:
            args: Parsed command-line arguments

        Returns:
            Exit code (0 for success, non-zero for error)
        """
        # Validate required arguments
        if not args.entity:
            self.logger.error("--entity is required (or set WANDB_ENTITY environment variable)")
            return 1

        if not args.project:
            self.logger.error("--project is required (or set WANDB_PROJECT environment variable)")
            return 1

        # Run the download
        status = self.download_wandb_logs(
            entity=args.entity,
            project=args.project,
            output_dir=args.output_dir,
            timeout=args.timeout,
            quiet=args.quiet,
            delete_outdated=not args.no_delete,
        )

        if status == 0:
            self.logger.info("Download completed successfully!")
        return status

    @staticmethod
    def sanitize_filename(name: str) -> str:
        """
        Sanitize the run name to create a valid filename.

        Args:
            name: The original run name

        Returns:
            A sanitized string suitable for use as a filename
        """
        return re.sub(r"[^\w\s\-\.]", "", name).strip().replace(" ", "_")

    def delete_outdated_logs(self, output_dir: str, current_run_ids: Set[str]) -> int:
        """
        Delete log files that do not correspond to any current run ID.

        Args:
            output_dir: Directory containing log files
            current_run_ids: Set of valid run IDs from W&B

        Returns:
            Number of files deleted
        """
        # List all files in the output directory
        local_files = os.listdir(output_dir)
        deleted_count = 0

        # Delete files that do not correspond to any current run ID
        for file in local_files:
            # Extract run ID from filename (assuming format: <sanitized_name>_<run_id>.json)
            match = re.match(r".*_(\w+)\.json$", file)
            if match:
                run_id = match.group(1)
                if run_id not in current_run_ids:
                    file_path = os.path.join(output_dir, file)
                    os.remove(file_path)
                    deleted_count += 1
                    self.logger.info(f"Deleted outdated log file: {file}")

        return deleted_count

    def process_run(self, run: WandbRun, output_dir: str) -> None:
        """
        Process a single W&B run and save its history to a JSON file.

        Args:
            run: W&B run object
            output_dir: Directory where the log file will be saved
        """
        # Sanitize the run name for use in filenames
        sanitized_name = self.sanitize_filename(run.name)

        # Construct the filename using run ID and sanitized run name
        filename = f"{sanitized_name}_{run.id}.json"
        filepath = os.path.join(output_dir, filename)

        # Get current last heartbeat time from W&B run
        current_last_heartbeat_time = run.heartbeatAt

        # Check if the file already exists to avoid redundant downloads
        if os.path.exists(filepath):
            try:
                with open(filepath, "r") as f:
                    existing_data = json.load(f)
                    existing_last_heartbeat_time = existing_data[0].get("last_heartbeat_time", None)

                # Skip updating if last heartbeat time hasn't changed
                if existing_last_heartbeat_time == current_last_heartbeat_time:
                    return
            except (json.JSONDecodeError, IndexError, KeyError) as e:
                self.logger.warning(f"Error reading existing file {filepath}: {e}. Will overwrite.")

        # Extract the history of the run as a dataframe
        try:
            history = run.history(pandas=True)
        except Exception as e:
            self.logger.warning(f"Failed to retrieve history for run {run.name}/{run.id}: {e}")
            return

        # Convert the dataframe to a dictionary
        history_dict = history.to_dict(orient="records")

        if len(history_dict) == 0:
            history_dict = [dict()]

        # Add last heartbeat time and run info to history[0]
        history_dict[0]["last_heartbeat_time"] = current_last_heartbeat_time
        history_dict[0]["run_info"] = {
            "id": run.id,
            "name": run.name,
            "config": run.config,
        }

        # Save the dictionary as a JSON file
        try:
            with open(filepath, "w") as f:
                json.dump(history_dict, f, indent=4)
        except Exception as e:
            self.logger.error(f"Failed to save log file {filepath}: {e}")
