"""Textual application."""

from __future__ import annotations

from datetime import UTC, datetime

from typing import ClassVar

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Static

from .config import PlanningSettings, WorkingCalendar
from .models import Task
from .planning import (
    build_absolute_schedule,
    build_planning_graph,
    build_relative_schedule,
    parse_taskwarrior_datetime,
    remaining_estimate_hours,
)
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
            yield Input(
                value=str(task.estimate_hours) if task and task.has_estimate else "",
                placeholder="Estimate (hours; 0 = milestone)",
                id="estimate",
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
                    "estimate": self.query_one("#estimate", Input).value.strip(),
                }
            )


class SearchForm(ModalScreen[str]):
    """Modal text search over the currently loaded Taskwarrior view."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [("escape", "clear_search", "Clear search")]

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


class TagFilterForm(ModalScreen[str]):
    """Modal exact tag filter over the currently loaded view."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [("escape", "clear_filter", "Clear tag filter")]

    CSS = """
    TagFilterForm { align: center top; padding-top: 3; }
    #tag-filter-box {
        width: 70%;
        max-width: 80;
        height: auto;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    """

    def __init__(self, initial_tag: str = "") -> None:
        super().__init__()
        self.initial_tag = initial_tag

    def compose(self) -> ComposeResult:
        with Vertical(id="tag-filter-box"):
            yield Label("Filter by exact tag")
            yield Input(
                value=self.initial_tag,
                placeholder="Tag (empty clears filter)",
                id="tag-filter",
            )

    def on_mount(self) -> None:
        self.query_one("#tag-filter", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip())

    def action_clear_filter(self) -> None:
        self.dismiss("")


class ProjectFilterForm(ModalScreen[str]):
    """Modal exact project filter over the currently loaded view."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [("escape", "clear_filter", "Clear project filter")]

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


class MilestonesScreen(ModalScreen[None]):
    """Read-only explicit milestone overview."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [("escape", "close", "Close")]

    CSS = """
    MilestonesScreen { align: center middle; }
    #milestones-box {
        width: 80%;
        max-width: 100;
        height: auto;
        max-height: 85%;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    """

    def __init__(self, body: str) -> None:
        super().__init__()
        self.body = body

    def compose(self) -> ComposeResult:
        with Vertical(id="milestones-box"):
            yield Label("Milestones")
            yield Static(self.body, id="milestones-body")

    def action_close(self) -> None:
        self.dismiss(None)


class ConstraintsScreen(ModalScreen[None]):
    """Read-only scheduling constraint overview."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [("escape", "close", "Close")]

    CSS = """
    ConstraintsScreen { align: center middle; }
    #constraints-box {
        width: 94%;
        max-width: 135;
        height: auto;
        max-height: 90%;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    """

    def __init__(self, body: str) -> None:
        super().__init__()
        self.body = body

    def compose(self) -> ComposeResult:
        with Vertical(id="constraints-box"):
            yield Label("Scheduling constraints")
            yield Static(self.body, id="constraints-body")

    def action_close(self) -> None:
        self.dismiss(None)


class CalendarPlanScreen(ModalScreen[None]):
    """Read-only calendar planning view for the current task graph."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [("escape", "close", "Close")]

    CSS = """
    CalendarPlanScreen { align: center middle; }
    #calendar-plan-box {
        width: 94%;
        max-width: 135;
        height: auto;
        max-height: 90%;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    """

    def __init__(self, body: str) -> None:
        super().__init__()
        self.body = body

    def compose(self) -> ComposeResult:
        with Vertical(id="calendar-plan-box"):
            yield Label("Calendar plan")
            yield Static(self.body, id="calendar-plan-body")

    def action_close(self) -> None:
        self.dismiss(None)


