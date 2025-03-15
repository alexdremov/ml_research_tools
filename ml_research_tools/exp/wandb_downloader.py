#!/usr/bin/env python3
"""
Script to download Weights & Biases (W&B) run logs to local JSON files.
"""

import argparse
import json
import logging
import os
import re
import sys
from typing import Any, Set

import wandb
from tqdm import tqdm

logger = logging.getLogger("wandb_downloader")


def sanitize_filename(name: str) -> str:
    """
    Sanitize the run name to create a valid filename.

    Args:
        name: The original run name

    Returns:
        A sanitized string suitable for use as a filename
    """
    return re.sub(r'[^\w\s\-\.]', '', name).strip().replace(' ', '_')


def download_wandb_logs(
    entity: str,
    project: str,
    output_dir: str = 'wandb_logs',
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
    try:
        api = wandb.Api(timeout=timeout)
    except Exception as e:
        logger.exception(f"Failed to initialize W&B API")
        return 1

    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Retrieve all runs from the specified project
    try:
        runs = api.runs(f"{entity}/{project}")
    except Exception as e:
        logger.exception(f"Failed to retrieve runs for {entity}/{project}")
        return 1

    # Create a set of current run IDs from W&B
    current_run_ids = set(run.id for run in runs)

    if delete_outdated:
        # Handle deletion of outdated logs
        try:
            delete_outdated_logs(output_dir, current_run_ids)
        except Exception as e:
            logger.warning(f"Error during deletion of outdated logs: {e}")

    # Use tqdm to create a progress bar for the runs
    runs_iter = runs
    if not quiet:
        runs_iter = tqdm(runs, desc="Processing runs", unit="run")

    # Process each run
    for run in runs_iter:
        try:
            # Update progress bar with current run details
            if not quiet and hasattr(runs_iter, 'set_postfix'):
                runs_iter.set_postfix(run_id=run.id, run_name=sanitize_filename(run.name))

            process_run(run, output_dir, quiet)
        except Exception as e:
            logger.warning(f"Error processing run {run.id}: {e}")
            continue

    return 0


def delete_outdated_logs(output_dir: str, current_run_ids: Set[str]) -> None:
    """
    Delete log files that do not correspond to any current run ID.

    Args:
        output_dir: Directory containing log files
        current_run_ids: Set of valid run IDs from W&B
    """
    # List all files in the output directory
    local_files = os.listdir(output_dir)

    # Delete files that do not correspond to any current run ID
    for file in local_files:
        # Extract run ID from filename (assuming format: <sanitized_name>_<run_id>.json)
        match = re.match(r".*_(\w+)\.json$", file)
        if match:
            run_id = match.group(1)
            if run_id not in current_run_ids:
                file_path = os.path.join(output_dir, file)
                os.remove(file_path)
                logger.info(f"Deleted outdated log file: {file}")


def process_run(run: Any, output_dir: str, quiet: bool = False) -> None:
    """
    Process a single W&B run and save its history to a JSON file.

    Args:
        run: W&B run object
        output_dir: Directory where the log file will be saved
        quiet: If True, suppress detailed logging
    """
    # Sanitize the run name for use in filenames
    sanitized_name = sanitize_filename(run.name)

    # Construct the filename using run ID and sanitized run name
    filename = f"{sanitized_name}_{run.id}.json"
    filepath = os.path.join(output_dir, filename)

    if not quiet:
        logger.info(f"Processing run: {run.name} ({run.id})")

    # Get current last heartbeat time from W&B run
    current_last_heartbeat_time = run.heartbeatAt

    # Check if the file already exists to avoid redundant downloads
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                existing_data = json.load(f)
                existing_last_heartbeat_time = existing_data[0].get('last_heartbeat_time', None)

            # Skip updating if last heartbeat time hasn't changed
            if existing_last_heartbeat_time == current_last_heartbeat_time:
                if not quiet:
                    logger.debug(f"Skipping unchanged run: {run.name} ({run.id})")
                return
        except (json.JSONDecodeError, IndexError, KeyError) as e:
            logger.warning(f"Error reading existing file {filepath}: {e}. Will overwrite.")

    # Extract the history of the run as a dataframe
    try:
        history = run.history()
    except Exception as e:
        logger.warning(f"Failed to retrieve history for run {run.id}: {e}")
        return

    # Convert the dataframe to a dictionary
    history_dict = history.to_dict(orient="records")

    if not history_dict:
        logger.warning(f"No history data for run {run.id}")
        return

    # Add last heartbeat time and run info to history[0]
    history_dict[0]['last_heartbeat_time'] = current_last_heartbeat_time
    history_dict[0]['run_info'] = {
        'id': run.id,
        'name': run.name,
        'config': run.config,
    }

    # Save the dictionary as a JSON file
    try:
        with open(filepath, 'w') as f:
            json.dump(history_dict, f, indent=4)
        if not quiet:
            logger.info(f"Saved log file: {filename}")
    except Exception as e:
        logger.error(f"Failed to save log file {filepath}: {e}")


def parse_arguments(args) -> argparse.Namespace:
    """
    Parse command line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        prog="wandb_downloader",
        description="Download Weights & Biases run logs to local JSON files."
    )

    parser.add_argument(
        "--entity", "-e",
        default=os.environ.get("WANDB_ENTITY"),
        help="W&B entity (username or team name). Can also use WANDB_ENTITY env variable."
    )

    parser.add_argument(
        "--project", "-p",
        default=os.environ.get("WANDB_PROJECT"),
        help="W&B project name. Can also use WANDB_PROJECT env variable."
    )

    parser.add_argument(
        "--output-dir", "-o",
        default="wandb_logs",
        help="Directory to save log files (default: wandb_logs)"
    )

    parser.add_argument(
        "--timeout", "-t",
        type=int,
        default=30,
        help="API timeout in seconds (default: 30)"
    )

    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress bar and detailed logging"
    )

    parser.add_argument(
        "--no-delete",
        action="store_true",
        help="Don't delete logs for runs that no longer exist"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args(args)

    # Validate required arguments
    if not args.entity:
        parser.error("--entity is required (or set WANDB_ENTITY environment variable)")
    if not args.project:
        parser.error("--project is required (or set WANDB_PROJECT environment variable)")

    return args


def main(args=None) -> int:
    """Main entry point for the script."""
    args = parse_arguments(args)

    # Configure logging level
    if args.debug:
        logger.setLevel(logging.DEBUG)
    elif args.quiet:
        logger.setLevel(logging.WARNING)


    # Run the download
    status = download_wandb_logs(
        entity=args.entity,
        project=args.project,
        output_dir=args.output_dir,
        timeout=args.timeout,
        quiet=args.quiet,
        delete_outdated=not args.no_delete,
    )

    if status == 0:
        logger.info("Download completed successfully.")
    return status


if __name__ == "__main__":
    sys.exit(main())
