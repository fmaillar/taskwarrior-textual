"""Textual forms and modal screens."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Static

from .models import Task

HELP_TEXT = """\
Task actions
  Enter   Inspect selected task
  a       Add task
  e       Edit ordinary task fields
  E       Edit planning fields
  s / x   Start / stop work
  d / D   Complete / delete task
  y       Synchronize Taskwarrior

Views, search and filters
  1..5    Pending / waiting / completed / deleted / scheduled
  /       Search description, project or tags
  p       Filter by project
  f       Filter by tag
  b       Toggle blocked tasks
  v       Toggle active tasks
  t       Cycle local sort
  c       Clear local filters and sort
  r       Refresh current Taskwarrior view

Planning
  g       Selected-task dependencies
  G       Dependency graph
  C       Critical path
  H       Gantt
  I       Planning health
  L       Calendar plan
  K       Scheduling constraints
  M       Milestones
  S       Auto-schedule selected project

Projects and time
  O       Interactive project cockpit
  P       Project overview
  T       Timewarrior effort report
  R       Timewarrior trend

General
  ?       Open / close this help
  Esc     Close current dialog
  q       Quit
"""


class HelpScreen(ModalScreen[None]):
    """Scrollable in-application reference for commands and key bindings."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "close", "Close"),
        Binding("question_mark", "close", "Close", key_display="?"),
    ]

    CSS = """
    HelpScreen { align: center middle; }
    #help-box {
        width: 90%;
        max-width: 100;
        height: 90%;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    #help-scroll { height: 1fr; margin-top: 1; overflow-y: auto; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="help-box"):
            yield Label("taskwarrior-textual help")
            with Vertical(id="help-scroll"):
                yield Static(HELP_TEXT, id="help-body")

    def action_close(self) -> None:
        self.dismiss(None)


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


class PlanningForm(ModalScreen[dict[str, str] | None]):
    """Edit only planning metadata for one task."""

    CSS = """
    PlanningForm { align: center middle; }
    #planning-form {
        width: 86%;
        max-width: 105;
        height: auto;
        max-height: 92%;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    #planning-candidates {
        height: auto;
        max-height: 14;
        margin: 1 0;
    }
    #planning-buttons { height: auto; margin-top: 1; }
    #planning-buttons Button { margin-right: 1; }
    """

    def __init__(self, task: Task, candidates: list[Task]) -> None:
        super().__init__()
        self.planned_task = task
        self.candidates = candidates
        rows = [
            f"{candidate.short_uuid} | {candidate.project or '(none)'} | "
            f"{candidate.description}"
            for candidate in sorted(
                candidates,
                key=lambda item: (
                    item.uuid == task.uuid,
                    item.project.casefold(),
                    item.short_uuid,
                    item.uuid,
                ),
            )
            if candidate.uuid != task.uuid
        ]
        self.candidate_body = (
            "Dependency candidates\nUUID | Project | Description\n"
            + ("\n".join(rows) if rows else "(none)")
        )

    def compose(self) -> ComposeResult:
        task = self.planned_task
        with Vertical(id="planning-form"):
            yield Label(
                f"Planning: {task.short_uuid} — {task.description}"
            )
            yield Input(
                value=task.display_due,
                placeholder="Due: YYYY-MM-DD, tomorrow, ...",
                id="planning-due",
            )
            yield Input(
                value=task.display_wait,
                placeholder="Wait: YYYY-MM-DD HH:MM, tomorrow, ...",
                id="planning-wait",
            )
            yield Input(
                value=task.display_scheduled,
                placeholder="Scheduled: YYYY-MM-DD HH:MM, tomorrow, ...",
                id="planning-scheduled",
            )
            yield Input(
                value=",".join(dep[:8] for dep in task.depends),
                placeholder="Dependencies: comma-separated UUIDs/prefixes",
                id="planning-depends",
            )
            yield Input(
                value=str(task.estimate_hours) if task.has_estimate else "",
                placeholder="Estimate hours (0 = milestone; empty clears)",
                id="planning-estimate",
            )
            yield Static(self.candidate_body, id="planning-candidates")
            with Horizontal(id="planning-buttons"):
                yield Button("Save planning", variant="primary", id="planning-save")
                yield Button("Cancel", id="planning-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "planning-cancel":
            self.dismiss(None)
            return
        self.dismiss(
            {
                "due": self.query_one("#planning-due", Input).value.strip(),
                "wait": self.query_one("#planning-wait", Input).value.strip(),
                "scheduled": self.query_one("#planning-scheduled", Input).value.strip(),
                "depends": self.query_one("#planning-depends", Input).value.strip(),
                "estimate": self.query_one("#planning-estimate", Input).value.strip(),
            }
        )


class SearchForm(ModalScreen[str]):
    """Modal text search over the currently loaded Taskwarrior view."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [("escape", "clear_search", "Clear search")]

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

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [("escape", "clear_filter", "Clear tag filter")]

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

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [("escape", "clear_filter", "Clear project filter")]

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

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [("escape", "close", "Close")]

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

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [("escape", "close", "Close")]

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

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [("escape", "close", "Close")]

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

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [("escape", "close", "Close")]

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

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [("escape", "close", "Close")]

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

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [("escape", "close", "Close")]

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

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [("escape", "close", "Close")]

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
        self.heading = title
        self.body = body

    def compose(self) -> ComposeResult:
        with Vertical(id="dependency-box"):
            yield Label(self.heading)
            yield Static(self.body, id="dependency-body")

    def action_close(self) -> None:
        self.dismiss(None)