class GanttScreen(ModalScreen[None]):
    """Read-only local Gantt-like planning view."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [("escape", "close", "Close")]

    CSS = """
    GanttScreen { align: center middle; }
    #gantt-box {
        width: 92%;
        max-width: 130;
        height: auto;
        max-height: 90%;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    """

    def __init__(self, body: str) -> None:
        super().__init__()
        self.body = body

    def compose(self) -> ComposeResult:
        with Vertical(id="gantt-box"):
            yield Label("Gantt planning")
            yield Static(self.body, id="gantt-body")

    def action_close(self) -> None:
        self.dismiss(None)


class CriticalPathScreen(ModalScreen[None]):
    """Read-only critical-path analysis for the current view."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [("escape", "close", "Close")]

    CSS = """
    CriticalPathScreen { align: center middle; }
    #critical-path-box {
        width: 90%;
        max-width: 120;
        height: auto;
        max-height: 90%;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    """

    def __init__(self, body: str) -> None:
        super().__init__()
        self.body = body

    def compose(self) -> ComposeResult:
        with Vertical(id="critical-path-box"):
            yield Label("Critical path")
            yield Static(self.body, id="critical-path-body")

    def action_close(self) -> None:
        self.dismiss(None)


class DependencyOverviewScreen(ModalScreen[None]):
    """Read-only dependency graph overview for the current view."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [("escape", "close", "Close")]

    CSS = """
    DependencyOverviewScreen { align: center middle; }
    #dependency-overview-box {
        width: 85%;
        max-width: 110;
        height: auto;
        max-height: 85%;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    """

    def __init__(self, body: str) -> None:
        super().__init__()
        self.body = body

    def compose(self) -> ComposeResult:
        with Vertical(id="dependency-overview-box"):
            yield Label("Dependency graph overview")
            yield Static(self.body, id="dependency-overview-body")

    def action_close(self) -> None:
        self.dismiss(None)


class DependencyScreen(ModalScreen[None]):
    """Read-only local dependency neighborhood for one task."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [("escape", "close", "Close")]

    CSS = """
    DependencyScreen { align: center middle; }
    #dependency-box {
        width: 70%;
        max-width: 90;
        height: auto;
        max-height: 80%;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    """

    def __init__(self, title: str, body: str) -> None:
        super().__init__()
        self.title = title
        self.body = body

    def compose(self) -> ComposeResult:
        with Vertical(id="dependency-box"):
            yield Label(self.title)
            yield Static(self.body, id="dependency-body")

    def action_close(self) -> None:
        self.dismiss(None)


