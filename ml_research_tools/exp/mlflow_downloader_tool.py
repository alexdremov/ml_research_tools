#!/usr/bin/env python3
"""
Tool to download MLflow run logs to local JSON files.
"""

import argparse
import json
import logging
import os
import re
import threading
from typing import TYPE_CHECKING, Any, Set, List, Dict
import joblib

if TYPE_CHECKING:
    import mlflow
    from mlflow.entities import Run as MlflowRun
else:
    MlflowRun = Any

from rich.panel import Panel
from ml_research_tools.core.base_tool import BaseTool


class MLFlowDownloaderTool(BaseTool):
    """Tool for downloading MLflow run logs to local JSON files."""

    name = "mlflow-downloader"
    description = "Download runs and metrics from MLflow"

    def __init__(self, services) -> None:
        """Initialize the MLflow downloader tool."""
        super().__init__(services)
        self.logger = logging.getLogger(__name__)

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add tool-specific arguments to the parser."""
        parser.add_argument(
            "--tracking-uri",
            "-u",
            default=os.environ.get("MLFLOW_TRACKING_URI"),
            help="MLflow tracking URI. Can also use MLFLOW_TRACKING_URI env variable.",
        )

        parser.add_argument(
            "--experiment-name",
            "-e",
            default=os.environ.get("MLFLOW_EXPERIMENT_NAME"),
            help="MLflow experiment name. Can also use MLFLOW_EXPERIMENT_NAME env variable.",
        )

        parser.add_argument(
            "--experiment-id",
            "-i",
            help="MLflow experiment ID (alternative to experiment name).",
        )

        parser.add_argument(
            "--workspace",
            "-w",
            help="MLflow workspace name (e.g. for Databricks).",
        )

        parser.add_argument(
            "--output-dir",
            "-o",
            default="mlflow_logs",
            help="Directory to save log files (default: mlflow_logs)",
        )

        parser.add_argument(
            "--timeout",
            "-t",
            type=int,
            default=30,
            help="API timeout in seconds (not all MLflow backends support this)",
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

        parser.add_argument(
            "--jobs",
            "-j",
            type=int,
            default=1,
            help="Number of concurrent jobs for downloading runs (default: 4)",
        )

        parser.add_argument(
            "--metric-jobs",
            type=int,
            default=10,
            help="Number of concurrent jobs for downloading metrics within a run (default: 8)",
        )

    def download_mlflow_logs(
        self,
        tracking_uri: str,
        experiment_name: str = None,
        experiment_id: str = None,
        workspace: str = None,
        output_dir: str = "mlflow_logs",
        quiet: bool = False,
        delete_outdated: bool = True,
        jobs: int = 4,
        metric_jobs: int = 8,
        verbose: bool = False,
    ) -> int:
        """
        Download MLflow logs for a specified experiment to local JSON files.
        """
        import mlflow
        from mlflow.tracking import MlflowClient

        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)

        # Set connection pool size to handle concurrency
        # Each client (per run) uses metric_jobs threads.
        pool_size = str(jobs * metric_jobs * 2)  # heuristic for pool size
        os.environ.setdefault("MLFLOW_HTTP_POOL_SIZE", pool_size)
        os.environ.setdefault("MLFLOW_HTTP_POOL_MAXSIZE", pool_size)

        if workspace:
            if hasattr(mlflow, "set_workspace"):
                self.logger.info(f"Setting MLflow workspace: {workspace}")
                mlflow.set_workspace(workspace)
            else:
                self.logger.warning(
                    "mlflow.set_workspace is not available in this version of mlflow."
                )

        actual_tracking_uri = mlflow.get_tracking_uri()
        self.logger.info(f"Initializing MLflow Client with URI: {actual_tracking_uri}")
        client = MlflowClient(tracking_uri=actual_tracking_uri)

        # Resolve experiment ID
        if not experiment_id and experiment_name:
            exp = client.get_experiment_by_name(experiment_name)
            if exp:
                experiment_id = exp.experiment_id
            else:
                self.logger.error(f"Experiment '{experiment_name}' not found.")
                return 1
        elif not experiment_id:
            self.logger.error("Either --experiment-name or --experiment-id must be provided.")
            return 1

        # Ensure the output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Retrieve all runs from the specified experiment
        self.logger.info(f"Retrieving runs from MLflow experiment {experiment_id}...")
        try:
            # search_runs returns a list of Run objects
            runs = client.search_runs(experiment_ids=[experiment_id])
        except Exception as e:
            self.logger.exception(f"Failed to retrieve runs for experiment {experiment_id}")
            return 1

        self.logger.info(f"Found {len(runs)} runs, processing...")

        current_run_ids = set(run.info.run_id for run in runs)

        # Display summary
        if not quiet:
            self.console.print(
                Panel(
                    f"[bold]MLflow Project Summary[/bold]\n"
                    f"🔹 Tracking URI: [cyan]{actual_tracking_uri}[/cyan]\n"
                    f"🔹 Experiment ID: [green]{experiment_id}[/green]\n"
                    f"🔹 Total runs: [yellow]{len(current_run_ids)}[/yellow]\n"
                    f"🔹 Output directory: [cyan]{output_dir}[/cyan]",
                    title="MLflow Downloader",
                    border_style="blue",
                )
            )

        if delete_outdated:
            try:
                deleted_count = self.delete_outdated_logs(output_dir, current_run_ids)
                if deleted_count > 0:
                    self.logger.info(f"Deleted {deleted_count} outdated log file(s)")
            except Exception as e:
                self.logger.warning(f"Error during deletion of outdated logs: {e}")

        # Process runs concurrently
        def process_single_run(run: MlflowRun, progress_update_func=None) -> None:
            try:
                # Create a fresh client for each thread to ensure thread safety
                local_client = MlflowClient(tracking_uri=actual_tracking_uri)
                self.process_run(
                    local_client, run, output_dir, metric_jobs=metric_jobs, verbose=verbose
                )
            except Exception as e:
                self.logger.warning(f"Error processing run {run.info.run_id}: {e}")
            finally:
                if progress_update_func:
                    progress_update_func()

        if not quiet:
            with self.create_progress() as progress:
                task = progress.add_task("[cyan]Processing runs...", total=len(runs))

                def update_progress():
                    progress.update(task, advance=1)

                joblib.Parallel(n_jobs=jobs, backend="threading")(
                    joblib.delayed(process_single_run)(run, update_progress) for run in runs
                )
        else:
            joblib.Parallel(n_jobs=jobs, backend="threading")(
                joblib.delayed(process_single_run)(run) for run in runs
            )

        self.logger.info(f"Successfully downloaded {len(runs)} run(s) to {output_dir}")
        return 0

    def execute(self, config, args: argparse.Namespace) -> int:
        """Execute the MLflow log download."""
        return self.download_mlflow_logs(
            tracking_uri=args.tracking_uri,
            experiment_name=args.experiment_name,
            experiment_id=args.experiment_id,
            workspace=args.workspace,
            output_dir=args.output_dir,
            quiet=args.quiet,
            delete_outdated=not args.no_delete,
            jobs=args.jobs,
            metric_jobs=args.metric_jobs,
            verbose=args.verbose if hasattr(args, "verbose") else False,
        )

    @staticmethod
    def sanitize_filename(name: str) -> str:
        """Sanitize the run name to create a valid filename."""
        return re.sub(r"[^\w\s\-\.]", "", name).strip().replace(" ", "_")

    def delete_outdated_logs(self, output_dir: str, current_run_ids: Set[str]) -> int:
        """Delete log files that do not correspond to any current run ID (32-char)."""
        local_files = os.listdir(output_dir)
        deleted_count = 0
        for file in local_files:
            # MLflow run IDs are 32-character hex/alphanumeric strings
            match = re.match(r".*_([a-zA-Z0-9]{32})\.json$", file)
            if match:
                run_id = match.group(1)
                if run_id not in current_run_ids:
                    file_path = os.path.join(output_dir, file)
                    os.remove(file_path)
                    deleted_count += 1
                    self.logger.info(f"Deleted outdated log file: {file}")
        return deleted_count

    def process_run(
        self,
        client: Any,
        run: MlflowRun,
        output_dir: str,
        metric_jobs: int = 8,
        verbose: bool = False,
    ) -> None:
        """Process a single MLflow run and save its history to a JSON file."""
        run_id = run.info.run_id
        run_name = run.data.tags.get("mlflow.runName", run_id)
        sanitized_name = self.sanitize_filename(run_name)
        filename = f"{sanitized_name}_{run_id}.json"
        filepath = os.path.join(output_dir, filename)

        # last_heartbeat_time equivalent: use end_time or start_time
        last_update_time = run.info.end_time or run.info.start_time
        is_running = run.info.status.lower() == "running"

        # Convert MLflow tags (dict) to W&B style tags (list)
        mlflow_tags = run.data.tags
        formatted_tags = []
        for k, v in mlflow_tags.items():
            if str(v).lower() == "true":
                formatted_tags.append(k)
            else:
                formatted_tags.append(f"{k}-{v}")

        run_info = {
            "id": run_id,
            "name": run_name,
            "config": run.data.params,
            "tags": formatted_tags,
            "url": f"{client.tracking_uri}/#/experiments/{run.info.experiment_id}/runs/{run_id}",
            "state": run.info.status.lower(),
            "notes": run.data.tags.get("mlflow.note.content", ""),
            "summary": run.data.metrics,
        }

        # Check if the file already exists to avoid redundant downloads
        if os.path.exists(filepath):
            try:
                with open(filepath, "r") as f:
                    existing_data = json.load(f)
                    existing_last_update_time = existing_data[0].get("last_heartbeat_time", None)

                # Skip updating ONLY if it's NOT running and last update time hasn't changed
                if not is_running and existing_last_update_time == last_update_time:
                    existing_data[0]["run_info"] = run_info
                    with open(filepath, "w") as f:
                        json.dump(existing_data, f, indent=4, sort_keys=True)
                    return
            except (json.JSONDecodeError, IndexError, KeyError):
                pass

        # Reconstruct history
        history_by_step = {}
        metric_keys = list(run.data.metrics.keys())
        total_metrics = len(metric_keys)

        if verbose and total_metrics > 0:
            self.logger.info(f"Run {run_name} ({run_id}): Fetching {total_metrics} metrics...")

        processed_metrics = 0
        progress_lock = threading.Lock()

        def fetch_metric(metric_key: str) -> List[Any]:
            nonlocal processed_metrics
            try:
                res = client.get_metric_history(run_id, metric_key)
                if verbose:
                    with progress_lock:
                        processed_metrics += 1
                        if processed_metrics % 20 == 0 or processed_metrics == total_metrics:
                            self.logger.info(
                                f"  - [{run_id}] Progress: {processed_metrics}/{total_metrics} metrics"
                            )
                return res
            except Exception as e:
                self.logger.warning(
                    f"Failed to retrieve history for metric {metric_key} in run {run_id}: {e}"
                )
                return []

        # Fetch all metrics in parallel within the run
        # Metrics within a run are strictly IO bound
        results = joblib.Parallel(n_jobs=metric_jobs, backend="threading")(
            joblib.delayed(fetch_metric)(key) for key in metric_keys
        )

        for metric_key, metric_history in zip(metric_keys, results):
            for m in metric_history:
                step = m.step
                if step not in history_by_step:
                    history_by_step[step] = {"_step": step, "step": step, "iteration": step}
                history_by_step[step][metric_key] = m.value

        if not history_by_step:
            history_dict = [dict()]
        else:
            history_dict = [history_by_step[s] for s in sorted(history_by_step.keys())]

        # Add metadata to history[0]
        history_dict[0]["last_heartbeat_time"] = last_update_time
        history_dict[0]["run_info"] = run_info

        # Save the dictionary as a JSON file
        try:
            with open(filepath, "w") as f:
                json.dump(history_dict, f, indent=4, sort_keys=True)
        except Exception as e:
            self.logger.error(f"Failed to save log file {filepath}: {e}")