class PlanningHealthScreen(ModalScreen[None]):
    """Read-only planning health report."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [("escape", "close", "Close")]

    CSS = """
    PlanningHealthScreen { align: center middle; }
    #planning-health-box {
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
        with Vertical(id="planning-health-box"):
            yield Label("Planning health")
            yield Static(self.body, id="planning-health-body")

    def action_close(self) -> None:
        self.dismiss(None)


class ScheduleProposalScreen(ModalScreen[bool]):
    """Preview an auto-schedule proposal before applying it."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel"),
    ]

    CSS = """
    ScheduleProposalScreen { align: center middle; }
    #schedule-proposal-box {
        width: 92%;
        max-width: 130;
        height: auto;
        max-height: 90%;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    #schedule-proposal-buttons { height: auto; margin-top: 1; }
    #schedule-proposal-buttons Button { margin-right: 1; }
    """

    def __init__(self, body: str, *, can_apply: bool) -> None:
        super().__init__()
        self.body = body
        self.can_apply = can_apply

    def compose(self) -> ComposeResult:
        with Vertical(id="schedule-proposal-box"):
            yield Label("Project auto-schedule")
            yield Static(self.body, id="schedule-proposal-body")
            with Horizontal(id="schedule-proposal-buttons"):
                yield Button(
                    "Apply",
                    variant="primary",
                    id="schedule-apply",
                    disabled=not self.can_apply,
                )
                yield Button("Cancel", id="schedule-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "schedule-apply")

    def action_cancel(self) -> None:
        self.dismiss(False)


class ProjectDashboardScreen(ModalScreen[tuple[str, str] | None]):
    """Interactive project cockpit over project tasks and external prerequisites."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "close", "Close"),
        ("enter", "inspect", "Inspect"),
        ("e", "edit_task", "Edit"),
        ("shift+e", "edit_planning", "Planning"),
        ("g", "dependencies", "Dependencies"),
        ("s", "start_task", "Start"),
        ("x", "stop_task", "Stop"),
        ("d", "done_task", "Done"),
        ("shift+s", "auto_schedule", "Auto schedule"),
    ]

    CSS = """
    ProjectDashboardScreen { align: center middle; }
    #project-dashboard-box {
        width: 96%;
        max-width: 140;
        height: 92%;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    #project-dashboard-body { height: auto; margin-bottom: 1; }
    #project-dashboard-tasks { height: 1fr; }
    #project-dashboard-help { height: auto; margin-top: 1; }
    """

    def __init__(
        self,
        body: str,
        tasks: list[Task],
        project_uuids: set[str],
    ) -> None:
        super().__init__()
        self.body = body
        self.tasks = list(tasks)
        self.project_uuids = set(project_uuids)

    def compose(self) -> ComposeResult:
        with Vertical(id="project-dashboard-box"):
            yield Label("Project cockpit")
            yield Static(self.body, id="project-dashboard-body")
            yield DataTable(
                id="project-dashboard-tasks",
                cursor_type="row",
                zebra_stripes=True,
            )
            yield Static(
                "Enter inspect | e edit | E planning | g dependencies | "
                "s/x start/stop | d done | S auto-schedule | Esc close",
                id="project-dashboard-help",
            )

    def on_mount(self) -> None:
        table = self.query_one("#project-dashboard-tasks", DataTable)
        table.add_columns(
            "UUID",
            "Scope",
            "State",
            "Project",
            "Estimate",
            "Due",
            "Description",
        )
        for task in sorted(
            self.tasks,
            key=lambda item: (
                item.uuid not in self.project_uuids,
                item.project.casefold(),
                item.short_uuid,
                item.uuid,
            ),
        ):
            table.add_row(
                task.short_uuid,
                "project" if task.uuid in self.project_uuids else "external",
                "active" if task.active else task.status,
                task.project or "(none)",
                task.display_estimate or "—",
                task.display_due or "—",
                task.description,
                key=task.uuid,
            )

    def _selected_uuid(self) -> str | None:
        table = self.query_one("#project-dashboard-tasks", DataTable)
        if table.row_count == 0:
            return None
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        return str(row_key.value)

    def _emit_task_action(self, action: str) -> None:
        uuid = self._selected_uuid()
        if uuid is not None:
            self.dismiss((action, uuid))

    def action_inspect(self) -> None:
        self._emit_task_action("inspect")

    def action_edit_task(self) -> None:
        self._emit_task_action("edit")

    def action_edit_planning(self) -> None:
        self._emit_task_action("planning")

    def action_dependencies(self) -> None:
        self._emit_task_action("dependencies")

    def action_start_task(self) -> None:
        self._emit_task_action("start")

    def action_stop_task(self) -> None:
        self._emit_task_action("stop")

    def action_done_task(self) -> None:
        self._emit_task_action("done")

    def action_auto_schedule(self) -> None:
        self.dismiss(("auto_schedule", ""))

    def action_close(self) -> None:
        self.dismiss(None)


