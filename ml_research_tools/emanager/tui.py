import json
import logging

from plumbum import ProcessExecutionError
from plumbum.cmd import git
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Footer,
    Header,
    Input,
    Label,
    Markdown,
    Static,
    TabbedContent,
    TabPane,
    Tree,
)


class InputModal(ModalScreen[str]):
    CSS = """
    InputModal {
        align: center middle;
    }
    #dialog {
        padding: 1 2;
        width: 60;
        height: 11;
        border: thick $background 80%;
        background: $surface;
    }
    #help-text {
        color: $text-muted;
        margin-top: 1;
    }
    """

    def __init__(self, title: str, placeholder: str = ""):
        super().__init__()
        self.title_text = title
        self.placeholder = placeholder

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self.title_text)
            yield Input(placeholder=self.placeholder, id="modal-input")
            yield Label("Press Enter to submit, Escape to cancel", id="help-text")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


class EmanagerApp(App):
    """A Textual app to manage experiments."""

    TITLE = "ML Research Tools - Experiment Manager"

    CSS = """
    #sidebar {
        width: 30%;
        dock: left;
        border-right: solid green;
    }
    #tree-view {
        height: 1fr;
    }
    #search-input {
        margin: 1;
    }
    #detail-view {
        width: 70%;
        height: 1fr;
    }
    .scrollable {
        height: 1fr;
        overflow: auto;
    }
    """

    BINDINGS = [
        Binding("d", "toggle_dark", "Toggle dark mode"),
        Binding("c", "checkout", "Checkout branch"),
        Binding("n", "new_branch", "New branch"),
        Binding("a", "toggle_archive", "Toggle archive"),
        Binding("m", "add_note", "Add note"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, tool_instance):
        super().__init__()
        self.tool = tool_instance
        self.metadata = self.tool._read_metadata()
        self.experiments = self.metadata.get("experiments", {})
        self.current_tag = self.tool._get_current_tag()
        self.selected_tag = None
        self.search_term = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="sidebar"):
                yield Input(placeholder="Search experiments...", id="search-input")
                yield Tree("Experiments", id="tree-view")

            with Vertical(id="detail-view"):
                with TabbedContent(initial="tab-overview"):
                    with TabPane("Overview", id="tab-overview"):
                        with VerticalScroll(classes="scrollable"):
                            yield Markdown(id="experiment-markdown")
                    with TabPane("Diff (vs Parent)", id="tab-diff"):
                        with VerticalScroll(classes="scrollable"):
                            yield Static(id="experiment-diff", expand=True)
                    with TabPane("Commits", id="tab-commits"):
                        with VerticalScroll(classes="scrollable"):
                            yield Static(id="experiment-commits", expand=True)
        yield Footer()

    def on_mount(self) -> None:
        self.rebuild_tree()

    def rebuild_tree(self):
        tree = self.query_one("#tree-view", Tree)
        tree.clear()

        visible_tags = set(self.experiments.keys())
        children = {}
        roots = []
        for tag, data in self.experiments.items():
            parent = data.get("parent")
            if not parent or parent not in visible_tags:
                roots.append(tag)
            else:
                children.setdefault(parent, []).append(tag)

        def add_node(parent_node, tag):
            data = self.experiments[tag]
            label = tag

            if tag == self.current_tag:
                label = f"🟢 [bold]{label}[/bold]"

            if data.get("archived"):
                label += " (archived)"

            if data.get("sync_commits"):
                label += " 🔄"

            node_matches = self.search_term.lower() in tag.lower()
            if self.search_term:
                notes = " ".join(data.get("notes", [])).lower()
                node_matches = node_matches or (self.search_term.lower() in notes)

            def has_matching_child(t):
                if (
                    self.search_term.lower() in t.lower()
                    or self.search_term.lower()
                    in " ".join(self.experiments[t].get("notes", [])).lower()
                ):
                    return True
                return any(has_matching_child(c) for c in children.get(t, []))

            if not self.search_term or node_matches or has_matching_child(tag):
                node = parent_node.add(label, data=tag)
                if self.search_term:
                    node.expand()
                for child in sorted(children.get(tag, [])):
                    add_node(node, child)

        for root in sorted(roots):
            add_node(tree.root, root)

        if not self.search_term:
            tree.root.expand()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            self.search_term = event.value
            self.rebuild_tree()

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        tag = event.node.data
        if tag is None:
            self.selected_tag = None
            return

        self.selected_tag = tag
        self.update_detail_view(tag)

    def update_detail_view(self, tag):
        data = self.experiments.get(tag)
        if not data:
            return

        # Overview tab
        md_text = self.tool._generate_readme_text(tag, self.metadata)
        md_widget = self.query_one("#experiment-markdown", Markdown)
        md_widget.update(md_text)

        # Diff tab
        diff_text = "No parent to diff against."
        parent = data.get("parent")
        if parent:
            try:
                diff_output = git("diff", "--color", f"exp/{parent}..exp/{tag}")
                diff_text = diff_output if diff_output.strip() else "No changes."
            except ProcessExecutionError as e:
                diff_text = f"Could not compute diff:\n{e.stderr or e.stdout or str(e)}"

        diff_widget = self.query_one("#experiment-diff", Static)
        diff_widget.update(Text.from_ansi(diff_text))

        # Commits tab
        try:
            commits_output = git("log", "--color", "--oneline", "-n", "50", f"exp/{tag}")
        except ProcessExecutionError as e:
            commits_output = f"Could not get commits:\n{e.stderr or e.stdout or str(e)}"

        commits_widget = self.query_one("#experiment-commits", Static)
        commits_widget.update(Text.from_ansi(commits_output))

    def action_checkout(self) -> None:
        if self.selected_tag:
            if self.selected_tag == self.current_tag:
                self.notify("Already on this experiment")
                return
            res = self.tool._switch(self.selected_tag)
            if res == 0:
                self.current_tag = self.tool._get_current_tag()
                self.rebuild_tree()
                self.notify(f"Checked out {self.selected_tag}")
            else:
                self.notify(
                    f"Failed to checkout {self.selected_tag} (Check CLI output)", severity="error"
                )

    def action_new_branch(self) -> None:
        if not self.selected_tag:
            self.notify("Select an experiment first to branch from", severity="error")
            return

        def check_new_branch(new_tag):
            if new_tag:
                # Switch to parent first
                if self.selected_tag != self.current_tag:
                    self.tool._switch(self.selected_tag)

                res = self.tool._create(new_tag)
                if res == 0:
                    self.metadata = self.tool._read_metadata()
                    self.experiments = self.metadata.get("experiments", {})
                    self.current_tag = self.tool._get_current_tag()
                    self.rebuild_tree()
                    self.notify(f"Created and checked out {new_tag}")
                else:
                    self.notify(f"Failed to create {new_tag}", severity="error")

        self.push_screen(InputModal("Enter new experiment tag:"), check_new_branch)

    def action_toggle_archive(self) -> None:
        if self.selected_tag:
            data = self.experiments.get(self.selected_tag)
            if data:
                is_archived = data.get("archived", False)
                if is_archived:
                    self.tool._unarchive(self.selected_tag)
                else:
                    self.tool._archive(self.selected_tag)

                self.metadata = self.tool._read_metadata()
                self.experiments = self.metadata.get("experiments", {})
                self.rebuild_tree()
                self.notify(f"{'Unarchived' if is_archived else 'Archived'} {self.selected_tag}")

    def action_add_note(self) -> None:
        if not self.selected_tag:
            self.notify("Select an experiment first", severity="error")
            return

        def check_new_note(note):
            if note:
                self.tool._note(self.selected_tag, note, False)
                self.metadata = self.tool._read_metadata()
                self.experiments = self.metadata.get("experiments", {})
                self.update_detail_view(self.selected_tag)
                self.notify(f"Added note to {self.selected_tag}")

        self.push_screen(InputModal(f"Enter note for {self.selected_tag}:"), check_new_note)
