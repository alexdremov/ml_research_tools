#!/usr/bin/env python3
"""
Kubernetes pod port forwarder tool - forwards local ports to pods matching a name pattern.
"""
import argparse
import logging
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

from rich.panel import Panel
from rich.table import Table

from ml_research_tools.core.base_tool import BaseTool


class PodForwardTool(BaseTool):
    """Tool for forwarding ports to Kubernetes pods matching a name pattern."""

    name = "kube-pod-forward"
    description = "Forward port to a Kubernetes pod with a specific name pattern."

    def __init__(self, services) -> None:
        """Initialize the tool with default values."""
        super().__init__(services)
        self.logger = logging.getLogger(__name__)

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add tool-specific arguments to the parser."""
        parser.add_argument(
            "-n",
            "--namespace",
            default="default",
            help="Kubernetes namespace (default: default)",
        )
        parser.add_argument(
            "-l",
            "--local-port",
            type=int,
            default=8080,
            help="Local port to forward (default: 8080)",
        )
        parser.add_argument(
            "-r",
            "--remote-port",
            type=int,
            default=8080,
            help="Remote port on the pod (default: 8080)",
        )
        parser.add_argument("--retries", type=int, default=5, help="Retry connections (default: 5)")
        parser.add_argument(
            "--retry-delay",
            type=int,
            default=5,
            help="Seconds to wait between retries (default: 5)",
        )
        parser.add_argument(
            "-p",
            "--pod-pattern",
            default="interactive",
            help="Pattern to match in pod name (default: interactive)",
        )

    def run_kubectl_command(self, args: List[str]) -> Tuple[bool, str, str]:
        """Run a kubectl command and return the results.

        Args:
            args: Arguments to pass to kubectl

        Returns:
            Tuple of (success, stdout, stderr)
        """
        cmd = ["kubectl"] + args
        try:
            process = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True, process.stdout, process.stderr
        except subprocess.CalledProcessError as e:
            return False, e.stdout, e.stderr
        except Exception as e:
            self.logger.error(f"Failed to execute kubectl command: {e}")
            return False, "", str(e)

    def get_running_pods(self, namespace: str) -> List[str]:
        """Get list of running pods in a namespace.

        Args:
            namespace: Kubernetes namespace

        Returns:
            List of pod names
        """
        self.logger.info(f"Getting running pods in namespace '{namespace}'")

        success, stdout, stderr = self.run_kubectl_command(
            ["-n", namespace, "get", "pods", "--field-selector=status.phase=Running", "-o", "name"]
        )

        if not success:
            self.logger.error(f"Error running kubectl: {stderr}")
            return []

        # Extract pod names from output (format: "pod/name")
        pods = []
        for line in stdout.strip().split("\n"):
            if line:
                pods.append(line.replace("pod/", ""))

        if not pods:
            self.logger.warning(f"No running pods found in namespace '{namespace}'")

        return pods

    def find_pod_by_pattern(self, namespace: str, pattern: str) -> Optional[str]:
        """Find a pod by pattern in a namespace.

        Args:
            namespace: Kubernetes namespace
            pattern: Pattern to match pod names against

        Returns:
            Matched pod name or None
        """
        pods = self.get_running_pods(namespace)

        if not pods:
            return None

        matching_pods = [pod for pod in pods if pattern in pod]

        if not matching_pods:
            return None

        if len(matching_pods) > 1:
            self.logger.warning(f"Multiple pods match pattern '{pattern}': {matching_pods}")
            self.logger.warning(f"Using the first match: {matching_pods[0]}")

        return matching_pods[0]

    def forward_port(self, namespace: str, pod_name: str, local_port: int, remote_port: int) -> int:
        """Forward a local port to the pod.

        Args:
            namespace: Kubernetes namespace
            pod_name: Name of the pod to forward to
            local_port: Local port to forward
            remote_port: Remote port on the pod

        Returns:
            0 for success, non-zero for error
        """
        try:
            # Display a formatted box with the connection details
            self.console.print(
                Panel(
                    f"[bold]Connection Details[/bold]\n"
                    f"🔹 Namespace: [cyan]{namespace}[/cyan]\n"
                    f"🔹 Pod: [green]{pod_name}[/green]\n"
                    f"🔹 Local port: [yellow]{local_port}[/yellow]\n"
                    f"🔹 Remote port: [yellow]{remote_port}[/yellow]\n\n"
                    f"[dim]Press Ctrl+C to stop forwarding[/dim]",
                    title="Port Forwarding",
                    border_style="blue",
                )
            )

            cmd = [
                "kubectl",
                "port-forward",
                "-n",
                namespace,
                f"pod/{pod_name}",
                f"{local_port}:{remote_port}",
            ]

            # Run port-forward in the foreground
            process = subprocess.Popen(cmd)

            # Wait a moment to ensure the port-forward starts
            time.sleep(1)

            # Check if process is still running
            if process.poll() is not None:
                return_code = process.returncode
                self.logger.error(
                    f"Port-forward process failed to start (exit code: {return_code})"
                )
                return return_code

            # Keep the script running until interrupted
            try:
                # Use process.poll() instead of sleep to check if process is still running
                while process.poll() is None:
                    time.sleep(1)

                # If we get here, the process terminated unexpectedly
                return_code = process.returncode
                self.logger.error(
                    f"Port-forward process terminated unexpectedly (exit code: {return_code})"
                )
                return return_code
            except KeyboardInterrupt:
                self.logger.info("Port forwarding stopped by user.")
                process.terminate()

                # Give process time to terminate gracefully
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.logger.warning("Process did not terminate gracefully, killing it...")
                    process.kill()

                return 0
        except Exception as e:
            self.logger.exception("Error during port forwarding")
            return 1

    def display_pod_table(self, all_pods: List[str], matching_pod: Optional[str] = None):
        """Display a table of available pods with the matching one highlighted.

        Args:
            all_pods: List of all pod names
            matching_pod: The pod that matches the pattern (if any)
        """
        if not all_pods:
            return

        table = Table(title="Available Pods")
        table.add_column("Pod Name", style="cyan")
        table.add_column("Status", style="green")

        for pod in all_pods:
            if pod == matching_pod:
                status = "[bold green]SELECTED[/bold green]"
            else:
                status = "[dim]running[/dim]"
            table.add_row(pod, status)

        self.console.print(table)

    def execute(self, config, args: argparse.Namespace) -> int:
        """
        Execute the port forwarding with the provided arguments.

        Args:
            args: Parsed command-line arguments

        Returns:
            Exit code (0 for success, non-zero for error)
        """
        # Find the pod
        pod_name = self.find_pod_by_pattern(args.namespace, args.pod_pattern)
        if not pod_name:
            self.display_pod_table(self.get_running_pods(args.namespace))
            self.logger.error(
                f"No running pod with '{args.pod_pattern}' in the name "
                f"found in namespace '{args.namespace}'."
            )
            return 1

        self.logger.info(f"Found pod: {pod_name}")
        self.display_pod_table(self.get_running_pods(args.namespace), pod_name)

        # Forward port with retries
        retry_count = 0
        while True:
            result = self.forward_port(
                args.namespace,
                pod_name,
                args.local_port,
                args.remote_port,
            )

            # If success or user interrupted, return the result
            if result == 0:
                return 0

            # Handle retry logic
            retry_count += 1
            if retry_count > args.retries:
                self.logger.error(f"Max retries reached ({args.retries}). Exiting.")
                return result

            # Calculate time remaining for retry
            remaining = args.retry_delay
            self.logger.info(f"Retrying ({retry_count}/{args.retries}) in {remaining} seconds...")

            # Show a countdown
            with self.create_progress() as progress:
                task = progress.add_task(f"[cyan]Retrying in...", total=args.retry_delay)
                for i in range(args.retry_delay):
                    time.sleep(1)
                    progress.update(task, advance=1)

            # Re-check pod in case it changed
            pod_name = self.find_pod_by_pattern(args.namespace, args.pod_pattern)
            if not pod_name:
                self.logger.error(
                    f"No running pod with '{args.pod_pattern}' in the name "
                    f"found in namespace '{args.namespace}'"
                )
                return 1