class ProjectOverviewScreen(ModalScreen[None]):
    """Read-only local project summary for the current view."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [("escape", "close", "Close")]

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


class TimewarriorReportScreen(ModalScreen[None]):
    """Read-only tracked-effort report for the current view."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [("escape", "close", "Close")]

    CSS = """
    TimewarriorReportScreen { align: center middle; }
    #timewarrior-report-box {
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
        with Vertical(id="timewarrior-report-box"):
            yield Label("Timewarrior effort report")
            yield Static(self.body, id="timewarrior-report-body")

    def action_close(self) -> None:
        self.dismiss(None)


class TimewarriorTrendScreen(ModalScreen[None]):
    """Read-only Timewarrior trend report with selectable periods."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("7", "period_7d", "7 days"),
        ("3", "period_30d", "30 days"),
        ("w", "period_week", "Week"),
        ("m", "period_month", "Month"),
        ("escape", "close", "Close"),
    ]

    CSS = """
    TimewarriorTrendScreen { align: center middle; }
    #timewarrior-trend-box {
        width: 90%;
        max-width: 120;
        height: auto;
        max-height: 90%;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    """

    def __init__(self, bodies: dict[str, str], initial_period: str = "7d") -> None:
        super().__init__()
        self.bodies = bodies
        self.period = initial_period

    def compose(self) -> ComposeResult:
        with Vertical(id="timewarrior-trend-box"):
            yield Label("Timewarrior trend")
            yield Static(self.bodies[self.period], id="timewarrior-trend-body")

    def _select_period(self, period: str) -> None:
        self.period = period
        self.query_one("#timewarrior-trend-body", Static).update(self.bodies[period])

    def action_period_7d(self) -> None:
        self._select_period("7d")

    def action_period_30d(self) -> None:
        self._select_period("30d")

    def action_period_week(self) -> None:
        self._select_period("week")

    def action_period_month(self) -> None:
        self._select_period("month")

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