class ProjectOverviewScreen(ModalScreen[None]):
    """Read-only local project summary for the current view."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [("escape", "close", "Close")]

    CSS = """
    ProjectOverviewScreen { align: center middle; }
    #project-overview-box {
        width: 80%;
        max-width: 100;
        height: auto;
        max-height: 80%;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    """

    def __init__(self, body: str) -> None:
        super().__init__()
        self.body = body

    def compose(self) -> ComposeResult:
        with Vertical(id="project-overview-box"):
            yield Label("Project overview")
            yield Static(self.body, id="project-overview-body")

    def action_close(self) -> None:
        self.dismiss(None)


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

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
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
        ("g", "show_dependencies", "Dependencies"),
        ("shift+g", "show_dependency_overview", "Dependency graph"),
        ("shift+c", "show_critical_path", "Critical path"),
        ("shift+h", "show_gantt", "Gantt"),
        ("shift+l", "show_calendar_plan", "Calendar"),
        ("shift+k", "show_constraints", "Constraints"),
        ("shift+m", "show_milestones", "Milestones"),
        ("shift+p", "show_project_overview", "Projects"),
        ("f", "filter_tag", "Tag"),
        ("v", "toggle_active", "Active"),
        ("c", "clear_local_state", "Clear"),
    ]

    SORT_CYCLE = (None, "urgency", "when", "project", "priority")

    CSS = """
    #tasks { width: 2fr; }
    #details { width: 1fr; padding: 1 2; border-left: solid $primary; }
    """

    def __init__(
        self,
        client: TaskwarriorClient | None = None,
        planning_settings: PlanningSettings | None = None,
    ) -> None:
        super().__init__()
        self.client = client or TaskwarriorClient()
        self.planning_settings = planning_settings or PlanningSettings()
        self.tasks: dict[str, Task] = {}
        self.view_tasks: list[Task] = []
        self.current_view = "pending"
        self.search_query = ""
        self.project_filter = ""
        self.tag_filter = ""
        self.blocked_only = False
        self.active_only = False
        self.sort_key: str | None = None
        self.tracked_hours: dict[str, float] = {}
        self.tracking_now = datetime.now(UTC)

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
            "Estimate",
            "Tracked",
            "Remaining",
            "Urgency",
        )
        self.action_refresh_tasks()

    @staticmethod
    def _task_row(
        task: Task,
        view: str,
        settings: PlanningSettings | None = None,
        *,
        now: datetime | None = None,
        tracked_hours: dict[str, float] | None = None,
    ) -> tuple[str, ...]:
        """Render one task as a table row for the selected view."""
        if view == "waiting":
            when = task.display_wait
        elif view == "scheduled":
            when = task.display_scheduled
        elif view in {"completed", "deleted"}:
            when = task.display_end
        else:
            when = task.display_due

        resolved_settings = settings or PlanningSettings()
        resolved_now = now or datetime.now(UTC)
        tracked = (
            tracked_hours[task.uuid]
            if tracked_hours is not None and task.uuid in tracked_hours
            else None
        )
        remaining = remaining_estimate_hours(
            task,
            WorkingCalendar(resolved_settings),
            resolved_now,
            tracked_hours,
        )

        return (
            task.short_uuid,
            "▶" if task.active else "",
            "◆" if task.depends else "",
            task.priority,
            task.project,
            when,
            ",".join(task.tags),
            task.description,
            task.display_estimate,
            "" if tracked is None else f"{tracked:.2f}h",
            f"{remaining:.2f}h" if task.has_estimate else "",
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

    @staticmethod
    def _matches_tag(task: Task, tag: str) -> bool:
        """Match an exact tag filter, case-insensitively."""
        if not tag:
            return True
        needle = tag.casefold()
        return any(candidate.casefold() == needle for candidate in task.tags)

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
            return sorted(tasks, key=lambda task: (-task.urgency, task.short_uuid, task.uuid))
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
                key=lambda task: (
                    not bool(when(task)),
                    when(task),
                    task.short_uuid,
                    task.uuid,
                ),
            )
        if sort_key == "project":
            return sorted(
                tasks,
                key=lambda task: (
                    not bool(task.project),
                    task.project.casefold(),
                    task.short_uuid,
                    task.uuid,
                ),
            )
        priority_rank = {"H": 0, "M": 1, "L": 2}
        return sorted(
            tasks,
            key=lambda task: (
                priority_rank.get(task.priority, 3),
                task.short_uuid,
                task.uuid,
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
            and self._matches_tag(task, self.tag_filter)
            and (not self.blocked_only or bool(task.depends))
            and (not self.active_only or task.active)
        ]
        visible = self._sort_tasks(visible, self.sort_key, self.current_view)

        for task in visible:
            self.tasks[task.short_uuid] = task
            table.add_row(
                *self._task_row(
                    task,
                    self.current_view,
                    self.planning_settings,
                    now=self.tracking_now,
                    tracked_hours=self.tracked_hours,
                ),
                key=task.short_uuid,
            )

        state = [f"{len(visible)}/{len(self.view_tasks)} {self.current_view} task(s)"]
        if self.search_query:
            state.append(f"search={self.search_query}")
        if self.project_filter:
            state.append(f"project={self.project_filter}")
        if self.tag_filter:
            state.append(f"tag={self.tag_filter}")
        if self.blocked_only:
            state.append("blocked")
        if self.active_only:
            state.append("active")
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

    def _apply_tag_filter(self, tag: str) -> None:
        """Apply an exact local tag filter without refetching."""
        self.tag_filter = tag.strip()
        self._render_tasks()

    @staticmethod
    def _dependency_summary(task: Task, tasks: list[Task]) -> str:
        """Describe dependency links that can be resolved from the current view."""
        by_uuid = {candidate.uuid: candidate for candidate in tasks}
        depends_on: list[str] = []
        for dependency in task.depends:
            known = by_uuid.get(dependency)
            if known is None:
                depends_on.append(dependency[:8])
            else:
                depends_on.append(f"{known.short_uuid} {known.description}")

        required_by = [
            f"{candidate.short_uuid} {candidate.description}"
            for candidate in tasks
            if task.uuid in candidate.depends
        ]

        sections: list[str] = []
        if depends_on:
            sections.append("Depends on\n" + "\n".join(depends_on))
        if required_by:
            sections.append("Required by\n" + "\n".join(required_by))
        if not sections:
            return "No dependencies in current view."
        return "\n\n".join(sections)

    @staticmethod
    def _dependency_overview(tasks: list[Task]) -> str:
        """Summarize the resolved dependency graph for the current view."""
        if not tasks:
            return "No tasks in current view."

        graph = build_planning_graph(tasks)
        by_uuid = graph.by_uuid
        dependencies = graph.dependencies
        unresolved = graph.unresolved

        remaining = set(by_uuid)
        layers: list[list[str]] = []
        while remaining:
            ready = sorted(
                (
                    uuid
                    for uuid in remaining
                    if not (dependencies[uuid] & remaining)
                ),
                key=lambda uuid: (by_uuid[uuid].short_uuid, uuid),
            )
            if not ready:
                break
            layers.append(ready)
            remaining.difference_update(ready)

        cycle_nodes = graph.cycle_nodes
        blocked_by_cycle = graph.blocked_by_cycle
        resolved_edges = sum(len(values) for values in dependencies.values())
        lines = [
            (f"Tasks: {len(tasks)} | Resolved edges: {resolved_edges} | "
            f"Unresolved: {len(unresolved)}")
        ]

        for index, layer in enumerate(layers):
            rendered = "; ".join(
                f"{by_uuid[uuid].short_uuid} {by_uuid[uuid].description}"
                for uuid in layer
            )
            lines.append(f"Layer {index}: {rendered}")

        if cycle_nodes:
            rendered = "; ".join(
                f"{by_uuid[uuid].short_uuid} {by_uuid[uuid].description}"
                for uuid in sorted(cycle_nodes, key=lambda item: (by_uuid[item].short_uuid, item))
            )
            lines.append(f"Cycle detected among: {rendered}")

        if blocked_by_cycle:
            rendered = "; ".join(
                f"{by_uuid[uuid].short_uuid} {by_uuid[uuid].description}"
                for uuid in sorted(
                    blocked_by_cycle,
                    key=lambda item: (by_uuid[item].short_uuid, item),
                )
            )
            lines.append(f"Blocked by cycle: {rendered}")

        if unresolved:
            lines.append("Unresolved dependencies")
            lines.extend(
                f"{task_uuid} -> {dependency_uuid}"
                for task_uuid, dependency_uuid in sorted(unresolved)
            )

        return "\n".join(lines)

    @staticmethod
    def _critical_path_summary(
        tasks: list[Task],
        settings: PlanningSettings | None = None,
        *,
        now: datetime | None = None,
        tracked_hours: dict[str, float] | None = None,
    ) -> str:
        """Compute a CPM schedule from resolved dependencies and estimates."""
        if not tasks:
            return "No tasks in current view."

        graph = build_planning_graph(tasks)
        if graph.cyclic:
            return "Critical path unavailable: dependency cycle detected."
        by_uuid = graph.by_uuid
        dependencies = graph.dependencies
        unresolved = graph.unresolved
        order = list(graph.order)

        schedule = build_relative_schedule(
            graph,
            settings,
            now=now,
            tracked_hours=tracked_hours,
        )
        assert schedule is not None
        earliest_start = schedule.earliest_start
        earliest_finish = schedule.earliest_finish
        project_duration = schedule.duration
        slack = schedule.slack
        critical = schedule.critical

        terminal = min(
            (
                uuid
                for uuid in order
                if abs(earliest_finish[uuid] - project_duration) < 1e-9
            ),
            key=lambda uuid: (by_uuid[uuid].short_uuid, uuid),
        )
        path = [terminal]
        current = terminal
        while dependencies[current]:
            candidates = sorted(
                (
                    dependency
                    for dependency in dependencies[current]
                    if dependency in critical
                    and abs(
                        earliest_finish[dependency] - earliest_start[current]
                    ) < 1e-9
                ),
                key=lambda uuid: (by_uuid[uuid].short_uuid, uuid),
            )
            current = candidates[0]
            path.append(current)
        path.reverse()

        lines = [
            f"Project duration: {project_duration:.2f}h",
            "Critical path: "
            + " -> ".join(by_uuid[uuid].short_uuid for uuid in path),
            "",
            "UUID | Estimate | ES | EF | Slack | Critical | Kind",
        ]
        for uuid in sorted(order, key=lambda item: (by_uuid[item].short_uuid, item)):
            task = by_uuid[uuid]
            lines.append(
                f"{task.short_uuid} | {task.display_estimate or '0.00h'} | "
                f"{earliest_start[uuid]:.2f} | {earliest_finish[uuid]:.2f} | "
                f"{slack[uuid]:.2f} | {'yes' if uuid in critical else 'no'} | "
                f"{'milestone' if task.is_milestone else 'task'}"
            )

        absolute = build_absolute_schedule(
            graph,
            settings,
            now=now,
            tracked_hours=tracked_hours,
        )
        if absolute is not None:
            deadline_rows = [
                uuid
                for uuid in order
                if uuid in absolute.due_slack
            ]
            if deadline_rows:
                lines.extend(
                    [
                        "",
                        "Deadline pressure",
                        (
                            "UUID | Due | Planned finish | Deadline slack | "
                            "CPM critical | Kind"
                        ),
                    ]
                )
                for uuid in sorted(
                    deadline_rows,
                    key=lambda item: (by_uuid[item].short_uuid, item),
                ):
                    task = by_uuid[uuid]
                    lines.append(
                        f"{task.short_uuid} | {task.display_due} | "
                        f"{absolute.finishes[uuid]:%Y-%m-%d %H:%M} | "
                        f"{absolute.due_slack[uuid]:+.2f}h | "
                        f"{'yes' if uuid in critical else 'no'} | "
                        f"{'milestone' if task.is_milestone else 'task'}"
                    )

        unestimated = sorted(
            task.short_uuid for task in tasks if not task.has_estimate
        )
        if unestimated:
            lines.extend(
                ["", "Unestimated tasks treated as 0h: " + ", ".join(unestimated)]
            )

        if unresolved:
            rendered = "; ".join(
                f"{task_uuid} -> {dependency_uuid}"
                for task_uuid, dependency_uuid in sorted(unresolved)
            )
            lines.extend(["", "Unresolved dependencies ignored: " + rendered])

        return "\n".join(lines)

    @staticmethod
    def _gantt_summary(
        tasks: list[Task],
        settings: PlanningSettings | None = None,
        *,
        now: datetime | None = None,
        tracked_hours: dict[str, float] | None = None,
    ) -> str:
        """Render an earliest-start dependency schedule as a compact ASCII Gantt."""
        if not tasks:
            return "No tasks in current view."

        graph = build_planning_graph(tasks)
        if graph.cyclic:
            return "Gantt unavailable: dependency cycle detected."
        by_uuid = graph.by_uuid
        unresolved = graph.unresolved
        order = list(graph.order)

        schedule = build_relative_schedule(
            graph,
            settings,
            now=now,
            tracked_hours=tracked_hours,
        )
        assert schedule is not None
        earliest_start = schedule.earliest_start
        earliest_finish = schedule.earliest_finish
        project_duration = schedule.duration
        critical = schedule.critical
        lines = [
            f"Scale: 1 char = 1h | Project duration: {project_duration:.2f}h",
            "Critical marker: *",
        ]

        for uuid in sorted(
            order,
            key=lambda item: (
                earliest_start[item],
                by_uuid[item].short_uuid,
                item,
            ),
        ):
            task = by_uuid[uuid]
            offset = round(earliest_start[uuid])
            if task.is_milestone:
                bar = " " * offset + "◆"
            elif not task.has_estimate:
                bar = " " * offset + "·"
            else:
                width = max(
                    1,
                    round(earliest_finish[uuid] - earliest_start[uuid]),
                )
                bar = " " * offset + "█" * width
            marker = "*" if uuid in critical else " "
            lines.append(
                f"{task.short_uuid} | {marker} | {earliest_start[uuid]:.2f}-"
                f"{earliest_finish[uuid]:.2f}h | {bar} | {task.description}"
            )

        unestimated = sorted(
            task.short_uuid for task in tasks if not task.has_estimate
        )
        if unestimated:
            lines.extend(
                ["", "Unestimated tasks shown as ·: " + ", ".join(unestimated)]
            )

        if unresolved:
            rendered = "; ".join(
                f"{task_uuid} -> {dependency_uuid}"
                for task_uuid, dependency_uuid in sorted(unresolved)
            )
            lines.extend(["", "Unresolved dependencies ignored: " + rendered])

        return "\n".join(lines)

    @staticmethod
    def _planning_datetime(value: str):
        """Parse a Taskwarrior UTC timestamp for local planning calculations."""
        return parse_taskwarrior_datetime(value)

    @classmethod
    def _calendar_plan(
        cls,
        tasks: list[Task],
        settings: PlanningSettings | None = None,
        *,
        now: datetime | None = None,
        tracked_hours: dict[str, float] | None = None,
    ) -> str:
        """Build an absolute UTC schedule from dependencies and scheduled dates."""
        if not tasks:
            return "No tasks in current view."

        graph = build_planning_graph(tasks)
        if graph.cyclic:
            return "Calendar plan unavailable: dependency cycle detected."

        schedule = build_absolute_schedule(
            graph,
            settings,
            now=now,
            tracked_hours=tracked_hours,
        )
        if schedule is None:
            return "Calendar plan unavailable: no valid scheduled date in current view."

        by_uuid = graph.by_uuid
        unresolved = graph.unresolved
        order = list(graph.order)
        starts = schedule.starts
        finishes = schedule.finishes
        late_by = schedule.late_by
        invalid_due = schedule.invalid_due
        invalid_scheduled = schedule.invalid_scheduled
        project_finish = max(finishes.values())

        lines = [
            (f"Calendar origin: {schedule.origin:%Y-%m-%d %H:%M} UTC | "
            f"Project finish: {project_finish:%Y-%m-%d %H:%M} UTC"),
            f"Late tasks: {len(late_by)}",
            "",
            "UUID | Start -> Finish | Due | Status | Description",
        ]

        scheduled_order = [uuid for uuid in order if uuid in starts]
        for uuid in sorted(
            scheduled_order,
            key=lambda item: (starts[item], by_uuid[item].short_uuid, item),
        ):
            task = by_uuid[uuid]
            due = cls._planning_datetime(task.due)
            if due is None:
                due_text = task.display_due if task.due else "-"
                status = "-"
            else:
                due_text = task.display_due
                status = (
                    f"LATE +{late_by[uuid]:.2f}h"
                    if uuid in late_by
                    else "on time"
                )
            lines.append(
                f"{task.short_uuid} | {starts[uuid]:%Y-%m-%d %H:%M} -> "
                f"{finishes[uuid]:%Y-%m-%d %H:%M} | {due_text} | "
                f"{status} | {task.description}"
            )

        unestimated = sorted(
            task.short_uuid for task in tasks if not task.has_estimate
        )
        if unestimated:
            lines.extend(
                ["", "Unestimated tasks treated as 0h: " + ", ".join(unestimated)]
            )

        if unresolved:
            rendered = "; ".join(
                f"{task_uuid} -> {dependency_uuid}"
                for task_uuid, dependency_uuid in unresolved
            )
            lines.extend(["", "Unresolved dependencies ignored: " + rendered])

        if invalid_due:
            lines.extend(["", "Invalid due dates ignored: " + ", ".join(invalid_due)])

        if invalid_scheduled:
            lines.extend(
                ["", "Invalid scheduled dates ignored: " + ", ".join(invalid_scheduled)]
            )

        return "\n".join(lines)

    @staticmethod
    def _milestones_summary(tasks: list[Task]) -> str:
        """Summarize explicit zero-duration milestones in the current view."""
        if not tasks:
            return "No tasks in current view."

        milestones = sorted(
            (task for task in tasks if task.is_milestone),
            key=lambda task: (task.short_uuid, task.uuid),
        )
        if not milestones:
            return "No explicit zero-duration milestones in current view."

        lines = [f"Milestones: {len(milestones)}", "", "UUID | When | Description"]
        for task in milestones:
            when = task.display_due or task.display_scheduled or "-"
            lines.append(f"{task.short_uuid} | {when} | {task.description}")
        return "\n".join(lines)

    @classmethod
    def _constraints_summary(
        cls,
        tasks: list[Task],
        settings: PlanningSettings | None = None,
        *,
        now: datetime | None = None,
        tracked_hours: dict[str, float] | None = None,
    ) -> str:
        """Summarize scheduled and due constraints in the current view."""
        if not tasks:
            return "No tasks in current view."

        constrained = [task for task in tasks if task.scheduled or task.due]
        if not constrained:
            return "No scheduled or due constraints in current view."

        graph = build_planning_graph(tasks)
        schedule = (
            None
            if graph.cyclic
            else build_absolute_schedule(
                graph,
                settings,
                now=now,
                tracked_hours=tracked_hours,
            )
        )
        scheduled_count = sum(bool(task.scheduled) for task in constrained)
        due_count = sum(bool(task.due) for task in constrained)

        lines = [
            (f"Constraints: {len(constrained)} | Scheduled: {scheduled_count} | "
            f"Due: {due_count}"),
            "",
            "UUID | Scheduled | Due | Planned finish | Status | Description",
        ]

        for task in sorted(constrained, key=lambda item: (item.short_uuid, item.uuid)):
            scheduled_value = cls._planning_datetime(task.scheduled)
            due_value = cls._planning_datetime(task.due)
            scheduled_text = task.display_scheduled if task.scheduled else "-"
            due_text = task.display_due if task.due else "-"
            planned_finish = "-"

            if task.scheduled and scheduled_value is None:
                status = "invalid scheduled"
            elif task.due and due_value is None:
                status = "invalid due"
            elif graph.cyclic:
                status = "cycle"
            elif schedule is None:
                status = "deadline"
            else:
                planned_finish = f"{schedule.finishes[task.uuid]:%Y-%m-%d %H:%M}"
                if task.due:
                    status = (
                        f"LATE +{schedule.late_by[task.uuid]:.2f}h"
                        if task.uuid in schedule.late_by
                        else "on time"
                    )
                else:
                    status = "scheduled"

            lines.append(
                f"{task.short_uuid} | {scheduled_text} | {due_text} | "
                f"{planned_finish} | {status} | {task.description}"
            )

        return "\n".join(lines)

    @staticmethod
    def _project_overview(
        tasks: list[Task],
        settings: PlanningSettings | None = None,
        *,
        now: datetime | None = None,
        tracked_hours: dict[str, float] | None = None,
    ) -> str:
        """Summarize estimate, tracked and remaining work by project."""
        if not tasks:
            return "No tasks in current view."

        summary: dict[str, dict[str, float | int]] = {}
        resolved_settings = settings or PlanningSettings()
        resolved_now = now or datetime.now(UTC)
        calendar = WorkingCalendar(resolved_settings)

        for task in tasks:
            project = task.project or "(none)"
            stats = summary.setdefault(
                project,
                {
                    "tasks": 0,
                    "active": 0,
                    "blocked": 0,
                    "estimate": 0.0,
                    "tracked": 0.0,
                    "remaining": 0.0,
                    "unestimated": 0,
                    "urgency": 0.0,
                },
            )
            stats["tasks"] += 1
            stats["active"] += int(task.active)
            stats["blocked"] += int(bool(task.depends))
            stats["estimate"] += task.estimate_hours
            stats["tracked"] += (
                tracked_hours.get(task.uuid, 0.0)
                if tracked_hours is not None
                else 0.0
            )
            stats["remaining"] += remaining_estimate_hours(
                task,
                calendar,
                resolved_now,
                tracked_hours,
            )
            stats["unestimated"] += int(not task.has_estimate)
            stats["urgency"] += task.urgency

        projects = sorted(
            summary,
            key=lambda project: (project == "(none)", project.casefold()),
        )
        lines = [
            "Project | Tasks | Active | Blocked | Estimate | Tracked | Remaining | Unestimated | Urgency"
        ]
        for project in projects:
            stats = summary[project]
            lines.append(
                f"{project} | {stats['tasks']} | {stats['active']} | "
                f"{stats['blocked']} | {stats['estimate']:.2f}h | "
                f"{stats['tracked']:.2f}h | {stats['remaining']:.2f}h | "
                f"{stats['unestimated']} | {stats['urgency']:.2f}"
            )
        return "\n".join(lines)

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

    def _expanded_planning_tasks(self) -> list[Task] | None:
        """Expand external dependencies for planning views."""
        try:
            return self.client.expand_dependencies(
                self.view_tasks,
                self.planning_settings.dependency_depth,
            )
        except TaskwarriorError as exc:
            self._show_error(exc)
            return None

    def _tracked_planning_context(
        self,
        tasks: list[Task],
    ) -> tuple[dict[str, float], datetime] | None:
        """Read Timewarrior effort once and share one reference instant."""
        now = datetime.now(UTC)
        try:
            return self.client.timewarrior_hours(tasks, now=now), now
        except TaskwarriorError as exc:
            self._show_error(exc)
            return None

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
        """Reload the current view, tracking effort, then reapply local state."""
        try:
            self.view_tasks = self.client.view(self.current_view)
        except TaskwarriorError as exc:
            self._show_error(exc)
            return

        self.tracking_now = datetime.now(UTC)
        tracking_error: TaskwarriorError | None = None
        try:
            self.tracked_hours = self.client.timewarrior_hours(
                self.view_tasks,
                now=self.tracking_now,
            )
        except TaskwarriorError as exc:
            self.tracked_hours = {}
            tracking_error = exc

        self._render_tasks()
        if tracking_error is not None:
            self._show_error(tracking_error)

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

    def action_filter_tag(self) -> None:
        """Open an exact local tag filter."""
        self.push_screen(
            TagFilterForm(self.tag_filter),
            self._apply_tag_filter,
        )

    def action_toggle_active(self) -> None:
        """Toggle a local filter for currently active tasks."""
        self.active_only = not self.active_only
        self._render_tasks()

    def action_clear_local_state(self) -> None:
        """Clear all local filters and sorting without refetching."""
        self.search_query = ""
        self.project_filter = ""
        self.tag_filter = ""
        self.blocked_only = False
        self.active_only = False
        self.sort_key = None
        self._render_tasks()

    def action_show_dependencies(self) -> None:
        """Show dependency links for the selected task, including external ancestors."""
        task = self._selected_task()
        if task is None:
            return
        tasks = self._expanded_planning_tasks()
        if tasks is None:
            return
        self.push_screen(
            DependencyScreen(
                f"Dependencies for {task.short_uuid}",
                self._dependency_summary(task, tasks),
            )
        )

    def action_show_dependency_overview(self) -> None:
        """Show the dependency graph, expanding external ancestors."""
        tasks = self._expanded_planning_tasks()
        if tasks is None:
            return
        self.push_screen(
            DependencyOverviewScreen(self._dependency_overview(tasks))
        )

    def action_show_critical_path(self) -> None:
        """Show estimate-based critical-path analysis for the expanded graph."""
        tasks = self._expanded_planning_tasks()
        if tasks is None:
            return
        context = self._tracked_planning_context(tasks)
        if context is None:
            return
        tracked_hours, now = context
        self.push_screen(
            CriticalPathScreen(
                self._critical_path_summary(
                    tasks,
                    self.planning_settings,
                    now=now,
                    tracked_hours=tracked_hours,
                )
            )
        )

    def action_show_gantt(self) -> None:
        """Show an estimate-based Gantt view for the expanded graph."""
        tasks = self._expanded_planning_tasks()
        if tasks is None:
            return
        context = self._tracked_planning_context(tasks)
        if context is None:
            return
        tracked_hours, now = context
        self.push_screen(
            GanttScreen(
                self._gantt_summary(
                    tasks,
                    self.planning_settings,
                    now=now,
                    tracked_hours=tracked_hours,
                )
            )
        )

    def action_show_calendar_plan(self) -> None:
        """Show an absolute calendar schedule for the expanded graph."""
        tasks = self._expanded_planning_tasks()
        if tasks is None:
            return
        context = self._tracked_planning_context(tasks)
        if context is None:
            return
        tracked_hours, now = context
        self.push_screen(
            CalendarPlanScreen(
                self._calendar_plan(
                    tasks,
                    self.planning_settings,
                    now=now,
                    tracked_hours=tracked_hours,
                )
            )
        )

    def action_show_constraints(self) -> None:
        """Show scheduled and due constraints for the expanded graph."""
        tasks = self._expanded_planning_tasks()
        if tasks is None:
            return
        context = self._tracked_planning_context(tasks)
        if context is None:
            return
        tracked_hours, now = context
        self.push_screen(
            ConstraintsScreen(
                self._constraints_summary(
                    tasks,
                    self.planning_settings,
                    now=now,
                    tracked_hours=tracked_hours,
                )
            )
        )

    def action_show_milestones(self) -> None:
        """Show explicit zero-duration milestones for the current view."""
        self.push_screen(MilestonesScreen(self._milestones_summary(self.view_tasks)))

    def action_show_project_overview(self) -> None:
        """Show project totals including tracked and remaining work."""
        context = self._tracked_planning_context(self.view_tasks)
        if context is None:
            return
        tracked_hours, now = context
        self.push_screen(
            ProjectOverviewScreen(
                self._project_overview(
                    self.view_tasks,
                    self.planning_settings,
                    now=now,
                    tracked_hours=tracked_hours,
                )
            )
        )

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
