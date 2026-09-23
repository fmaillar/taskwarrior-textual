"""Pure planning and reporting helpers shared by the Textual application."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from .config import PlanningSettings, WorkingCalendar
from .models import Task
from .planning import (
    build_absolute_schedule,
    build_planning_graph,
    build_relative_schedule,
    parse_taskwarrior_datetime,
    remaining_estimate_hours,
)
from .taskwarrior import TimewarriorInterval


class PlanningReportsMixin:
    """Deterministic planning calculations and text report rendering."""

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
    def _timewarrior_trend(
        tasks: list[Task],
        intervals: tuple[TimewarriorInterval, ...],
        settings: PlanningSettings | None = None,
        *,
        now: datetime | None = None,
        period: str = "7d",
        days: int | None = None,
    ) -> str:
        """Summarize matched Timewarrior effort and compare the prior period."""
        resolved_settings = settings or PlanningSettings()
        resolved_now = now or datetime.now(UTC)
        zone = WorkingCalendar(resolved_settings).timezone
        local_today = resolved_now.astimezone(zone).date()

        if days is not None:
            if days <= 0:
                raise ValueError("days must be a positive integer")
            first_day = local_today - timedelta(days=days - 1)
            last_day = local_today
            previous_first = first_day - timedelta(days=days)
            previous_last = first_day - timedelta(days=1)
            label = (
                f"Last {days} local days through {local_today.isoformat()} "
                f"({resolved_settings.timezone})"
            )
        elif period == "7d":
            first_day = local_today - timedelta(days=6)
            last_day = local_today
            previous_first = first_day - timedelta(days=7)
            previous_last = first_day - timedelta(days=1)
            label = (
                f"Last 7 local days through {local_today.isoformat()} "
                f"({resolved_settings.timezone})"
            )
        elif period == "30d":
            first_day = local_today - timedelta(days=29)
            last_day = local_today
            previous_first = first_day - timedelta(days=30)
            previous_last = first_day - timedelta(days=1)
            label = (
                f"Last 30 local days through {local_today.isoformat()} "
                f"({resolved_settings.timezone})"
            )
        elif period == "week":
            first_day = local_today - timedelta(days=local_today.weekday())
            last_day = first_day + timedelta(days=6)
            previous_first = first_day - timedelta(days=7)
            previous_last = previous_first + timedelta(days=local_today.weekday())
            label = (
                f"Current week {first_day.isoformat()} through {last_day.isoformat()} "
                f"({resolved_settings.timezone})"
            )
        elif period == "month":
            first_day = local_today.replace(day=1)
            if first_day.month == 12:
                next_month = first_day.replace(
                    year=first_day.year + 1,
                    month=1,
                )
            else:
                next_month = first_day.replace(month=first_day.month + 1)
            last_day = next_month - timedelta(days=1)

            previous_month_last = first_day - timedelta(days=1)
            previous_first = previous_month_last.replace(day=1)
            previous_last = previous_first.replace(
                day=min(local_today.day, previous_month_last.day)
            )
            label = (
                f"Current month {first_day.isoformat()} through {last_day.isoformat()} "
                f"({resolved_settings.timezone})"
            )
        else:
            raise ValueError(f"unknown trend period: {period}")

        by_uuid = {task.uuid: task for task in tasks}

        def aggregate(
            range_first,
            range_last,
            *,
            include_daily: bool,
        ) -> tuple[float, dict[str, float], dict]:
            window_start = datetime.combine(
                range_first,
                time.min,
                tzinfo=zone,
            ).astimezone(UTC)
            window_end = datetime.combine(
                range_last + timedelta(days=1),
                time.min,
                tzinfo=zone,
            ).astimezone(UTC)
            daily = (
                {
                    range_first + timedelta(days=offset): 0.0
                    for offset in range((range_last - range_first).days + 1)
                }
                if include_daily
                else {}
            )
            projects: dict[str, float] = {}
            total = 0.0

            for interval in intervals:
                task = by_uuid.get(interval.task_uuid)
                if task is None:
                    continue
                clipped_start = max(interval.start, window_start)
                clipped_end = min(interval.end, window_end)
                if clipped_end <= clipped_start:
                    continue

                hours = (clipped_end - clipped_start).total_seconds() / 3600
                total += hours
                project = task.project or "(none)"
                projects[project] = projects.get(project, 0.0) + hours

                if not include_daily:
                    continue
                cursor = clipped_start
                while cursor < clipped_end:
                    local_day = cursor.astimezone(zone).date()
                    next_midnight = datetime.combine(
                        local_day + timedelta(days=1),
                        time.min,
                        tzinfo=zone,
                    ).astimezone(UTC)
                    segment_end = min(clipped_end, next_midnight)
                    daily[local_day] += (
                        segment_end - cursor
                    ).total_seconds() / 3600
                    cursor = segment_end

            return total, projects, daily

        total, projects, daily = aggregate(
            first_day,
            last_day,
            include_daily=True,
        )
        previous_total, previous_projects, _ = aggregate(
            previous_first,
            previous_last,
            include_daily=False,
        )
        delta = total - previous_total
        if previous_total == 0:
            relative_change = "new" if total > 0 else "+0.0%"
        else:
            relative_change = f"{delta / previous_total * 100:+.1f}%"

        lines = [
            label,
            f"Tracked in window: {total:.2f}h",
            f"Previous comparable: {previous_total:.2f}h",
            f"Change: {delta:+.2f}h ({relative_change})",
            "",
            "Daily",
            "Date | Tracked",
        ]
        lines.extend(
            f"{day.isoformat()} | {daily[day]:.2f}h"
            for day in sorted(daily)
        )
        lines.extend(
            [
                "",
                "Projects",
                "Project | Tracked | Previous | Change",
            ]
        )
        all_projects = set(projects) | set(previous_projects)
        lines.extend(
            (
                f"{project} | {projects.get(project, 0.0):.2f}h | "
                f"{previous_projects.get(project, 0.0):.2f}h | "
                f"{projects.get(project, 0.0) - previous_projects.get(project, 0.0):+.2f}h"
            )
            for project in sorted(
                all_projects,
                key=lambda item: (
                    -projects.get(item, 0.0),
                    -previous_projects.get(item, 0.0),
                    item.casefold(),
                ),
            )
        )
        return "\n".join(lines)

    @staticmethod
    def _timewarrior_report(
        tasks: list[Task],
        settings: PlanningSettings | None = None,
        *,
        now: datetime | None = None,
        tracked_hours: dict[str, float] | None = None,
    ) -> str:
        """Summarize per-task tracked effort and remaining work."""
        if not tasks:
            return "No tasks in current view."

        resolved_settings = settings or PlanningSettings()
        resolved_now = now or datetime.now(UTC)
        calendar = WorkingCalendar(resolved_settings)
        tracked = tracked_hours or {}

        total_estimate = sum(task.estimate_hours for task in tasks)
        total_tracked = sum(tracked.get(task.uuid, 0.0) for task in tasks)
        total_remaining = sum(
            remaining_estimate_hours(
                task,
                calendar,
                resolved_now,
                tracked_hours,
            )
            for task in tasks
        )

        lines = [
            (
                f"Tracked total: {total_tracked:.2f}h | "
                f"Estimated total: {total_estimate:.2f}h | "
                f"Remaining total: {total_remaining:.2f}h"
            ),
            "",
            "UUID | Project | Estimate | Tracked | Remaining | Progress | Description",
        ]

        ordered = sorted(
            tasks,
            key=lambda task: (
                -tracked.get(task.uuid, 0.0),
                task.project.casefold(),
                task.short_uuid,
                task.uuid,
            ),
        )
        for task in ordered:
            tracked_value = tracked.get(task.uuid, 0.0)
            if not task.has_estimate:
                estimate = "—"
                remaining = "—"
                progress = "—"
            else:
                estimate = f"{task.estimate_hours:.2f}h"
                remaining_value = remaining_estimate_hours(
                    task,
                    calendar,
                    resolved_now,
                    tracked_hours,
                )
                remaining = f"{remaining_value:.2f}h"
                if task.is_milestone:
                    progress = "milestone"
                else:
                    progress = f"{tracked_value / task.estimate_hours * 100:.1f}%"

            lines.append(
                f"{task.short_uuid} | {task.project or '(none)'} | "
                f"{estimate} | {tracked_value:.2f}h | {remaining} | "
                f"{progress} | {task.description}"
            )

        return "\n".join(lines)

    @staticmethod
    def _planning_health(
        tasks: list[Task],
        settings: PlanningSettings | None = None,
        *,
        now: datetime | None = None,
        tracked_hours: dict[str, float] | None = None,
    ) -> str:
        """Report structural, scheduling, estimate, and effort planning issues."""
        if not tasks:
            return "No tasks in current view."

        resolved_settings = settings or PlanningSettings()
        resolved_now = now or datetime.now(UTC)
        calendar = WorkingCalendar(resolved_settings)
        graph = build_planning_graph(tasks)
        tracked = tracked_hours or {}

        unestimated = sorted(
            task.short_uuid
            for task in tasks
            if not task.has_estimate
        )
        invalid_scheduled: list[str] = []
        invalid_due: list[str] = []
        for task in tasks:
            if task.scheduled:
                scheduled = parse_taskwarrior_datetime(task.scheduled)
                if scheduled is None or not calendar.is_working_time(scheduled):
                    invalid_scheduled.append(task.short_uuid)
            if task.due:
                due = parse_taskwarrior_datetime(task.due)
                if due is None:
                    invalid_due.append(task.short_uuid)
                elif due.hour == 0 and due.minute == 0 and due.second == 0:
                    try:
                        calendar.deadline_for_date(due.date().isoformat())
                    except ValueError:
                        invalid_due.append(task.short_uuid)
                elif not calendar.is_working_time(due):
                    invalid_due.append(task.short_uuid)

        overtracked = sorted(
            (
                task.short_uuid,
                tracked.get(task.uuid, 0.0) - task.estimate_hours,
            )
            for task in tasks
            if task.has_estimate
            and tracked.get(task.uuid, 0.0) > task.estimate_hours
        )

        projected_late: list[tuple[str, float]] = []
        if not graph.cyclic:
            schedule = build_absolute_schedule(
                graph,
                resolved_settings,
                now=resolved_now,
                tracked_hours=tracked_hours,
                origin=resolved_now,
            )
            assert schedule is not None
            projected_late = sorted(
                (
                    graph.by_uuid[uuid].short_uuid,
                    hours,
                )
                for uuid, hours in schedule.late_by.items()
            )

        issue_count = (
            len(graph.cycle_nodes)
            + len(graph.blocked_by_cycle)
            + len(graph.unresolved)
            + len(unestimated)
            + len(invalid_scheduled)
            + len(invalid_due)
            + len(projected_late)
            + len(overtracked)
        )

        lines = [
            "Planning health",
            (
                f"Tasks: {len(tasks)} | Cycle nodes: {len(graph.cycle_nodes)} | "
                f"Blocked by cycle: {len(graph.blocked_by_cycle)} | "
                f"Unresolved: {len(graph.unresolved)}"
            ),
            (
                f"Unestimated: {len(unestimated)} | "
                f"Invalid scheduled: {len(invalid_scheduled)} | "
                f"Invalid due: {len(invalid_due)} | "
                f"Projected late: {len(projected_late)} | "
                f"Overtracked: {len(overtracked)}"
            ),
            "Health: clean" if issue_count == 0 else f"Health: {issue_count} issue(s)",
        ]

        if graph.cycle_nodes:
            lines.append(
                "Cycle nodes: "
                + ", ".join(
                    graph.by_uuid[uuid].short_uuid
                    for uuid in sorted(
                        graph.cycle_nodes,
                        key=lambda item: (graph.by_uuid[item].short_uuid, item),
                    )
                )
            )
        if graph.blocked_by_cycle:
            lines.append(
                "Blocked by cycle: "
                + ", ".join(
                    graph.by_uuid[uuid].short_uuid
                    for uuid in sorted(
                        graph.blocked_by_cycle,
                        key=lambda item: (graph.by_uuid[item].short_uuid, item),
                    )
                )
            )
        if graph.unresolved:
            lines.append(
                "Unresolved dependencies: "
                + "; ".join(
                    f"{task_uuid} -> {dependency_uuid}"
                    for task_uuid, dependency_uuid in graph.unresolved
                )
            )
        if unestimated:
            lines.append("Unestimated tasks: " + ", ".join(unestimated))
        if invalid_scheduled:
            lines.append(
                "Invalid scheduled: " + ", ".join(sorted(invalid_scheduled))
            )
        if invalid_due:
            lines.append("Invalid due: " + ", ".join(sorted(invalid_due)))
        if projected_late:
            lines.append(
                "Projected late tasks: "
                + "; ".join(
                    f"{uuid} +{hours:.2f}h"
                    for uuid, hours in projected_late
                )
            )
        if overtracked:
            lines.append(
                "Overtracked estimates: "
                + "; ".join(
                    f"{uuid} +{hours:.2f}h"
                    for uuid, hours in overtracked
                )
            )

        return "\n".join(lines)

    @staticmethod
    def _schedule_proposal(
        project: str,
        project_tasks: list[Task],
        expanded_tasks: list[Task],
        settings: PlanningSettings | None = None,
        *,
        now: datetime | None = None,
        tracked_hours: dict[str, float] | None = None,
    ) -> tuple[str, dict[str, str]]:
        """Build an auto-schedule preview for unscheduled inactive project tasks."""
        resolved_settings = settings or PlanningSettings()
        resolved_now = now or datetime.now(UTC)
        graph = build_planning_graph(expanded_tasks)
        if graph.cyclic:
            return "Auto-schedule unavailable: dependency cycle detected.", {}

        schedule = build_absolute_schedule(
            graph,
            resolved_settings,
            now=resolved_now,
            tracked_hours=tracked_hours,
            origin=resolved_now,
        )
        assert schedule is not None

        project_uuids = {task.uuid for task in project_tasks}
        changes: dict[str, str] = {}
        rows: list[str] = []
        for task in sorted(
            project_tasks,
            key=lambda item: (item.short_uuid, item.uuid),
        ):
            if (
                task.uuid not in schedule.starts
                or task.scheduled
                or task.active
                or task.status in {"completed", "deleted"}
            ):
                continue
            proposed = schedule.starts[task.uuid]
            changes[task.uuid] = proposed.strftime("%Y%m%dT%H%M%SZ")
            rows.append(
                f"{task.short_uuid} | — | {proposed:%Y-%m-%d %H:%M} UTC | "
                f"{task.description}"
            )

        lines = [
            f"Auto-schedule proposal: {project or '(none)'}",
            f"Planning origin: {schedule.origin:%Y-%m-%d %H:%M} UTC",
            f"Project tasks to schedule: {len(changes)}",
        ]
        if changes:
            lines.extend(
                [
                    "",
                    "UUID | Current scheduled | Proposed scheduled | Description",
                    *rows,
                ]
            )
        else:
            lines.extend(
                [
                    "",
                    "No unscheduled inactive project tasks require changes.",
                ]
            )

        external = sum(
            task.uuid not in project_uuids
            for task in expanded_tasks
        )
        if external:
            lines.append(f"External dependencies used for planning: {external}")
        return "\n".join(lines), changes

    @staticmethod
    def _project_dashboard(
        project: str,
        project_tasks: list[Task],
        expanded_tasks: list[Task],
        settings: PlanningSettings | None = None,
        *,
        now: datetime | None = None,
        tracked_hours: dict[str, float] | None = None,
        include_tasks: bool = True,
    ) -> str:
        """Consolidate project effort, dependencies, and calendar planning."""
        if not project_tasks:
            return "No tasks in project."

        resolved_settings = settings or PlanningSettings()
        resolved_now = now or datetime.now(UTC)
        calendar = WorkingCalendar(resolved_settings)
        tracked = tracked_hours or {}
        project_uuids = {task.uuid for task in project_tasks}

        estimate = sum(task.estimate_hours for task in project_tasks)
        tracked_total = sum(tracked.get(task.uuid, 0.0) for task in project_tasks)
        remaining = sum(
            remaining_estimate_hours(
                task,
                calendar,
                resolved_now,
                tracked_hours,
            )
            for task in project_tasks
        )
        active = sum(task.active for task in project_tasks)
        blocked = sum(bool(task.depends) for task in project_tasks)
        unestimated = sum(not task.has_estimate for task in project_tasks)
        external_count = sum(task.uuid not in project_uuids for task in expanded_tasks)

        graph = build_planning_graph(expanded_tasks)
        resolved_edges = sum(len(values) for values in graph.dependencies.values())
        graph_state = "cycle" if graph.cyclic else "acyclic"

        lines = [
            f"Project: {project or '(none)'}",
            (
                f"Project tasks: {len(project_tasks)} | "
                f"External dependencies: {external_count} | "
                f"Active: {active} | Blocked: {blocked} | "
                f"Unestimated: {unestimated}"
            ),
            (
                f"Estimate: {estimate:.2f}h | Tracked: {tracked_total:.2f}h | "
                f"Remaining: {remaining:.2f}h"
            ),
            (
                f"Dependency graph: {graph_state} | Resolved edges: {resolved_edges} | "
                f"Unresolved: {len(graph.unresolved)}"
            ),
        ]

        if graph.cyclic:
            lines.extend(
                [
                    "Graph remaining duration: unavailable (cycle)",
                    "Critical path: unavailable (cycle)",
                    "Planned finish: unavailable (cycle)",
                ]
            )
        else:
            relative = build_relative_schedule(
                graph,
                resolved_settings,
                now=resolved_now,
                tracked_hours=tracked_hours,
            )
            assert relative is not None
            lines.append(f"Graph remaining duration: {relative.duration:.2f}h")

            terminal = min(
                (
                    uuid
                    for uuid in graph.order
                    if abs(
                        relative.earliest_finish[uuid] - relative.duration
                    ) < 1e-9
                ),
                key=lambda uuid: (
                    graph.by_uuid[uuid].short_uuid,
                    uuid,
                ),
            )
            path = [terminal]
            current = terminal
            while graph.dependencies[current]:
                predecessors = sorted(
                    (
                        dependency
                        for dependency in graph.dependencies[current]
                        if dependency in relative.critical
                        and abs(
                            relative.earliest_finish[dependency]
                            - relative.earliest_start[current]
                        ) < 1e-9
                    ),
                    key=lambda uuid: (
                        graph.by_uuid[uuid].short_uuid,
                        uuid,
                    ),
                )
                current = predecessors[0]
                path.append(current)
            path.reverse()
            lines.append(
                "Critical path: "
                + " -> ".join(
                    graph.by_uuid[uuid].short_uuid
                    for uuid in path
                )
            )
            absolute = build_absolute_schedule(
                graph,
                resolved_settings,
                now=resolved_now,
                tracked_hours=tracked_hours,
            )
            if absolute is None:
                lines.append("Planned finish: unavailable (no calendar anchor)")
            else:
                project_finishes = [
                    absolute.finishes[uuid]
                    for uuid in project_uuids
                    if uuid in absolute.finishes
                ]
                finish = max(project_finishes)
                late_project_tasks = sum(
                    uuid in absolute.late_by
                    for uuid in project_uuids
                )
                lines.append(
                    f"Planned finish: {finish:%Y-%m-%d %H:%M} UTC | "
                    f"Late project tasks: {late_project_tasks}"
                )

        if graph.unresolved:
            lines.append(
                "Unresolved dependencies: "
                + "; ".join(
                    f"{task_uuid} -> {dependency_uuid}"
                    for task_uuid, dependency_uuid in graph.unresolved
                )
            )

        if not include_tasks:
            return "\n".join(lines)

        lines.extend(
            [
                "",
                "Tasks",
                (
                    "UUID | Scope | State | Estimate | Tracked | Remaining | "
                    "Due | Description"
                ),
            ]
        )
        for task in sorted(
            expanded_tasks,
            key=lambda item: (
                item.uuid not in project_uuids,
                item.project.casefold(),
                item.short_uuid,
                item.uuid,
            ),
        ):
            if task.uuid in project_uuids:
                scope = "project"
            else:
                scope = f"external:{task.project or '(none)'}"
            state = "active" if task.active else task.status
            estimate_text = task.display_estimate or "—"
            tracked_value = tracked.get(task.uuid, 0.0)
            remaining_value = (
                f"{remaining_estimate_hours(task, calendar, resolved_now, tracked_hours):.2f}h"
                if task.has_estimate
                else "—"
            )
            due = task.display_due or "—"
            lines.append(
                f"{task.short_uuid} | {scope} | {state} | {estimate_text} | "
                f"{tracked_value:.2f}h | {remaining_value} | {due} | "
                f"{task.description}"
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
