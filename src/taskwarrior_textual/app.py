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

    def __init__(self, initial_task: Task | None = None) -> None:
        super().__init__()
        self.initial_task = initial_task

    def compose(self) -> ComposeResult:
        task = self.initial_task
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
            yield Input(
                value=",".join(task.tags) if task else "",
                placeholder="Tags: comma-separated",
                id="tags",
            )
            yield Input(
                value=task.display_wait if task else "",
                placeholder="Wait: YYYY-MM-DD HH:MM, tomorrow, ...",
                id="wait",
            )
            yield Input(
                value=task.display_scheduled if task else "",
                placeholder="Scheduled: YYYY-MM-DD HH:MM, tomorrow, ...",
                id="scheduled",
            )
            yield Input(
                value=",".join(task.depends) if task else "",
                placeholder="Depends: comma-separated UUIDs or prefixes",
                id="depends",
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
                    "tags": self.query_one("#tags", Input).value.strip(),
                    "wait": self.query_one("#wait", Input).value.strip(),
                    "scheduled": self.query_one("#scheduled", Input).value.strip(),
                    "depends": self.query_one("#depends", Input).value.strip(),
                }
            )


class SearchForm(ModalScreen[str]):
    """Modal text search over the currently loaded Taskwarrior view."""

    BINDINGS = [("escape", "clear_search", "Clear search")]

    CSS = """
    SearchForm { align: center top; padding-top: 3; }
    #search-box {
        width: 70%;
        max-width: 80;
        height: auto;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    """

    def __init__(self, initial_query: str = "") -> None:
        super().__init__()
        self.initial_query = initial_query

    def compose(self) -> ComposeResult:
        with Vertical(id="search-box"):
            yield Label("Search description, project or tags")
            yield Input(
                value=self.initial_query,
                placeholder="Search…",
                id="search",
            )

    def on_mount(self) -> None:
        self.query_one("#search", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip())

    def action_clear_search(self) -> None:
        self.dismiss("")


