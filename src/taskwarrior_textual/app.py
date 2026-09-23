"""Textual application."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import DataTable, Footer, Header, Static

from .taskwarrior import TaskwarriorClient, TaskwarriorError


class TaskwarriorApp(App[None]):
    """Interactive Taskwarrior browser."""

    TITLE = "Taskwarrior Textual"
    SUB_TITLE = "Taskwarrior 3 frontend"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh_tasks", "Refresh"),
        ("enter", "inspect_task", "Inspect"),
    ]

    CSS = """
    #tasks { width: 2fr; }
    #details { width: 1fr; padding: 1 2; border-left: solid $primary; }
    """

    def __init__(self, client: TaskwarriorClient | None = None) -> None:
        super().__init__()
        self.client = client or TaskwarriorClient()

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield DataTable(id="tasks", cursor_type="row", zebra_stripes=True)
            yield Static("Select a task and press Enter.", id="details")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#tasks", DataTable)
        table.add_columns("UUID", "P", "Project", "Due", "Description", "Urgency")
        self.action_refresh_tasks()

    def action_refresh_tasks(self) -> None:
        """Reload pending tasks from Taskwarrior."""
        table = self.query_one("#tasks", DataTable)
        details = self.query_one("#details", Static)
        table.clear()
        try:
            tasks = self.client.pending()
        except TaskwarriorError as exc:
            details.update(f"[bold red]Taskwarrior error[/bold red]\n\n{exc}")
            return
        for task in tasks:
            table.add_row(
                task.short_uuid,
                task.priority,
                task.project,
                task.due,
                task.description,
                f"{task.urgency:.2f}",
                key=task.short_uuid,
            )
        details.update(f"{len(tasks)} pending task(s).")

    def action_inspect_task(self) -> None:
        """Show Taskwarrior information for the selected row."""
        table = self.query_one("#tasks", DataTable)
        details = self.query_one("#details", Static)
        if table.row_count == 0:
            return
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        uuid_prefix = str(row_key.value)
        try:
            information = self.client.information(uuid_prefix)
        except TaskwarriorError as exc:
            details.update(f"[bold red]Taskwarrior error[/bold red]\n\n{exc}")
            return
        details.update(information)


def run() -> None:
    """Run the Textual application."""
    TaskwarriorApp().run()
