#!/usr/bin/env python3
"""
Tool to manage experiments local files. Lean git wrapper.
Uses a hidden branch 'emanager-meta' to store experiment lineage and notes.
"""

import argparse
import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from plumbum import ProcessExecutionError
from plumbum.cmd import git
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table
from rich.tree import Tree

from ml_research_tools.core.base_tool import BaseTool

META_BRANCH = "emanager-meta"
META_FILE = "metadata.json"


class ExpManagerTool(BaseTool):
    """Tool to manage experiments local files using Git."""

    name = "emanager"
    description = "Manage local experiment files with Git-based versioning and lineage tracking"

    def __init__(self, services) -> None:
        """Initialize the experiment manager tool."""
        super().__init__(services)
        self.logger = logging.getLogger(__name__)

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add tool-specific arguments to the parser."""
        subparsers = parser.add_subparsers(dest="command", help="Experiment manager commands")

        # Init command
        subparsers.add_parser("init", help="Initialize the experiment manager in the current repo")

        # Create command
        create_parser = subparsers.add_parser(
            "create",
            help="Create a new experiment (from current experiment / branch). Does not preserve parent",
        )
        create_parser.add_argument("tag", help="Unique tag for the new experiment")

        # Clone command
        clone_parser = subparsers.add_parser(
            "clone", help="Clone an existing experiment (current by default)"
        )
        clone_parser.add_argument("dst", default=None, help="Destination experiment tag")
        clone_parser.add_argument("--src", default=None, help="Source experiment tag")

        # Switch command
        switch_parser = subparsers.add_parser("switch", help="Switch to an experiment")
        switch_parser.add_argument("tag", help="Experiment tag to switch to")

        # Diff command
        diff_parser = subparsers.add_parser("diff", help="Compare two experiments")
        diff_parser.add_argument("tag1", help="First experiment tag")
        diff_parser.add_argument(
            "tag2", nargs="?", help="Second experiment tag (defaults to current)"
        )
        diff_parser.add_argument(
            "--stat", action="store_true", help="Show only files changed instead of full diff"
        )

        # Note command
        note_parser = subparsers.add_parser("note", help="Add a note to an experiment")
        note_parser.add_argument("text", help="Note text")
        note_parser.add_argument(
            "-t", "--tag", help="Experiment tag (defaults to current experiment)"
        )
        note_parser.add_argument(
            "--amend", action="store_true", help="Overwrite the last note instead of appending"
        )

        # List command
        list_parser = subparsers.add_parser("list", help="List experiments")
        list_parser.add_argument("regexp", nargs="?", help="Optional regexp to filter tags")
        list_parser.add_argument("--notes", action="store_true", help="Include notes in the list")
        list_parser.add_argument(
            "--sort", choices=["date", "name"], default="date", help="Sort order (default: date)"
        )
        list_parser.add_argument(
            "--all", action="store_true", help="Show all experiments, including archived ones"
        )

        # Tree command
        tree_parser = subparsers.add_parser("tree", help="Display experiment lineage tree")
        tree_parser.add_argument(
            "--all", action="store_true", help="Show all experiments, including archived ones"
        )

        # Status command
        state_parser = subparsers.add_parser("status", help="Show current experiment status")
        state_parser.add_argument(
            "--simple", action="store_true", help="Simply output the current tag"
        )

        # Snapshot command
        snapshot_parser = subparsers.add_parser("snapshot", help="Save current state as a snapshot")
        snapshot_parser.add_argument(
            "message", nargs="?", default="Snapshot", help="Snapshot message"
        )

        # Take command
        take_parser = subparsers.add_parser(
            "take", help="Take files or directories from another experiment"
        )
        take_parser.add_argument("tag", help="Source experiment tag")
        take_parser.add_argument("paths", nargs="+", help="Paths to take (supports globs)")
        take_parser.add_argument(
            "--overwrite", action="store_true", help="Overwrite existing files without prompting"
        )

        # Archive command
        archive_parser = subparsers.add_parser("archive", help="Archive an experiment to hide it")
        archive_parser.add_argument("tag", help="Experiment tag to archive")

        # Unarchive command
        unarchive_parser = subparsers.add_parser("unarchive", help="Unarchive an experiment")
        unarchive_parser.add_argument("tag", help="Experiment tag to unarchive")

        # Update command
        subparsers.add_parser(
            "update", help="Update current experiment with changes from its parent"
        )

        # Clean command
        subparsers.add_parser("clean", help="Discard uncommitted changes and untracked files")

        # Export command
        export_parser = subparsers.add_parser("export", help="Export an experiment to a zip file")
        export_parser.add_argument("tag", help="Experiment tag to export")
        export_parser.add_argument(
            "output_file", nargs="?", help="Output zip file path (defaults to <tag>.zip)"
        )

        # Which command
        which_parser = subparsers.add_parser(
            "which", help="Identify the experiment tag for a given commit hash"
        )
        which_parser.add_argument(
            "commit", nargs="?", default="HEAD", help="Commit hash (defaults to HEAD)"
        )

        # Shared commands
        shared_add_parser = subparsers.add_parser(
            "shared-add", help="Register paths as globally shared"
        )
        shared_add_parser.add_argument("paths", nargs="+", help="Paths to register")

        shared_remove_parser = subparsers.add_parser(
            "shared-remove", help="Remove paths from globally shared list"
        )
        shared_remove_parser.add_argument("paths", nargs="+", help="Paths to remove")

        subparsers.add_parser("shared-list", help="List globally shared paths")

        sync_parser = subparsers.add_parser("sync", help="Sync shared paths with a base branch")
        sync_parser.add_argument(
            "base_branch",
            nargs="?",
            default="main",
            help="Base branch to sync with (defaults to main)",
        )

        subparsers.add_parser("push", help="Push all branches and metadata to the remote")

    def execute(self, config, args: argparse.Namespace) -> int:
        """Execute the experiment manager command."""
        if not self._check_git_repo():
            self.console.print("[red]Error: Not a git repository.[/red]")
            return 1

        if not args.command:
            self.console.print("[yellow]No command specified. Use --help for usage.[/yellow]")
            return 0

        # Always try to sync metadata with remote if possible before reading/modifying it
        if args.command not in ["init"]:
            self._sync_metadata()

        try:
            ret = 1
            if args.command == "init":
                ret = self._init()
            elif args.command == "create":
                ret = self._create(args.tag)
            elif args.command == "clone":
                ret = self._clone(args.src, args.dst)
            elif args.command == "switch":
                ret = self._switch(args.tag)
            elif args.command == "diff":
                ret = self._diff(args.tag1, args.tag2, getattr(args, "stat", False))
            elif args.command == "note":
                ret = self._note(args.tag, args.text, args.amend)
            elif args.command == "list":
                ret = self._list(
                    args.regexp,
                    args.notes,
                    getattr(args, "sort", "date"),
                    getattr(args, "all", False),
                )
            elif args.command == "tree":
                ret = self._tree(getattr(args, "all", False))
            elif args.command == "status":
                ret = self._status(args.simple)
            elif args.command == "snapshot":
                ret = self._snapshot(args.message)
            elif args.command == "take":
                ret = self._take(args.tag, args.paths, args.overwrite)
            elif args.command == "archive":
                ret = self._archive(args.tag)
            elif args.command == "unarchive":
                ret = self._unarchive(args.tag)
            elif args.command == "update":
                ret = self._update()
            elif args.command == "clean":
                ret = self._clean()
            elif args.command == "export":
                ret = self._export(args.tag, getattr(args, "output_file", None))
            elif args.command == "which":
                ret = self._which(args.commit)
            elif args.command == "shared-add":
                ret = self._shared_add(args.paths)
            elif args.command == "shared-remove":
                ret = self._shared_remove(args.paths)
            elif args.command == "shared-list":
                ret = self._shared_list()
            elif args.command == "sync":
                ret = self._sync(args.base_branch)
            elif args.command == "push":
                ret = self._push()
            else:
                self.console.print(f"[red]Unknown command: {args.command}[/red]")
                return 1

            if ret == 0 and args.command in [
                "init",
                "create",
                "clone",
                "switch",
                "note",
                "snapshot",
                "archive",
                "unarchive",
                "update",
                "sync",
            ]:
                self._update_readme()

            return ret
        except ProcessExecutionError as e:
            self.console.print(f"[red]Git error:[/red] {e.stderr or e.stdout or str(e)}")
            return 1
        except Exception as e:
            self.logger.exception("Unexpected error")
            self.console.print(f"[red]Error:[/red] {str(e)}")
            return 1

    # Internal Git Helpers

    def _check_git_repo(self) -> bool:
        """Check if the current directory is a git repository."""
        try:
            git("rev-parse", "--is-inside-work-tree")
            return True
        except ProcessExecutionError:
            self.logger.debug("Not inside a git work tree")
            return False

    def _has_origin(self) -> bool:
        """Check if remote 'origin' exists."""
        try:
            remotes = git("remote").strip().split("\n")
            return "origin" in remotes
        except ProcessExecutionError as e:
            self.logger.debug(f"Failed to check remotes: {e}")
            return False

    def _sync_metadata(self) -> None:
        """Sync local metadata with remote, resolving conflicts by merging dictionaries."""
        if not self._has_origin():
            return

        try:
            git("fetch", "origin", META_BRANCH)
        except ProcessExecutionError as e:
            self.logger.debug(
                f"Could not fetch metadata branch from remote. It might not exist yet: {e}"
            )
            return

        local_meta = self._read_metadata_from_ref(META_BRANCH)
        remote_meta = self._read_metadata_from_ref(f"origin/{META_BRANCH}")

        if not remote_meta or not remote_meta.get("experiments"):
            return

        if not local_meta:
            local_meta = {"experiments": {}, "shared_paths": []}

        changed = False

        # Merge shared paths
        l_shared = local_meta.get("shared_paths", [])
        r_shared = remote_meta.get("shared_paths", [])
        if r_shared:
            merged_shared = sorted(list(set(l_shared + r_shared)))
            if merged_shared != l_shared:
                local_meta["shared_paths"] = merged_shared
                changed = True

        for tag, r_data in remote_meta.get("experiments", {}).items():
            if tag not in local_meta["experiments"]:
                local_meta["experiments"][tag] = r_data
                changed = True
            else:
                l_data = local_meta["experiments"][tag]
                # Merge notes
                l_notes = l_data.get("notes", [])
                r_notes = r_data.get("notes", [])
                merged_notes = list(l_notes)
                for note in r_notes:
                    if note not in merged_notes:
                        merged_notes.append(note)
                        changed = True

                if len(merged_notes) != len(l_notes):
                    l_data["notes"] = merged_notes
                    changed = True

                # Merge archive status (if remote says it's archived, and local doesn't have it, update)
                if r_data.get("archived") and not l_data.get("archived"):
                    l_data["archived"] = True
                    changed = True

        if changed:
            self._save_metadata(local_meta, push=False)
            self.logger.info("Merged remote metadata updates.")

    def _get_current_branch(self) -> str:
        """Get the current branch name."""
        return git("rev-parse", "--abbrev-ref", "HEAD").strip()

    def _get_current_tag(self) -> Optional[str]:
        """Get the experiment tag associated with the current branch."""
        branch = self._get_current_branch()
        if branch.startswith("exp/"):
            return branch[len("exp/") :]
        return None

    def _read_metadata_from_ref(self, ref: str) -> Optional[Dict[str, Any]]:
        """Read metadata from a specific git ref without checking it out."""
        try:
            content = git("show", f"{ref}:{META_FILE}")
            return json.loads(content)
        except ProcessExecutionError as e:
            self.logger.debug(f"Could not read metadata from {ref}: {e}")
            return None

    def _read_metadata(self) -> Dict[str, Any]:
        """Read metadata from the local emanager-meta branch."""
        meta = self._read_metadata_from_ref(META_BRANCH)
        if meta is None:
            return {"experiments": {}, "shared_paths": []}
        if "shared_paths" not in meta:
            meta["shared_paths"] = []
        if "experiments" not in meta:
            meta["experiments"] = {}
        return meta

    def _save_metadata(self, metadata: Dict[str, Any], push: bool = True) -> None:
        """Save metadata to the emanager-meta branch using low-level git commands."""
        content = json.dumps(metadata, indent=2)

        blob_hash = (git["hash-object", "-w", "--stdin"] << content)().strip()
        tree_input = f"100644 blob {blob_hash}\t{META_FILE}\n"
        tree_hash = (git["mktree"] << tree_input)().strip()

        try:
            parent_hash = git("rev-parse", META_BRANCH).strip()
            commit_hash = git(
                "commit-tree",
                tree_hash,
                "-p",
                parent_hash,
                "-m",
                f"Update metadata {datetime.now()}",
            ).strip()
        except ProcessExecutionError:
            commit_hash = git(
                "commit-tree", tree_hash, "-m", f"Initialize metadata {datetime.now()}"
            ).strip()

        git("update-ref", f"refs/heads/{META_BRANCH}", commit_hash)

        if push and self._has_origin():
            try:
                git("push", "origin", META_BRANCH)
            except ProcessExecutionError as e:
                self.logger.warning(f"Failed to push metadata to origin: {e}")

    def _push_branch(self, branch: str) -> None:
        """Push a branch to origin if it exists."""
        if self._has_origin():
            try:
                git("push", "-u", "origin", branch)
            except ProcessExecutionError as e:
                self.logger.warning(f"Failed to push branch {branch} to origin: {e}")

    # Command Implementations

    def _init(self) -> int:
        """Initialize the emanager-meta branch."""
        metadata = self._read_metadata()
        if metadata.get("experiments") or metadata.get("shared_paths"):
            self.console.print("[yellow]Experiment manager already initialized.[/yellow]")
        else:
            self._save_metadata({"experiments": {}, "shared_paths": []})
            self.console.print("[green]Initialized experiment manager.[/green]")
        return 0

    def _create(self, tag: str) -> int:
        """Create a new experiment branch."""
        if not re.match(r"^[a-zA-Z0-9_\-\.]+", tag):
            self.console.print(f"[red]Invalid tag name: {tag}[/red]")
            return 1

        metadata = self._read_metadata()
        if tag in metadata["experiments"]:
            self.console.print(f"[red]Experiment tag '{tag}' already exists.[/red]")
            return 1

        branch_name = f"exp/{tag}"
        try:
            git("rev-parse", "--verify", branch_name)
            self.console.print(f"[red]Branch '{branch_name}' already exists in Git.[/red]")
            return 1
        except ProcessExecutionError as e:
            self.logger.debug(f"Expected failure finding branch {branch_name}: {e}")

        git("checkout", "-b", branch_name)

        metadata["experiments"][tag] = {
            "parent": None,
            "notes": [],
            "created_at": datetime.now().isoformat(),
            "archived": False,
        }
        self._save_metadata(metadata)
        self._push_branch(branch_name)

        self.console.print(f"[green]Created and switched to experiment [bold]{tag}[/bold].[/green]")
        return 0

    def _clone(self, src: str | None, dst: str) -> int:
        """Clone an existing experiment."""
        metadata = self._read_metadata()
        src = src or self._get_current_tag()
        if src is None:
            self.console.print(
                f"[red]Source experiment must be specified as no current experiment found.[/red]"
            )
            return 1
        if src not in metadata["experiments"]:
            self.console.print(f"[red]Source experiment '{src}' not found.[/red]")
            return 1
        if dst in metadata["experiments"]:
            self.console.print(f"[red]Destination experiment '{dst}' already exists.[/red]")
            return 1

        src_branch = f"exp/{src}"
        dst_branch = f"exp/{dst}"

        try:
            git("rev-parse", "--verify", src_branch)
        except ProcessExecutionError:
            if self._has_origin():
                try:
                    git("fetch", "origin", f"{src_branch}:{src_branch}")
                except ProcessExecutionError as e:
                    self.logger.debug(f"Failed to fetch {src_branch}: {e}")
                    self.console.print(
                        f"[red]Branch '{src_branch}' not found locally or remotely.[/red]"
                    )
                    return 1
            else:
                self.console.print(f"[red]Branch '{src_branch}' not found locally.[/red]")
                return 1

        git("checkout", "-b", dst_branch, src_branch)

        metadata["experiments"][dst] = {
            "parent": src,
            "notes": [f"Cloned from {src}"],
            "created_at": datetime.now().isoformat(),
            "archived": False,
        }
        self._save_metadata(metadata)
        self._push_branch(dst_branch)

        self.console.print(
            f"[green]Cloned [bold]{src}[/bold] to [bold]{dst}[/bold] and switched.[/green]"
        )
        return 0

    def _switch(self, tag: str) -> int:
        """Switch to an existing experiment."""
        metadata = self._read_metadata()
        if tag not in metadata["experiments"]:
            self.console.print(
                f"[yellow]Warning: Experiment '{tag}' not found in metadata.[/yellow]"
            )

        branch_name = f"exp/{tag}"
        try:
            git("checkout", branch_name)
        except ProcessExecutionError:
            if self._has_origin():
                try:
                    git("fetch", "origin", f"{branch_name}:{branch_name}")
                    git("checkout", branch_name)
                except ProcessExecutionError as e:
                    self.logger.debug(f"Failed to fetch {branch_name}: {e}")
                    self.console.print(
                        f"[red]Failed to checkout {branch_name} (locally or remotely).[/red]"
                    )
                    return 1
            else:
                self.console.print(f"[red]Failed to checkout {branch_name}.[/red]")
                return 1

        if tag not in metadata["experiments"]:
            self.console.print(f"[yellow]Tracking branch '{branch_name}' in metadata now.[/yellow]")
            metadata["experiments"][tag] = {
                "parent": None,
                "notes": ["Manually tracked after switch"],
                "created_at": datetime.now().isoformat(),
                "archived": False,
            }
            self._save_metadata(metadata)

        if self._has_origin():
            try:
                git("pull", "origin", branch_name)
            except ProcessExecutionError as e:
                self.logger.warning(f"Could not cleanly pull from origin: {e}")
                self.console.print(
                    "[yellow]Conflicts detected or could not pull automatically. Please resolve manually.[/yellow]"
                )

        self.console.print(f"[green]Switched to experiment [bold]{tag}[/bold].[/green]")
        return 0

    def _diff(self, tag1: str, tag2: Optional[str], stat: bool) -> int:
        """Diff two experiments."""
        metadata = self._read_metadata()
        if tag1 not in metadata["experiments"]:
            self.console.print(f"[red]Experiment '{tag1}' not found.[/red]")
            return 1

        target1 = f"exp/{tag1}"
        if tag2:
            if tag2 not in metadata["experiments"]:
                self.console.print(f"[red]Experiment '{tag2}' not found.[/red]")
                return 1
            target2 = f"exp/{tag2}"
        else:
            target2 = "HEAD"
            tag2 = self._get_current_tag() or "current"

        self.console.print(
            Panel(f"Comparing [bold]{tag1}[/bold] with [bold]{tag2}[/bold]", style="blue")
        )

        try:
            args = ["--color", target1, target2]
            if stat:
                args.insert(1, "--stat")
            output = git("diff", *args)
            if output.strip():
                print(output)
            else:
                self.console.print("[yellow]No differences found.[/yellow]")
        except ProcessExecutionError as e:
            self.console.print(f"[red]Failed to compute diff: {e}[/red]")
            return 1

        return 0

    def _note(self, tag: str | None, text: str, amend: bool) -> int:
        """Add or amend a note for an experiment."""
        tag = tag or self._get_current_tag()
        if not tag:
            self.console.print(
                "[red]Not currently on an experiment branch. Please specify a tag with --tag.[/red]"
            )
            return 1

        metadata = self._read_metadata()
        if tag not in metadata["experiments"]:
            self.console.print(f"[red]Experiment '{tag}' not found.[/red]")
            return 1

        if amend and metadata["experiments"][tag]["notes"]:
            metadata["experiments"][tag]["notes"][-1] = text
            msg = "Amended last note"
        else:
            metadata["experiments"][tag].setdefault("notes", []).append(text)
            msg = "Added new note"

        self._save_metadata(metadata)
        self.console.print(f"[green]{msg} for experiment [bold]{tag}[/bold].[/green]")
        return 0

    def _list(self, regexp: Optional[str], show_notes: bool, sort_by: str, show_all: bool) -> int:
        """List experiments."""
        metadata = self._read_metadata()
        experiments = metadata.get("experiments", {})

        if not experiments:
            self.console.print("[yellow]No experiments found.[/yellow]")
            return 0

        table = Table(title="Experiments")
        table.add_column("Tag", style="cyan", no_wrap=True)
        table.add_column("Parent", style="magenta")
        table.add_column("Created", style="green")
        table.add_column("Status", style="blue")
        if show_notes:
            table.add_column("Notes", style="yellow")

        pattern = re.compile(regexp) if regexp else None
        current_tag = self._get_current_tag()
        items = []

        for tag, data in experiments.items():
            if not show_all and data.get("archived", False):
                continue
            if pattern and not pattern.search(tag):
                continue
            items.append((tag, data))

        if sort_by == "date":
            items.sort(key=lambda x: x[1].get("created_at", ""), reverse=True)
        else:
            items.sort(key=lambda x: x[0])

        for tag, data in items:
            tag_display = f" {tag}" if tag != current_tag else f"*[bold]{tag}[/bold]"
            parent = data.get("parent") or "-"
            created = data.get("created_at", "")[:16].replace("T", " ")
            status = "[dim]archived[/dim]" if data.get("archived") else "active"

            row = [tag_display, parent, created, status]
            if show_notes:
                notes = "\n".join([f"- {n}" for n in data.get("notes", [])])
                row.append(notes)

            table.add_row(*row)

        self.console.print(table)
        return 0

    def _tree(self, show_all: bool) -> int:
        """Display lineage tree."""
        metadata = self._read_metadata()
        experiments = metadata.get("experiments", {})

        if not experiments:
            self.console.print("[yellow]No experiments found.[/yellow]")
            return 0

        visible_tags = set()
        for tag, data in experiments.items():
            if show_all or not data.get("archived", False):
                visible_tags.add(tag)

        children: Dict[str, List[str]] = {}
        roots: List[str] = []

        for tag in visible_tags:
            data = experiments[tag]
            parent = data.get("parent")
            if not parent or parent not in visible_tags:
                roots.append(tag)
            else:
                children.setdefault(parent, []).append(tag)

        tree = Tree("[bold blue]Experiment Lineage[/bold blue]")
        current_tag = self._get_current_tag()

        def add_node(parent_tree: Tree, tag: str) -> None:
            data = experiments[tag]
            label = tag
            if tag == current_tag:
                label = f"[bold green]{tag} (current)[/bold green]"
            if data.get("archived"):
                label += " [dim](archived)[/dim]"

            node = parent_tree.add(label)
            for child in sorted(children.get(tag, [])):
                add_node(node, child)

        for root in sorted(roots):
            add_node(tree, root)

        self.console.print(tree)
        return 0

    def _status(self, simple) -> int:
        """Show current status."""
        tag = self._get_current_tag()
        if simple:
            print(tag)
            return 0
        if not tag:
            self.console.print(f"Current branch: [yellow]{self._get_current_branch()}[/yellow]")
            self.console.print("[dim]Not currently on an experiment branch (exp/*).[/dim]")
            return 0

        metadata = self._read_metadata()
        data = metadata["experiments"].get(tag)

        if not data:
            self.console.print(f"Experiment: [bold]{tag}[/bold] [red](untracked)[/red]")
            return 0

        archived_status = " [dim](Archived)[/dim]" if data.get("archived") else ""

        self.console.print(
            Panel(
                f"Experiment: [bold cyan]{tag}[/bold cyan]{archived_status}\n"
                f"Parent: [magenta]{data.get('parent') or 'None'}[/magenta]\n"
                f"Created: [green]{data.get('created_at', '')[:19].replace('T', ' ')}[/green]\n"
                f"Notes: {len(data.get('notes', []))}",
                title="Current Experiment",
                border_style="blue",
            )
        )

        if data.get("notes"):
            self.console.print("[bold]Latest Notes:[/bold]")
            for n in data["notes"][-3:]:
                self.console.print(f" - {n}")

        return 0

    def _snapshot(self, message: str) -> int:
        """Commit all changes with a snapshot message."""
        tag = self._get_current_tag()
        full_message = f"[snapshot] {message}"
        if tag:
            full_message = f"[snapshot][{tag}] {message}"

        self.console.print(f"Creating snapshot: [dim]{full_message}[/dim]")

        status = git("status", "--porcelain").strip()
        if not status:
            self.console.print("[yellow]No changes to snapshot.[/yellow]")
            return 0

        git("add", "-A")
        git("commit", "-m", full_message)
        self.console.print("[green]Snapshot saved.[/green]")

        branch = self._get_current_branch()
        self._push_branch(branch)

        return 0

    def _take(self, tag: str, paths: List[str], overwrite: bool) -> int:
        """Take files or directories from another experiment (supports globs)."""
        metadata = self._read_metadata()
        if tag not in metadata["experiments"]:
            self.console.print(f"[red]Experiment '{tag}' not found.[/red]")
            return 1

        source_branch = f"exp/{tag}"

        try:
            git("rev-parse", "--verify", source_branch)
        except ProcessExecutionError:
            if self._has_origin():
                try:
                    git("fetch", "origin", f"{source_branch}:{source_branch}")
                except ProcessExecutionError as e:
                    self.logger.debug(f"Failed to fetch {source_branch}: {e}")
                    self.console.print(
                        f"[red]Branch '{source_branch}' not found locally or remotely.[/red]"
                    )
                    return 1
            else:
                self.console.print(f"[red]Branch '{source_branch}' not found locally.[/red]")
                return 1

        try:
            # Use git ls-tree to resolve paths/globs into exact files on the target branch
            output = git("ls-tree", "-r", "--name-only", source_branch, "--", *paths)
            matched_files = [line.strip() for line in output.strip().split("\n") if line.strip()]
        except ProcessExecutionError as e:
            self.logger.debug(f"Failed to ls-tree {source_branch}: {e}")
            matched_files = []

        if not matched_files:
            self.console.print(
                f"[yellow]No files found in '{tag}' matching the provided paths.[/yellow]"
            )
            return 0

        files_to_checkout = []
        for file_path in matched_files:
            if os.path.exists(file_path) and not overwrite:
                if not Confirm.ask(
                    f"File [yellow]{file_path}[/yellow] already exists. Overwrite?", default=False
                ):
                    self.console.print(f"Skipping [yellow]{file_path}[/yellow].")
                    continue
            files_to_checkout.append(file_path)

        if not files_to_checkout:
            self.console.print("[yellow]No files to take.[/yellow]")
            return 0

        try:
            git("checkout", source_branch, "--", *files_to_checkout)
            self.console.print(
                f"[green]Successfully took {len(files_to_checkout)} file(s) from [bold]{tag}[/bold].[/green]"
            )
        except ProcessExecutionError as e:
            self.console.print(f"[red]Failed to take files: {e.stderr or e.stdout or str(e)}[/red]")
            return 1

        return 0

    def _archive(self, tag: str) -> int:
        """Archive an experiment."""
        metadata = self._read_metadata()
        if tag not in metadata["experiments"]:
            self.console.print(f"[red]Experiment '{tag}' not found.[/red]")
            return 1

        metadata["experiments"][tag]["archived"] = True
        self._save_metadata(metadata)
        self.console.print(f"[green]Archived experiment [bold]{tag}[/bold].[/green]")
        return 0

    def _unarchive(self, tag: str) -> int:
        """Unarchive an experiment."""
        metadata = self._read_metadata()
        if tag not in metadata["experiments"]:
            self.console.print(f"[red]Experiment '{tag}' not found.[/red]")
            return 1

        metadata["experiments"][tag]["archived"] = False
        self._save_metadata(metadata)
        self.console.print(f"[green]Unarchived experiment [bold]{tag}[/bold].[/green]")
        return 0

    def _update(self) -> int:
        """Update current experiment with changes from its parent."""
        tag = self._get_current_tag()
        if not tag:
            self.console.print("[red]Not currently on an experiment branch.[/red]")
            return 1

        metadata = self._read_metadata()
        data = metadata["experiments"].get(tag)
        if not data:
            self.console.print(f"[red]Experiment '{tag}' is not tracked in metadata.[/red]")
            return 1

        parent = data.get("parent")
        if not parent:
            self.console.print("[yellow]No parent experiment recorded. Cannot update.[/yellow]")
            return 1

        parent_branch = f"exp/{parent}"
        try:
            git("rev-parse", "--verify", parent_branch)
        except ProcessExecutionError:
            if self._has_origin():
                try:
                    git("fetch", "origin", f"{parent_branch}:{parent_branch}")
                except ProcessExecutionError as e:
                    self.logger.debug(f"Failed to fetch {parent_branch}: {e}")

        self.console.print(
            f"Updating [bold]{tag}[/bold] with changes from parent [bold]{parent}[/bold]..."
        )

        status = git("status", "--porcelain").strip()
        if status:
            self.console.print(
                "[red]Working directory is not clean. Please commit or snapshot your changes first.[/red]"
            )
            return 1

        try:
            # We rebase current branch onto parent
            output = git("rebase", parent_branch)
            self.console.print(f"[green]{output.strip()}[/green]")
            self.console.print("[green]Successfully updated experiment.[/green]")
        except ProcessExecutionError as e:
            self.console.print(
                "[red]Rebase conflict! Please resolve conflicts manually, then run 'git rebase --continue'.[/red]"
            )
            return 1

        return 0

    def _clean(self) -> int:
        """Discard all uncommitted changes and untracked files."""
        status = git("status", "--porcelain").strip()
        if not status:
            self.console.print("[green]Working directory is already clean.[/green]")
            return 0

        self.console.print("[yellow]The following files will be affected:[/yellow]")
        self.console.print(status)

        if not Confirm.ask(
            "[red]This will destroy all uncommitted modifications and untracked files. Are you sure?[/red]",
            default=False,
        ):
            self.console.print("Clean cancelled.")
            return 0

        try:
            git("reset", "--hard", "HEAD")
            git("clean", "-fd")
            self.console.print("[green]Working directory cleaned.[/green]")
        except ProcessExecutionError as e:
            self.console.print(f"[red]Failed to clean: {e.stderr or e.stdout or str(e)}[/red]")
            return 1

        return 0

    def _export(self, tag: str, output_file: Optional[str]) -> int:
        """Export an experiment to a zip file."""
        metadata = self._read_metadata()
        if tag not in metadata["experiments"]:
            self.console.print(f"[red]Experiment '{tag}' not found.[/red]")
            return 1

        branch_name = f"exp/{tag}"
        try:
            git("rev-parse", "--verify", branch_name)
        except ProcessExecutionError:
            self.console.print(
                f"[red]Branch '{branch_name}' not found locally. Please fetch it first.[/red]"
            )
            return 1

        if not output_file:
            output_file = f"{tag}.zip"
        elif not output_file.endswith(".zip"):
            output_file += ".zip"

        try:
            git("archive", "--format=zip", f"--output={output_file}", branch_name)
            self.console.print(f"[green]Successfully exported {tag} to {output_file}[/green]")
        except ProcessExecutionError as e:
            self.console.print(f"[red]Failed to export: {e.stderr or e.stdout or str(e)}[/red]")
            return 1

        return 0

    def _which(self, commit: str) -> int:
        """Identify the experiment tag for a given commit hash."""
        try:
            commit_hash = git("rev-parse", "--verify", commit).strip()
        except ProcessExecutionError:
            self.console.print(f"[red]Invalid commit hash or reference: '{commit}'[/red]")
            return 1

        try:
            output = git("branch", "--contains", commit_hash)
            branches = [
                line.strip().lstrip("* ") for line in output.strip().split("\n") if line.strip()
            ]
        except ProcessExecutionError as e:
            self.console.print(
                f"[red]Failed to find branches: {e.stderr or e.stdout or str(e)}[/red]"
            )
            return 1

        exp_tags = []
        for branch in branches:
            if branch.startswith("exp/"):
                exp_tags.append(branch[len("exp/") :])

        if not exp_tags:
            self.console.print(
                f"[yellow]Commit {commit_hash[:7]} is not part of any experiment branch.[/yellow]"
            )
            return 0

        metadata = self._read_metadata()
        experiments = metadata.get("experiments", {})

        self.console.print(
            f"[green]Commit [bold]{commit_hash[:7]}[/bold] belongs to the following experiment(s):[/green]"
        )
        for tag in exp_tags:
            data = experiments.get(tag, {})
            archived = " [dim](Archived)[/dim]" if data.get("archived") else ""
            self.console.print(f"  - [bold cyan]{tag}[/bold cyan]{archived}")

        return 0

    def _shared_add(self, paths: List[str]) -> int:
        """Register paths as globally shared."""
        metadata = self._read_metadata()
        shared = set(metadata.get("shared_paths", []))
        for p in paths:
            shared.add(p)
        metadata["shared_paths"] = sorted(list(shared))
        self._save_metadata(metadata)
        self.console.print(f"[green]Added {len(paths)} path(s) to shared resources.[/green]")
        return 0

    def _shared_remove(self, paths: List[str]) -> int:
        """Remove paths from globally shared list."""
        metadata = self._read_metadata()
        shared = set(metadata.get("shared_paths", []))
        removed = 0
        for p in paths:
            if p in shared:
                shared.remove(p)
                removed += 1
        metadata["shared_paths"] = sorted(list(shared))
        self._save_metadata(metadata)
        self.console.print(f"[green]Removed {removed} path(s) from shared resources.[/green]")
        return 0

    def _shared_list(self) -> int:
        """List globally shared paths."""
        metadata = self._read_metadata()
        shared = metadata.get("shared_paths", [])
        if not shared:
            self.console.print("[yellow]No shared paths registered.[/yellow]")
            return 0
        self.console.print("[bold cyan]Shared Paths:[/bold cyan]")
        for p in shared:
            self.console.print(f"  - {p}")
        return 0

    def _sync(self, base_branch: str) -> int:
        """Sync shared paths with a base branch (two-way merge)."""
        metadata = self._read_metadata()
        shared = metadata.get("shared_paths", [])
        if not shared:
            self.console.print("[yellow]No shared paths registered to sync.[/yellow]")
            return 0

        try:
            git("rev-parse", "--verify", base_branch)
        except ProcessExecutionError:
            if self._has_origin():
                try:
                    git("fetch", "origin", f"{base_branch}:{base_branch}")
                except ProcessExecutionError:
                    self.console.print(
                        f"[red]Base branch '{base_branch}' not found locally or remotely.[/red]"
                    )
                    return 1
            else:
                self.console.print(f"[red]Base branch '{base_branch}' not found locally.[/red]")
                return 1

        current_branch = self._get_current_branch()
        if current_branch == base_branch:
            self.console.print("[red]Already on base branch.[/red]")
            return 1

        existing_paths = []
        for p in shared:
            try:
                git("ls-tree", "--name-only", base_branch, p)
                existing_paths.append(p)
                continue
            except ProcessExecutionError as e:
                self.logger.debug(f"ls-tree {base_branch} {p} failed: {e}")
            try:
                git("ls-tree", "--name-only", current_branch, p)
                existing_paths.append(p)
            except ProcessExecutionError as e:
                self.logger.debug(f"ls-tree {current_branch} {p} failed: {e}")

        if not existing_paths:
            self.console.print(f"[yellow]None of the shared paths exist in either branch.[/yellow]")
            return 0

        existing_paths = list(set(existing_paths))

        tag = self._get_current_tag()

        # Ensure metadata entry exists
        if tag and tag in metadata.get("experiments", {}):
            exp_data = metadata["experiments"][tag]
            if "sync_commits" not in exp_data:
                exp_data["sync_commits"] = {}
        else:
            exp_data = {"sync_commits": {}}

        status = git("status", "--porcelain").strip()
        if status:
            self.console.print(
                "[yellow]Working directory is not clean. Committing current changes first...[/yellow]"
            )
            git("add", "-A")
            git("commit", "-m", "[snapshot] Pre-sync auto-commit")

        try:
            # Determine the last commit we synced with from base_branch
            last_sync = exp_data["sync_commits"].get(base_branch)
            if not last_sync:
                last_sync = git("merge-base", base_branch, current_branch).strip()

            # Step 1: Pull new changes from base_branch since last_sync
            main_patch = git("diff", last_sync, base_branch, "--", *existing_paths)
            if main_patch.strip():
                try:
                    (git["apply", "--3way", "--whitespace=nowarn"] << main_patch)()
                    if git("status", "--porcelain", "--", *existing_paths).strip():
                        git("add", "--", *existing_paths)
                        git("commit", "-m", f"Sync shared resources from {base_branch}")
                        self.console.print(
                            f"[green]Successfully pulled shared path(s) from [bold]{base_branch}[/bold].[/green]"
                        )
                except ProcessExecutionError as e:
                    self.console.print(
                        f"[red]Conflicts pulling from {base_branch}! Please resolve them, commit, and run sync again.[/red]"
                    )
                    return 1
            else:
                self.console.print(
                    f"[green]No upstream changes to pull from [bold]{base_branch}[/bold].[/green]"
                )

            # Step 2: Push our fully resolved shared paths back to base_branch
            # Instead of patching, we just copy our exact shared paths over to base_branch to avoid git apply whitespace issues
            git("checkout", base_branch)
            try:
                git("checkout", current_branch, "--", *existing_paths)
                if git("status", "--porcelain", "--", *existing_paths).strip():
                    git("add", "--", *existing_paths)
                    msg = f"Update shared resources from {current_branch}"
                    if tag:
                        msg = f"Update shared resources from [{tag}]"
                    git("commit", "-m", msg)
                    self.console.print(
                        f"[green]Successfully pushed shared path(s) to [bold]{base_branch}[/bold].[/green]"
                    )
                else:
                    self.console.print(
                        f"[green]No local changes to push to [bold]{base_branch}[/bold].[/green]"
                    )

                # Update the sync pointer to the new base_branch HEAD
                new_base_commit = git("rev-parse", "HEAD").strip()
                if tag and tag in metadata.get("experiments", {}):
                    metadata["experiments"][tag]["sync_commits"][base_branch] = new_base_commit
                    self._save_metadata(metadata)

            finally:
                git("checkout", current_branch)

        except ProcessExecutionError as e:
            self.console.print(f"[red]Failed to sync: {e.stderr or e.stdout or str(e)}[/red]")
            return 1

        return 0

    def _generate_readme_text(self, tag: Optional[str], metadata: Dict[str, Any]) -> str:
        lines = []
        if tag is None:
            lines.append("## 🧪 Experiment Tracker\n")

            lines.append("### 🚀 Quick Start")
            lines.append("```bash")
            lines.append("mlrt emanager create <new-exp>  # Start a new experiment")
            lines.append("mlrt emanager switch <exp>      # Switch to an existing experiment")
            lines.append("mlrt emanager list              # List all experiments")
            lines.append("```\n")

            experiments = metadata.get("experiments", {})
            if experiments:
                lines.append("### 📊 Experiments\n")
                lines.append("| Tag | Parent | Created | Status |")
                lines.append("|---|---|---|---|")

                items = list(experiments.items())
                items.sort(key=lambda x: x[1].get("created_at", ""), reverse=True)

                for t, data in items:
                    parent = data.get("parent") or "-"
                    created = data.get("created_at", "")[:16].replace("T", " ")
                    status = "archived" if data.get("archived") else "active"
                    tag_str = f"**{t}**" if t == tag else t
                    lines.append(f"| {tag_str} | {parent} | {created} | {status} |")

                lines.append("\n### 🌳 Lineage\n")
                lines.append("```text")

                visible_tags = set(experiments.keys())
                children = {}
                roots = []
                for t in visible_tags:
                    data = experiments[t]
                    parent = data.get("parent")
                    if not parent or parent not in visible_tags:
                        roots.append(t)
                    else:
                        children.setdefault(parent, []).append(t)

                def build_tree(current_tag, prefix, is_last_child):
                    d = experiments[current_tag]
                    label = current_tag
                    if d.get("archived"):
                        label += " (archived)"

                    marker = "└── " if is_last_child else "├── "
                    lines.append(prefix + marker + label)

                    child_list = sorted(children.get(current_tag, []))
                    for i, child in enumerate(child_list):
                        new_prefix = prefix + ("    " if is_last_child else "│   ")
                        build_tree(child, new_prefix, i == len(child_list) - 1)

                for i, root in enumerate(sorted(roots)):
                    build_tree(root, "", i == len(roots) - 1)

                lines.append("```\n")

                lines.append("### 📝 Recent Activity")
                recent_notes = []
                # Find the latest note from the most recently created active experiments
                for t, data in items:
                    if not data.get("archived") and data.get("notes"):
                        recent_notes.append((t, data["notes"][-1]))
                        if len(recent_notes) >= 5:
                            break

                if recent_notes:
                    for t, note in recent_notes:
                        lines.append(f"- **{t}**: {note}")
                else:
                    lines.append("_No recent notes._")
                lines.append("\n")

            else:
                lines.append("_No experiments found._\n")

            shared_paths = metadata.get("shared_paths", [])
            if shared_paths:
                lines.append("### 🔗 Shared Resources")
                lines.append(
                    "These paths are synchronized across experiments (via `emanager sync`):"
                )
                for p in shared_paths:
                    lines.append(f"- `{p}`")
                lines.append("\n")

        else:
            data = metadata.get("experiments", {}).get(tag)
            if data:
                archived_status = " (Archived)" if data.get("archived") else ""
                lines.append(f"## 🧪 Current Experiment: `{tag}`{archived_status}\n")

                path = [tag]
                curr = data.get("parent")
                while curr and curr in metadata.get("experiments", {}):
                    path.insert(0, curr)
                    curr = metadata["experiments"][curr].get("parent")
                path.insert(0, "main")

                lines.append(f"**Lineage:** {' → '.join(f'`{p}`' for p in path)}\n")
                lines.append(f"- **Created:** {data.get('created_at', '')[:19].replace('T', ' ')}")

                syncs = data.get("sync_commits", {})
                if syncs:
                    sync_str = ", ".join(f"`{b}`" for b in syncs.keys())
                    lines.append(f"- **Synced with:** {sync_str}")
                else:
                    lines.append("- **Synced with:** _Never synced_")

                lines.append("\n### 📝 Latest Notes")
                if data.get("notes"):
                    for n in data["notes"][-5:]:
                        lines.append(f"- {n}")
                else:
                    lines.append("_No notes yet._")

                lines.append("\n### ⚡ Quick Commands")
                lines.append("```bash")
                lines.append('mlrt emanager note "my note"    # Add a note to this experiment')
                parent = data.get("parent")
                if parent:
                    lines.append(
                        f"mlrt emanager update            # Pull changes from parent ({parent})"
                    )
                if metadata.get("shared_paths"):
                    lines.append(
                        "mlrt emanager sync main         # Two-way sync shared files with main"
                    )
                lines.append("mlrt emanager snapshot          # Save current state")
                lines.append("```\n")
            else:
                lines.append(f"**Error:** Experiment '{tag}' not found in metadata.")

        return "\n".join(lines)

    def _replace_readme_section(self, content: str, new_text: str) -> str:
        if "<!-- EMANAGER_START -->" not in content:
            if content and not content.endswith("\n"):
                content += "\n"
            content += "\n<!-- EMANAGER_START -->\n<!-- EMANAGER_END -->\n"

        start_idx = content.find("<!-- EMANAGER_START -->") + len("<!-- EMANAGER_START -->")
        end_idx = content.find("<!-- EMANAGER_END -->")
        return content[:start_idx] + "\n" + new_text + "\n" + content[end_idx:]

    def _update_readme(self) -> None:
        """Update README.md in the current working directory automatically."""
        if not self._check_git_repo():
            return

        tag = self._get_current_tag()
        metadata = self._read_metadata()

        # --- 1. Update Local README.md ---
        readme_path = "README.md"
        local_content = ""
        is_dirty = False

        try:
            is_dirty = bool(git("status", "--porcelain", readme_path).strip())
        except ProcessExecutionError as e:
            self.logger.debug(f"Failed to check git status for {readme_path}: {e}")

        if os.path.exists(readme_path):
            with open(readme_path, "r", encoding="utf-8") as f:
                local_content = f.read()

        local_ansi = self._generate_readme_text(tag, metadata)
        new_local_content = self._replace_readme_section(local_content, local_ansi)

        if local_content != new_local_content:
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(new_local_content)

            if not is_dirty:
                try:
                    git("add", readme_path)
                    git("commit", "-m", "[emanager] Auto-update README.md")
                    self.console.print("[dim]Auto-updated and committed README.md.[/dim]")
                except ProcessExecutionError as e:
                    self.logger.debug(f"Failed to auto-commit local README.md: {e}")
            else:
                self.console.print(
                    "[yellow]README.md was updated with experiment data, but left uncommitted due to existing local changes.[/yellow]"
                )

        # --- 2. Update main branch README.md ---
        try:
            main_sha = git("rev-parse", "main").strip()

            try:
                main_content = git("show", "main:README.md")
            except ProcessExecutionError as e:
                self.logger.debug(f"Failed to show main:README.md: {e}")
                main_content = ""

            main_ansi = self._generate_readme_text(None, metadata)
            new_main_content = self._replace_readme_section(main_content, main_ansi)

            if main_content != new_main_content:
                blob_sha = (git["hash-object", "-w", "--stdin"] << new_main_content)().strip()

                lines = git("ls-tree", "main").strip().split("\n")
                new_lines = []
                replaced = False
                for line in lines:
                    if not line.strip():
                        continue
                    parts = line.split("\t", 1)
                    if len(parts) == 2 and parts[1] == "README.md":
                        new_lines.append(f"100644 blob {blob_sha}\tREADME.md")
                        replaced = True
                    else:
                        new_lines.append(line)

                if not replaced:
                    new_lines.append(f"100644 blob {blob_sha}\tREADME.md")

                new_tree_input = "\n".join(new_lines) + "\n"
                new_tree_sha = (git["mktree"] << new_tree_input)().strip()

                new_commit_sha = git(
                    "commit-tree",
                    new_tree_sha,
                    "-p",
                    main_sha,
                    "-m",
                    "[emanager] Auto-update README.md with global experiment data",
                ).strip()
                git("update-ref", "refs/heads/main", new_commit_sha)

                self.console.print("[dim]Auto-updated README.md on main branch.[/dim]")

        except ProcessExecutionError as e:
            self.logger.debug(f"Failed to auto-update main README.md: {e}")

    def _push(self) -> int:
        """Push all branches and metadata to the remote."""
        if not self._has_origin():
            self.console.print("[red]No remote 'origin' found. Cannot push.[/red]")
            return 1

        self.console.print("[cyan]Pushing metadata...[/cyan]")
        try:
            git("push", "origin", META_BRANCH)
        except ProcessExecutionError as e:
            self.console.print(f"[yellow]Failed to push metadata: {e}[/yellow]")

        try:
            git("push", "origin", "main")
        except ProcessExecutionError as e:
            self.console.print(f"[yellow]Failed to push main: {e}[/yellow]")

        self.console.print("[cyan]Pushing all experiment branches...[/cyan]")
        try:
            output = git("for-each-ref", "--format=%(refname:short)", "refs/heads/exp/")
            branches = [b.strip() for b in output.strip().split("\n") if b.strip()]

            if branches:
                git("push", "origin", *branches)
                self.console.print(
                    f"[green]Successfully pushed {len(branches)} experiment branch(es).[/green]"
                )
            else:
                self.console.print("[yellow]No experiment branches found to push.[/yellow]")
        except ProcessExecutionError as e:
            self.console.print(
                f"[red]Failed to push branches: {e.stderr or e.stdout or str(e)}[/red]"
            )
            return 1

        return 0