class ProjectFilterForm(ModalScreen[str]):
    """Modal exact project filter over the currently loaded view."""

    BINDINGS = [("escape", "clear_filter", "Clear project filter")]

    CSS = """
    ProjectFilterForm { align: center top; padding-top: 3; }
    #project-filter-box {
        width: 70%;
        max-width: 80;
        height: auto;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    """

    def __init__(self, initial_project: str = "") -> None:
        super().__init__()
        self.initial_project = initial_project

    def compose(self) -> ComposeResult:
        with Vertical(id="project-filter-box"):
            yield Label("Filter by exact project")
            yield Input(
                value=self.initial_project,
                placeholder="Project (empty clears filter)",
                id="project-filter",
            )

    def on_mount(self) -> None:
        self.query_one("#project-filter", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip())

    def action_clear_filter(self) -> None:
        self.dismiss("")


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

    def __init__(self, target_task: Task) -> None:
        super().__init__()
        self.target_task = target_task

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm"):
            yield Label(f"Delete task {self.target_task.short_uuid}?")
            yield Static(self.target_task.description)
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
        ("1", "view_pending", "Pending"),
        ("2", "view_waiting", "Waiting"),
        ("3", "view_completed", "Completed"),
        ("4", "view_deleted", "Deleted"),
        ("5", "view_scheduled", "Scheduled"),
        ("/", "search_tasks", "Search"),
        ("t", "cycle_sort", "Sort"),
        ("p", "filter_project", "Project"),
        ("b", "toggle_blocked", "Blocked"),
    ]

    SORT_CYCLE = (None, "urgency", "when", "project", "priority")

    CSS = """
    #tasks { width: 2fr; }
    #details { width: 1fr; padding: 1 2; border-left: solid $primary; }
    """

    def __init__(self, client: TaskwarriorClient | None = None) -> None:
        super().__init__()
        self.client = client or TaskwarriorClient()
        self.tasks: dict[str, Task] = {}
        self.view_tasks: list[Task] = []
        self.current_view = "pending"
        self.search_query = ""
        self.project_filter = ""
        self.blocked_only = False
        self.sort_key: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield DataTable(id="tasks", cursor_type="row", zebra_stripes=True)
            yield Static("Select a task and press Enter.", id="details")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#tasks", DataTable)
        table.add_columns(
            "UUID",
            "A",
            "B",
            "P",
            "Project",
            "When",
            "Tags",
            "Description",
            "Urgency",
        )
        self.action_refresh_tasks()

    @staticmethod
    def _task_row(task: Task, view: str) -> tuple[str, ...]:
        """Render one task as a table row for the selected view."""
        if view == "waiting":
            when = task.display_wait
        elif view == "scheduled":
            when = task.display_scheduled
        elif view in {"completed", "deleted"}:
            when = task.display_end
        else:
            when = task.display_due

        return (
            task.short_uuid,
            "▶" if task.active else "",
            "◆" if task.depends else "",
            task.priority,
            task.project,
            when,
            ",".join(task.tags),
            task.description,
            f"{task.urgency:.2f}",
        )

    @staticmethod
    def _matches_search(task: Task, query: str) -> bool:
        """Match a local query against description, project and tags."""
        needle = query.casefold()
        haystack = " ".join(
            (task.description, task.project, " ".join(task.tags))
        ).casefold()
        return needle in haystack

    @staticmethod
    def _matches_project(task: Task, project: str) -> bool:
        """Match an exact project filter, case-insensitively."""
        if not project:
            return True
        return task.project.casefold() == project.casefold()

    @classmethod
    def _sort_tasks(
        cls,
        tasks: list[Task],
        sort_key: str | None,
        view: str = "pending",
    ) -> list[Task]:
        """Return tasks in the deterministic order selected by the user."""
        if sort_key is None:
            return list(tasks)
        if sort_key == "urgency":
            return sorted(tasks, key=lambda task: (-task.urgency, task.short_uuid))
        if sort_key == "when":
            def when(task: Task) -> str:
                if view == "waiting":
                    return task.display_wait
                if view == "scheduled":
                    return task.display_scheduled
                if view in {"completed", "deleted"}:
                    return task.display_end
                return task.display_due

            return sorted(
                tasks,
                key=lambda task: (not bool(when(task)), when(task), task.short_uuid),
            )
        if sort_key == "project":
            return sorted(
                tasks,
                key=lambda task: (
                    not bool(task.project),
                    task.project.casefold(),
                    task.short_uuid,
                ),
            )
        priority_rank = {"H": 0, "M": 1, "L": 2}
        return sorted(
            tasks,
            key=lambda task: (
                priority_rank.get(task.priority, 3),
                task.short_uuid,
            ),
        )

    def _render_tasks(self) -> None:
        """Render cached tasks after applying local search and sorting."""
        table = self.query_one("#tasks", DataTable)
        details = self.query_one("#details", Static)
        table.clear()
        self.tasks.clear()

        visible = [
            task
            for task in self.view_tasks
            if self._matches_search(task, self.search_query)
            and self._matches_project(task, self.project_filter)
            and (not self.blocked_only or bool(task.depends))
        ]
        visible = self._sort_tasks(visible, self.sort_key, self.current_view)

        for task in visible:
            self.tasks[task.short_uuid] = task
            table.add_row(
                *self._task_row(task, self.current_view),
                key=task.short_uuid,
            )

        state = [f"{len(visible)}/{len(self.view_tasks)} {self.current_view} task(s)"]
        if self.search_query:
            state.append(f"search={self.search_query}")
        if self.project_filter:
            state.append(f"project={self.project_filter}")
        if self.blocked_only:
            state.append("blocked")
        if self.sort_key:
            state.append(f"sort={self.sort_key}")
        details.update(" | ".join(state) + ".")

    def _apply_search(self, query: str) -> None:
        """Apply a local search without querying Taskwarrior again."""
        self.search_query = query.strip()
        self._render_tasks()

    def _apply_project_filter(self, project: str) -> None:
        """Apply an exact local project filter without refetching."""
        self.project_filter = project.strip()
        self._render_tasks()

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
        """Reload the current view, then reapply local search and sorting."""
        try:
            self.view_tasks = self.client.view(self.current_view)
        except TaskwarriorError as exc:
            self._show_error(exc)
            return
        self._render_tasks()

    def _switch_view(self, name: str) -> None:
        """Select a named view and reload its tasks."""
        self.current_view = name
        self.action_refresh_tasks()

    def action_view_pending(self) -> None:
        self._switch_view("pending")

    def action_view_waiting(self) -> None:
        self._switch_view("waiting")

    def action_view_completed(self) -> None:
        self._switch_view("completed")

    def action_view_deleted(self) -> None:
        self._switch_view("deleted")

    def action_view_scheduled(self) -> None:
        self._switch_view("scheduled")

    def action_search_tasks(self) -> None:
        """Open local text search for the current view."""
        self.push_screen(SearchForm(self.search_query), self._apply_search)

    def action_cycle_sort(self) -> None:
        """Cycle through deterministic local sort modes."""
        index = self.SORT_CYCLE.index(self.sort_key)
        self.sort_key = self.SORT_CYCLE[(index + 1) % len(self.SORT_CYCLE)]
        self._render_tasks()

    def action_filter_project(self) -> None:
        """Open an exact local project filter."""
        self.push_screen(
            ProjectFilterForm(self.project_filter),
            self._apply_project_filter,
        )

    def action_toggle_blocked(self) -> None:
        """Toggle a local filter for tasks with unresolved dependencies."""
        self.blocked_only = not self.blocked_only
        self._render_tasks()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Inspect the row activated with Enter in the task table."""
        self.action_inspect_task()

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
                self.client.modify(
                    task.short_uuid,
                    **values,
                    previous_tags=task.tags,
                )
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
