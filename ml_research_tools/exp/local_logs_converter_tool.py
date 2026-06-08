#!/usr/bin/env python3
"""
Tool to convert raw local JSONL logs and config files to standardized experiment JSON format.
"""

import argparse
import json
import logging
import os
import re
import yaml
from typing import Any, Dict, List, Set, Optional
from pathlib import Path
from rich.panel import Panel

from ml_research_tools.core.base_tool import BaseTool


class LocalLogsConverterTool(BaseTool):
    """Tool for converting local JSONL logs to standardized JSON format."""

    name = "local-logs-converter"
    description = "Convert raw local JSONL logs and configs to standardized experiment JSON"

    def __init__(self, services) -> None:
        """Initialize the local logs converter tool."""
        super().__init__(services)
        self.logger = logging.getLogger(__name__)

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add tool-specific arguments to the parser."""
        parser.add_argument(
            "input_dir",
            help="Base directory containing experiment run folders",
        )
        parser.add_argument(
            "--output-dir",
            "-o",
            default="converted_logs",
            help="Directory to save converted JSON files (default: converted_logs)",
        )
        parser.add_argument(
            "--quiet",
            "-q",
            action="store_true",
            help="Suppress progress bar and detailed logging",
        )
        parser.add_argument(
            "--recursive",
            "-r",
            action="store_true",
            help="Search for logs directories recursively",
        )

    def execute(self, config, args: argparse.Namespace) -> int:
        """Execute the conversion process."""
        input_dir = Path(args.input_dir).expanduser().resolve()
        output_dir = Path(args.output_dir).expanduser().resolve()

        if not input_dir.exists():
            self.logger.error(f"Input directory does not exist: {input_dir}")
            return 1

        output_dir.mkdir(parents=True, exist_ok=True)

        # Find all 'logs' directories
        log_dirs = []
        if args.recursive:
            for root, dirs, files in os.walk(input_dir):
                if "logs" in dirs:
                    log_dirs.append(Path(root) / "logs")
        else:
            # If input_dir itself is a logs dir or contains one
            if input_dir.name == "logs":
                log_dirs.append(input_dir)
            elif (input_dir / "logs").is_dir():
                log_dirs.append(input_dir / "logs")
            else:
                # Check immediate subdirectories for 'logs'
                for d in input_dir.iterdir():
                    if d.is_dir() and (d / "logs").is_dir():
                        log_dirs.append(d / "logs")

        if not log_dirs:
            self.logger.warning(f"No 'logs' directories found in {input_dir}")
            return 0

        self.logger.info(f"Found {len(log_dirs)} experiment log directories.")

        if not args.quiet:
            self.console.print(
                Panel(
                    f"🔹 Input: [cyan]{input_dir}[/cyan]\n"
                    f"🔹 Output: [green]{output_dir}[/green]\n"
                    f"🔹 Experiments found: [yellow]{len(log_dirs)}[/yellow]",
                    title="Local Logs Converter",
                    border_style="blue",
                )
            )

        processed_count = 0
        if not args.quiet:
            with self.create_progress() as progress:
                task = progress.add_task("[cyan]Converting experiments...", total=len(log_dirs))
                for log_dir in log_dirs:
                    exp_name = log_dir.parent.name
                    progress.update(task, description=f"[cyan]Processing [bold]{exp_name}[/bold]...")
                    try:
                        self.process_experiment(log_dir, output_dir)
                        processed_count += 1
                    except Exception as e:
                        self.logger.error(f"Failed to process {exp_name}: {e}")
                    progress.update(task, advance=1)
        else:
            for log_dir in log_dirs:
                try:
                    self.process_experiment(log_dir, output_dir)
                    processed_count += 1
                except Exception as e:
                    self.logger.error(f"Failed to process {log_dir}: {e}")

        self.logger.info(f"Successfully converted {processed_count} experiments to {output_dir}")
        return 0

    def process_experiment(self, log_dir: Path, output_dir: Path) -> None:
        """Process a single experiment logs directory."""
        exp_name = log_dir.parent.name
        
        # 1. Load Config
        config_data = self.load_config(log_dir)
        
        # 2. Extract Run Metadata
        run_info = self.extract_run_info(exp_name, config_data)
        
        # 3. Process JSONL metrics
        history_by_step = {}
        last_heartbeat_time = None

        # Sort files to ensure deterministic merging
        jsonl_files = sorted(list(log_dir.glob("*.jsonl")))
        
        for jsonl_file in jsonl_files:
            with open(jsonl_file, "r") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        step = entry.get("step")
                        if step is None:
                            continue
                        
                        group = entry.get("group", "train")
                        timestamp = entry.get("timestamp")
                        if timestamp:
                            last_heartbeat_time = timestamp

                        if step not in history_by_step:
                            history_by_step[step] = {"_step": step, "step": step, "iteration": step}
                        
                        # Merge metrics, prefixing if not in main metrics.jsonl or if special group
                        for k, v in entry.items():
                            if k in ["step", "group", "timestamp"]:
                                continue
                            
                            key = k
                            if group != "train" and not k.startswith(f"{group}/"):
                                key = f"{group}/{k}"
                            
                            history_by_step[step][key] = v
                    except json.JSONDecodeError:
                        self.logger.warning(f"Malformed JSON in {jsonl_file}: {line[:50]}...")

        if not history_by_step:
            history_dict = [dict()]
        else:
            history_dict = [history_by_step[s] for s in sorted(history_by_step.keys())]

        # Add metadata to history[0]
        history_dict[0]["last_heartbeat_time"] = last_heartbeat_time
        history_dict[0]["run_info"] = run_info

        # Generate output filename
        # Use a short hash or part of the name if run_id is not available
        run_id = run_info.get("id", "local")
        sanitized_name = self.sanitize_filename(exp_name)
        # To avoid collisions, if ID is generic 'local', use the full folder name
        if run_id == "local":
            filename = f"{sanitized_name}.json"
        else:
            filename = f"{sanitized_name}_{run_id}.json"
            
        filepath = output_dir / filename

        with open(filepath, "w") as f:
            json.dump(history_dict, f, indent=4, sort_keys=True)

    def load_config(self, log_dir: Path) -> Dict[str, Any]:
        """Load configuration from JSON or YAML files in the logs directory."""
        # Try finding a file that looks like a config
        config_files = list(log_dir.glob("*_config.json")) + list(log_dir.glob("*_config.yaml"))
        if not config_files:
            return {}

        # Prefer JSON if both exist
        config_file = config_files[0]
        try:
            with open(config_file, "r") as f:
                if config_file.suffix == ".json":
                    return json.load(f)
                else:
                    return yaml.safe_load(f)
        except Exception as e:
            self.logger.warning(f"Failed to load config from {config_file}: {e}")
            return {}

    def extract_run_info(self, exp_name: str, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract standardized run info from config data."""
        # Try to find run ID from the config (loggers section often has it)
        run_id = "local"
        tags = []
        notes = None
        
        # Heuristic for our specific config format
        args = config_data.get("args", {})
        if args:
            tags = args.get("tags", [])
            notes = args.get("notes")
            
        # Try to find a unique ID from loggers
        loggers = config_data.get("loggers", [])
        if isinstance(loggers, list):
            for logger in loggers:
                if logger.get("_name") in ["wandb", "mlflow"] and logger.get("id"):
                    run_id = logger.get("id")
                    break

        return {
            "id": run_id,
            "name": exp_name,
            "config": config_data,
            "tags": tags,
            "url": None,
            "state": "finished", # Assume finished for local logs
            "notes": notes,
            "summary": {}, # Will be filled from last history entry if needed
        }

    @staticmethod
    def sanitize_filename(name: str) -> str:
        """Sanitize the run name to create a valid filename."""
        return re.sub(r"[^\w\s\-\.]", "", name).strip().replace(" ", "_")