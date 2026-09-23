"""Textual application."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Static

from .models import Task
from .taskwarrior import TaskwarriorClient, TaskwarriorError


class TaskForm(ModalScreen[dict[str, str] | None]):
    """Modal form used to add or edit a task."""

    CSS = """
    TaskForm { align: center middle; }
    #form {
        width: 70%;
        max-width: 80;
        height: auto;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    #form-buttons { height: auto; margin-top: 1; }
    #form-buttons Button { margin-right: 1; }
    """

    def __init__(self, task: Task | None = None) -> None:
        super().__init__()
        self.task = task

    def compose(self) -> ComposeResult:
        task = self.task
        with Vertical(id="form"):
            yield Label("Edit task" if task else "Add task")
            yield Input(
                value=task.description if task else "",
                placeholder="Description",
                id="description",
            )
            yield Input(value=task.project if task else "", placeholder="Project", id="project")
            yield Input(
                value=task.priority if task else "",
                placeholder="Priority: H, M, L or empty",
                id="priority",
            )
            yield Input(
                value=task.display_due if task else "",
                placeholder="Due: YYYY-MM-DD, tomorrow, ...",
                id="due",
            )
            with Horizontal(id="form-buttons"):
                yield Button("Save", variant="primary", id="save")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        if event.button.id == "save":
            description = self.query_one("#description", Input).value.strip()
            if not description:
                self.query_one("#description", Input).focus()
                return
            self.dismiss(
                {
                    "description": description,
                    "project": self.query_one("#project", Input).value.strip(),
                    "priority": self.query_one("#priority", Input).value.strip().upper(),
                    "due": self.query_one("#due", Input).value.strip(),
                }
            )


class ConfirmDelete(ModalScreen[bool]):
    """Confirm deletion of a task."""

    CSS = """
    ConfirmDelete { align: center middle; }
    #confirm {
        width: 60%;
        max-width: 70;
        height: auto;
        padding: 1 2;
        border: round $error;
        background: $surface;
    }
    """

    def __init__(self, task: Task) -> None:
        super().__init__()
        self.task = task

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm"):
            yield Label(f"Delete task {self.task.short_uuid}?")
            yield Static(self.task.description)
            with Horizontal():
                yield Button("Delete", variant="error", id="delete")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "delete")


class TaskwarriorApp(App[None]):
    """Interactive Taskwarrior browser and editor."""

    TITLE = "Taskwarrior Textual"
    SUB_TITLE = "Taskwarrior 3 frontend"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh_tasks", "Refresh"),
        ("enter", "inspect_task", "Inspect"),
        ("a", "add_task", "Add"),
        ("e", "edit_task", "Edit"),
        ("s", "start_task", "Start"),
        ("x", "stop_task", "Stop"),
        ("d", "done_task", "Done"),
        ("shift+d", "delete_task", "Delete"),
        ("y", "sync_tasks", "Sync"),
    ]

    CSS = """
    #tasks { width: 2fr; }
    #details { width: 1fr; padding: 1 2; border-left: solid $primary; }
    """

    def __init__(self, client: TaskwarriorClient | None = None) -> None:
        super().__init__()
        self.client = client or TaskwarriorClient()
        self.tasks: dict[str, Task] = {}

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

    def _selected_task(self) -> Task | None:
        table = self.query_one("#tasks", DataTable)
        if table.row_count == 0:
            return None
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        return self.tasks.get(str(row_key.value))

    def _show_error(self, exc: Exception) -> None:
        self.query_one("#details", Static).update(
            f"[bold red]Taskwarrior error[/bold red]\n\n{exc}"
        )

    def _run_task_action(self, callback) -> None:
        task = self._selected_task()
        if task is None:
            return
        try:
            message = callback(task.short_uuid)
        except TaskwarriorError as exc:
            self._show_error(exc)
            return
        self.query_one("#details", Static).update(message or "Done.")
        self.action_refresh_tasks()

    def action_refresh_tasks(self) -> None:
        """Reload pending tasks from Taskwarrior."""
        table = self.query_one("#tasks", DataTable)
        details = self.query_one("#details", Static)
        table.clear()
        self.tasks.clear()
        try:
            tasks = self.client.pending()
        except TaskwarriorError as exc:
            self._show_error(exc)
            return

        for task in tasks:
            self.tasks[task.short_uuid] = task
            table.add_row(
                task.short_uuid,
                task.priority,
                task.project,
                task.display_due,
                task.description,
                f"{task.urgency:.2f}",
                key=task.short_uuid,
            )
        details.update(f"{len(tasks)} pending task(s).")

    def action_inspect_task(self) -> None:
        """Show Taskwarrior information for the selected row."""
        task = self._selected_task()
        if task is None:
            return
        try:
            information = self.client.information(task.short_uuid)
        except TaskwarriorError as exc:
            self._show_error(exc)
            return
        self.query_one("#details", Static).update(information)

    def action_add_task(self) -> None:
        """Open the add-task form."""

        def save(values: dict[str, str] | None) -> None:
            if values is None:
                return
            try:
                self.client.add(**values)
            except TaskwarriorError as exc:
                self._show_error(exc)
                return
            self.action_refresh_tasks()

        self.push_screen(TaskForm(), save)

    def action_edit_task(self) -> None:
        """Edit the selected task."""
        task = self._selected_task()
        if task is None:
            return

        def save(values: dict[str, str] | None) -> None:
            if values is None:
                return
            try:
                self.client.modify(task.short_uuid, **values)
            except TaskwarriorError as exc:
                self._show_error(exc)
                return
            self.action_refresh_tasks()

        self.push_screen(TaskForm(task), save)

    def action_start_task(self) -> None:
        self._run_task_action(self.client.start)

    def action_stop_task(self) -> None:
        self._run_task_action(self.client.stop)

    def action_done_task(self) -> None:
        self._run_task_action(self.client.done)

    def action_delete_task(self) -> None:
        task = self._selected_task()
        if task is None:
            return

        def remove(confirmed: bool) -> None:
            if not confirmed:
                return
            try:
                self.client.delete(task.short_uuid)
            except TaskwarriorError as exc:
                self._show_error(exc)
                return
            self.action_refresh_tasks()

        self.push_screen(ConfirmDelete(task), remove)

    def action_sync_tasks(self) -> None:
        try:
            message = self.client.sync()
        except TaskwarriorError as exc:
            self._show_error(exc)
            return
        self.query_one("#details", Static).update(message or "Sync complete.")
        self.action_refresh_tasks()


def run() -> None:
    """Run the Textual application."""
    TaskwarriorApp().run()
