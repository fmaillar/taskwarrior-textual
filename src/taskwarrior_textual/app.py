"""Textual application."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import ClassVar, cast

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import DataTable, Footer, Header, Static

from .config import PlanningSettings, WorkingCalendar, load_planning_settings
from .models import Task
from .planning import build_planning_graph, remaining_estimate_hours
from .reporting import PlanningReportsMixin
from .taskwarrior import TaskwarriorClient, TaskwarriorError
from .ui import (
    CalendarPlanScreen,
    ConfirmDelete,
    ConstraintsScreen,
    CriticalPathScreen,
    DependencyOverviewScreen,
    DependencyScreen,
    GanttScreen,
    HelpScreen,
    MilestonesScreen,
    PlanningForm,
    PlanningHealthScreen,
    ProjectDashboardScreen,
    ProjectFilterForm,
    ProjectOverviewScreen,
    ScheduleProposalScreen,
    SearchForm,
    TagFilterForm,
    TaskForm,
    TimewarriorReportScreen,
    TimewarriorTrendScreen,
)


class TaskwarriorApp(PlanningReportsMixin, App[None]):
    """Interactive Taskwarrior browser and editor."""

    TITLE = "Taskwarrior Textual"
    SUB_TITLE = "Taskwarrior 3 frontend"

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("question_mark", "show_help", "Help", key_display="?"),
        ("q", "quit", "Quit"),
        ("r", "refresh_tasks", "Refresh"),
        ("enter", "inspect_task", "Inspect"),
        ("a", "add_task", "Add"),
        ("e", "edit_task", "Edit"),
        ("shift+e", "edit_planning", "Planning"),
        ("s", "start_task", "Start"),
        ("shift+s", "auto_schedule_project", "Auto schedule"),
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
        ("shift+i", "show_planning_health", "Health"),
        ("shift+l", "show_calendar_plan", "Calendar"),
        ("shift+k", "show_constraints", "Constraints"),
        ("shift+m", "show_milestones", "Milestones"),
        ("shift+p", "show_project_overview", "Projects"),
        ("shift+o", "show_project_dashboard", "Dashboard"),
        ("shift+t", "show_timewarrior_report", "Timewarrior"),
        ("shift+r", "show_timewarrior_trend", "Trend"),
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

    def _apply_search(self, query: str | None) -> None:
        """Apply a local search without querying Taskwarrior again."""
        self.search_query = cast(str, query).strip()
        self._render_tasks()

    def _apply_project_filter(self, project: str | None) -> None:
        """Apply an exact local project filter without refetching."""
        self.project_filter = cast(str, project).strip()
        self._render_tasks()

    def _apply_tag_filter(self, tag: str | None) -> None:
        """Apply an exact local tag filter without refetching."""
        self.tag_filter = cast(str, tag).strip()
        self._render_tasks()

    def _selected_task(self) -> Task | None:
        table = self.query_one("#tasks", DataTable)
        if table.row_count == 0:
            return None
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        return self.tasks.get(str(row_key.value))

    @staticmethod
    def _resolve_planning_dependencies(
        value: str,
        target: Task,
        candidates: list[Task],
    ) -> str:
        """Resolve comma-separated UUID prefixes to deterministic full UUIDs."""
        requested = [
            part.strip()
            for part in value.split(",")
            if part.strip()
        ]
        resolved: list[str] = []
        for prefix in requested:
            matches = [
                task
                for task in candidates
                if task.uuid.startswith(prefix)
            ]
            if target.uuid.startswith(prefix) and any(
                task.uuid == target.uuid for task in matches
            ):
                raise TaskwarriorError(
                    f"task cannot depend on itself: {prefix}"
                )
            if not matches:
                raise TaskwarriorError(f"unknown dependency: {prefix}")
            if len(matches) > 1:
                raise TaskwarriorError(f"ambiguous dependency prefix: {prefix}")
            uuid = matches[0].uuid
            if uuid not in resolved:
                resolved.append(uuid)
        return ",".join(resolved)

    @staticmethod
    def _validate_planning_dependency_update(
        target: Task,
        resolved_depends: str,
        candidates: list[Task],
    ) -> None:
        """Reject dependency changes that introduce a cycle through target."""
        depends = tuple(
            part.strip()
            for part in resolved_depends.split(",")
            if part.strip()
        )
        replacement = replace(target, depends=depends)
        hypothetical = [
            replacement if task.uuid == target.uuid else task
            for task in candidates
        ]
        graph = build_planning_graph(hypothetical)
        if target.uuid in graph.cycle_nodes:
            raise TaskwarriorError("dependency cycle would include the edited task")

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

    def _run_task_action_for(self, task: Task, callback) -> None:
        """Run a Taskwarrior state action for an explicit task."""
        try:
            message = callback(task.short_uuid)
        except TaskwarriorError as exc:
            self._show_error(exc)
            return
        self.query_one("#details", Static).update(message or "Done.")
        self.action_refresh_tasks()

    def _run_task_action(self, callback) -> None:
        task = self._selected_task()
        if task is None:
            return
        self._run_task_action_for(task, callback)

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

    def action_show_help(self) -> None:
        """Open the in-application key and feature reference."""
        self.push_screen(HelpScreen())

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

    def _show_task_dependencies(
        self,
        task: Task,
        tasks: list[Task],
    ) -> None:
        """Show dependency links for an explicit task in an expanded graph."""
        self.push_screen(
            DependencyScreen(
                f"Dependencies for {task.short_uuid}",
                self._dependency_summary(task, tasks),
            )
        )

    def action_show_dependencies(self) -> None:
        """Show dependency links for the selected task, including external ancestors."""
        task = self._selected_task()
        if task is None:
            return
        tasks = self._expanded_planning_tasks()
        if tasks is None:
            return
        self._show_task_dependencies(task, tasks)

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

    def action_show_planning_health(self) -> None:
        """Show planning health for the expanded current view."""
        tasks = self._expanded_planning_tasks()
        if tasks is None:
            return
        context = self._tracked_planning_context(tasks)
        if context is None:
            return
        tracked_hours, now = context
        self.push_screen(
            PlanningHealthScreen(
                self._planning_health(
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

    def action_show_timewarrior_trend(self) -> None:
        """Show selectable Timewarrior trends for the current view."""
        now = datetime.now(UTC)
        try:
            intervals = self.client.timewarrior_intervals(
                self.view_tasks,
                now=now,
            )
        except TaskwarriorError as exc:
            self._show_error(exc)
            return

        bodies = {
            period: self._timewarrior_trend(
                self.view_tasks,
                intervals,
                self.planning_settings,
                now=now,
                period=period,
            )
            for period in ("7d", "30d", "week", "month")
        }
        self.push_screen(TimewarriorTrendScreen(bodies))

    def action_show_timewarrior_report(self) -> None:
        """Show tracked effort and remaining work for the current view."""
        context = self._tracked_planning_context(self.view_tasks)
        if context is None:
            return
        tracked_hours, now = context
        self.push_screen(
            TimewarriorReportScreen(
                self._timewarrior_report(
                    self.view_tasks,
                    self.planning_settings,
                    now=now,
                    tracked_hours=tracked_hours,
                )
            )
        )

    def action_auto_schedule_project(self) -> None:
        """Preview and optionally apply an auto-schedule for the selected project."""
        selected = self._selected_task()
        if selected is None:
            return

        project_tasks = [
            task
            for task in self.view_tasks
            if task.project == selected.project
        ]
        try:
            expanded_tasks = self.client.expand_dependencies(
                project_tasks,
                self.planning_settings.dependency_depth,
            )
        except TaskwarriorError as exc:
            self._show_error(exc)
            return

        context = self._tracked_planning_context(expanded_tasks)
        if context is None:
            return
        tracked_hours, now = context
        body, changes = self._schedule_proposal(
            selected.project,
            project_tasks,
            expanded_tasks,
            self.planning_settings,
            now=now,
            tracked_hours=tracked_hours,
        )

        def apply(confirmed: bool | None) -> None:
            if not confirmed:
                return
            try:
                for task in sorted(
                    project_tasks,
                    key=lambda item: (item.short_uuid, item.uuid),
                ):
                    scheduled = changes.get(task.uuid)
                    if scheduled is None:
                        continue
                    self.client.modify_scheduled(task.short_uuid, scheduled)
            except TaskwarriorError as exc:
                self.action_refresh_tasks()
                self._show_error(exc)
                return
            self.action_refresh_tasks()

        self.push_screen(
            ScheduleProposalScreen(body, can_apply=bool(changes)),
            apply,
        )

    def action_show_project_dashboard(self) -> None:
        """Open the selected project's interactive planning cockpit."""
        selected = self._selected_task()
        if selected is None:
            return

        project_tasks = [
            task
            for task in self.view_tasks
            if task.project == selected.project
        ]
        try:
            expanded_tasks = self.client.expand_dependencies(
                project_tasks,
                self.planning_settings.dependency_depth,
            )
        except TaskwarriorError as exc:
            self._show_error(exc)
            return

        context = self._tracked_planning_context(expanded_tasks)
        if context is None:
            return
        tracked_hours, now = context
        by_uuid = {task.uuid: task for task in expanded_tasks}
        project_uuids = {task.uuid for task in project_tasks}

        def handle(result: tuple[str, str] | None) -> None:
            if result is None:
                return
            action, task_uuid = result
            if action == "auto_schedule":
                self.action_auto_schedule_project()
                return

            task = by_uuid[task_uuid]
            handlers = {
                "inspect": self._inspect_task,
                "edit": self._edit_task,
                "planning": lambda item: self._edit_planning_task(
                    item,
                    expanded_tasks,
                ),
                "dependencies": lambda item: self._show_task_dependencies(
                    item,
                    expanded_tasks,
                ),
                "start": lambda item: self._run_task_action_for(
                    item,
                    self.client.start,
                ),
                "stop": lambda item: self._run_task_action_for(
                    item,
                    self.client.stop,
                ),
                "done": lambda item: self._run_task_action_for(
                    item,
                    self.client.done,
                ),
            }
            handlers[action](task)

        self.push_screen(
            ProjectDashboardScreen(
                self._project_dashboard(
                    selected.project,
                    project_tasks,
                    expanded_tasks,
                    self.planning_settings,
                    now=now,
                    tracked_hours=tracked_hours,
                    include_tasks=False,
                ),
                expanded_tasks,
                project_uuids,
            ),
            handle,
        )

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

    def _inspect_task(self, task: Task) -> None:
        """Show Taskwarrior information for an explicit task."""
        try:
            information = self.client.information(task.short_uuid)
        except TaskwarriorError as exc:
            self._show_error(exc)
            return
        self.query_one("#details", Static).update(information)

    def action_inspect_task(self) -> None:
        """Show Taskwarrior information for the selected row."""
        task = self._selected_task()
        if task is None:
            return
        self._inspect_task(task)

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

    def _edit_task(self, task: Task) -> None:
        """Open the ordinary task editor for an explicit task."""

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

    def action_edit_task(self) -> None:
        """Edit the selected task."""
        task = self._selected_task()
        if task is None:
            return
        self._edit_task(task)

    def _edit_planning_task(
        self,
        task: Task,
        candidates: list[Task],
    ) -> None:
        """Open the planning editor for an explicit task and graph."""

        def save(values: dict[str, str] | None) -> None:
            if values is None:
                return
            try:
                resolved_depends = self._resolve_planning_dependencies(
                    values["depends"],
                    task,
                    candidates,
                )
                self._validate_planning_dependency_update(
                    task,
                    resolved_depends,
                    candidates,
                )
                self.client.modify_planning(
                    task.short_uuid,
                    due=values["due"],
                    wait=values["wait"],
                    scheduled=values["scheduled"],
                    depends=resolved_depends,
                    estimate=values["estimate"],
                )
            except TaskwarriorError as exc:
                self._show_error(exc)
                return
            self.action_refresh_tasks()

        self.push_screen(PlanningForm(task, candidates), save)

    def action_edit_planning(self) -> None:
        """Edit scheduling metadata and dependencies for the selected task."""
        task = self._selected_task()
        if task is None:
            return
        candidates = self._expanded_planning_tasks()
        if candidates is None:
            return
        self._edit_planning_task(task, candidates)

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

        def remove(confirmed: bool | None) -> None:
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
    """Run the Textual application with persisted planning settings."""
    TaskwarriorApp(planning_settings=load_planning_settings()).run()
