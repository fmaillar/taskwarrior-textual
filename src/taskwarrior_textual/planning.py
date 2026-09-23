"""Shared dependency graph primitives for planning views."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from .config import PlanningSettings, WorkingCalendar
from .models import Task


@dataclass(frozen=True, slots=True)
class PlanningGraph:
    """Resolved dependency graph plus deterministic topological information."""

    by_uuid: dict[str, Task]
    dependencies: dict[str, frozenset[str]]
    successors: dict[str, frozenset[str]]
    order: tuple[str, ...]
    remaining: tuple[str, ...]
    cycle_nodes: frozenset[str]
    blocked_by_cycle: frozenset[str]
    unresolved: tuple[tuple[str, str], ...]

    @property
    def cyclic(self) -> bool:
        """Whether the graph contains a dependency cycle."""
        return bool(self.remaining)


@dataclass(frozen=True, slots=True)
class RelativeSchedule:
    """CPM-style relative schedule over an acyclic planning graph."""

    graph: PlanningGraph
    earliest_start: dict[str, float]
    earliest_finish: dict[str, float]
    latest_start: dict[str, float]
    slack: dict[str, float]
    critical: frozenset[str]
    duration: float


@dataclass(frozen=True, slots=True)
class AbsoluteSchedule:
    """Absolute UTC schedule honoring dependencies and scheduled constraints."""

    graph: PlanningGraph
    origin: datetime
    starts: dict[str, datetime]
    finishes: dict[str, datetime]
    late_by: dict[str, float]
    due_slack: dict[str, float]
    invalid_due: tuple[str, ...]
    invalid_scheduled: tuple[str, ...]


def build_planning_graph(tasks: list[Task]) -> PlanningGraph:
    """Resolve in-view dependencies and compute a deterministic topological order."""
    by_uuid = {task.uuid: task for task in tasks}
    dependency_sets: dict[str, set[str]] = {task.uuid: set() for task in tasks}
    successor_sets: dict[str, set[str]] = {task.uuid: set() for task in tasks}
    unresolved: list[tuple[str, str]] = []

    for task in tasks:
        for dependency in task.depends:
            if dependency in by_uuid:
                dependency_sets[task.uuid].add(dependency)
                successor_sets[dependency].add(task.uuid)
            else:
                unresolved.append((task.short_uuid, dependency[:8]))

    index = 0
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    cycle_nodes: set[str] = set()

    def visit(uuid: str) -> None:
        nonlocal index
        indices[uuid] = index
        lowlink[uuid] = index
        index += 1
        stack.append(uuid)
        on_stack.add(uuid)

        for successor in successor_sets[uuid]:
            if successor not in indices:
                visit(successor)
                lowlink[uuid] = min(lowlink[uuid], lowlink[successor])
            elif successor in on_stack:
                lowlink[uuid] = min(lowlink[uuid], indices[successor])

        if lowlink[uuid] != indices[uuid]:
            return

        component: list[str] = []
        while True:
            member = stack.pop()
            on_stack.remove(member)
            component.append(member)
            if member == uuid:
                break

        if len(component) > 1:
            cycle_nodes.update(component)
        elif component[0] in dependency_sets[component[0]]:
            cycle_nodes.add(component[0])

    for uuid in sorted(by_uuid):
        if uuid not in indices:
            visit(uuid)

    remaining = set(by_uuid)
    order: list[str] = []
    while remaining:
        ready = sorted(
            (
                uuid
                for uuid in remaining
                if not (dependency_sets[uuid] & remaining)
            ),
            key=lambda uuid: (by_uuid[uuid].short_uuid, uuid),
        )
        if not ready:
            break
        order.extend(ready)
        remaining.difference_update(ready)

    return PlanningGraph(
        by_uuid=by_uuid,
        dependencies={
            uuid: frozenset(values)
            for uuid, values in dependency_sets.items()
        },
        successors={
            uuid: frozenset(values)
            for uuid, values in successor_sets.items()
        },
        order=tuple(order),
        remaining=tuple(
            sorted(remaining, key=lambda uuid: (by_uuid[uuid].short_uuid, uuid))
        ),
        cycle_nodes=frozenset(cycle_nodes),
        blocked_by_cycle=frozenset(remaining - cycle_nodes),
        unresolved=tuple(sorted(unresolved)),
    )


def remaining_estimate_hours(
    task: Task,
    calendar: WorkingCalendar,
    now: datetime,
    tracked_hours: dict[str, float] | None = None,
) -> float:
    """Return future work remaining for one task."""
    if task.status in {"completed", "deleted"}:
        return 0.0
    if tracked_hours is not None and task.uuid in tracked_hours:
        return max(0.0, task.estimate_hours - tracked_hours[task.uuid])
    if not task.active:
        return task.estimate_hours

    started = parse_taskwarrior_datetime(task.start)
    if started is None or started >= now:
        return task.estimate_hours

    elapsed = calendar.working_hours_between(started, now)
    return max(0.0, task.estimate_hours - elapsed)


def build_relative_schedule(
    graph: PlanningGraph,
    settings: PlanningSettings | None = None,
    *,
    now: datetime | None = None,
    tracked_hours: dict[str, float] | None = None,
) -> RelativeSchedule | None:
    """Compute earliest/latest timing and slack from remaining future work."""
    if graph.cyclic:
        return None

    resolved_settings = settings or PlanningSettings()
    calendar = WorkingCalendar(resolved_settings)
    resolved_now = now or datetime.now(UTC)
    remaining_hours = {
        uuid: remaining_estimate_hours(
            task,
            calendar,
            resolved_now,
            tracked_hours,
        )
        for uuid, task in graph.by_uuid.items()
    }

    earliest_start: dict[str, float] = {}
    earliest_finish: dict[str, float] = {}
    for uuid in graph.order:
        start = max(
            (
                earliest_finish[dependency]
                for dependency in graph.dependencies[uuid]
            ),
            default=0.0,
        )
        earliest_start[uuid] = start
        earliest_finish[uuid] = start + remaining_hours[uuid]

    duration = max(earliest_finish.values(), default=0.0)
    latest_start: dict[str, float] = {}
    for uuid in reversed(graph.order):
        if graph.successors[uuid]:
            finish = min(
                latest_start[successor]
                for successor in graph.successors[uuid]
            )
        else:
            finish = duration
        latest_start[uuid] = finish - remaining_hours[uuid]

    slack = {
        uuid: latest_start[uuid] - earliest_start[uuid]
        for uuid in graph.order
    }
    critical = frozenset(
        uuid for uuid in graph.order if abs(slack[uuid]) < 1e-9
    )

    return RelativeSchedule(
        graph=graph,
        earliest_start=earliest_start,
        earliest_finish=earliest_finish,
        latest_start=latest_start,
        slack=slack,
        critical=critical,
        duration=duration,
    )


def parse_taskwarrior_datetime(value: str) -> datetime | None:
    """Parse a Taskwarrior UTC timestamp used by planning calculations."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y%m%dT%H%M%S%z")
    except ValueError:
        return None


def _capacity_allows(
    start: datetime,
    finish: datetime,
    reservations: list[tuple[datetime, datetime]],
    capacity: int,
) -> bool:
    """Return whether one more task fits without exceeding capacity."""
    points = {start}
    for reserved_start, reserved_finish in reservations:
        if reserved_start < finish and reserved_finish > start:
            points.add(max(start, reserved_start))

    return all(
        sum(
            reserved_start <= point < reserved_finish
            for reserved_start, reserved_finish in reservations
        )
        < capacity
        for point in points
    )


def _capacity_constrained_start(
    calendar: WorkingCalendar,
    earliest: datetime,
    hours: float,
    capacity: int | None,
    reservations: list[tuple[datetime, datetime]],
) -> datetime:
    """Return the earliest working start that fits available capacity."""
    start = calendar.next_working_time(earliest)
    if capacity is None or hours == 0:
        return start

    while True:
        finish = calendar.add_working_hours(start, hours)
        if _capacity_allows(start, finish, reservations, capacity):
            return start

        blocker_finishes = [
            reserved_finish
            for reserved_start, reserved_finish in reservations
            if reserved_start < finish and reserved_finish > start
        ]
        start = calendar.next_working_time(min(blocker_finishes))


def build_absolute_schedule(
    graph: PlanningGraph,
    settings: PlanningSettings | None = None,
    *,
    now: datetime | None = None,
    tracked_hours: dict[str, float] | None = None,
) -> AbsoluteSchedule | None:
    """Build an absolute UTC schedule using the configured working calendar."""
    if graph.cyclic:
        return None

    resolved_settings = settings or PlanningSettings()
    calendar = WorkingCalendar(resolved_settings)
    resolved_now = now or datetime.now(UTC)
    scheduled = {
        uuid: parse_taskwarrior_datetime(task.scheduled)
        for uuid, task in graph.by_uuid.items()
    }
    invalid_scheduled = sorted(
        task.short_uuid
        for uuid, task in graph.by_uuid.items()
        if task.scheduled
        and (
            scheduled[uuid] is None
            or not calendar.is_working_time(scheduled[uuid])
        )
    )
    invalid_scheduled_uuids = {
        uuid
        for uuid, task in graph.by_uuid.items()
        if task.scheduled
        and (
            scheduled[uuid] is None
            or not calendar.is_working_time(scheduled[uuid])
        )
    }
    anchors = [
        value
        for uuid, value in scheduled.items()
        if value is not None and uuid not in invalid_scheduled_uuids
    ]
    if any(task.active for task in graph.by_uuid.values()):
        anchors.append(resolved_now)
    if not anchors:
        return None
    origin = min(anchors)

    starts: dict[str, datetime] = {}
    finishes: dict[str, datetime] = {}
    late_by: dict[str, float] = {}
    due_slack: dict[str, float] = {}
    invalid_due: list[str] = []
    reservations: list[tuple[datetime, datetime]] = []

    for uuid in graph.order:
        if uuid in invalid_scheduled_uuids:
            continue

        dependencies = graph.dependencies[uuid]
        if any(dependency not in finishes for dependency in dependencies):
            continue

        task = graph.by_uuid[uuid]
        candidates = [origin]
        explicit_start = scheduled[uuid]
        if task.active:
            candidates.append(resolved_now)
        elif explicit_start is not None:
            candidates.append(explicit_start)
        candidates.extend(finishes[dependency] for dependency in dependencies)
        estimate_hours = _remaining_estimate_hours(
            task,
            calendar,
            resolved_now,
            tracked_hours,
        )
        start = _capacity_constrained_start(
            calendar,
            max(candidates),
            estimate_hours,
            resolved_settings.capacity,
            reservations,
        )
        finish = calendar.add_working_hours(start, estimate_hours)
        starts[uuid] = start
        finishes[uuid] = finish
        if finish > start:
            reservations.append((start, finish))

        raw_due = graph.by_uuid[uuid].due
        due = parse_taskwarrior_datetime(raw_due)
        if raw_due and due is None:
            invalid_due.append(graph.by_uuid[uuid].short_uuid)
            continue
        if due is None:
            continue

        if due.hour == 0 and due.minute == 0 and due.second == 0:
            try:
                deadline = calendar.deadline_for_date(due.date().isoformat())
            except ValueError:
                invalid_due.append(graph.by_uuid[uuid].short_uuid)
                continue
        else:
            if not calendar.is_working_time(due):
                invalid_due.append(graph.by_uuid[uuid].short_uuid)
                continue
            deadline = due

        slack_hours = (deadline - finish).total_seconds() / 3600
        due_slack[uuid] = slack_hours
        if slack_hours < 0:
            late_by[uuid] = -slack_hours

    return AbsoluteSchedule(
        graph=graph,
        origin=origin,
        starts=starts,
        finishes=finishes,
        late_by=late_by,
        due_slack=due_slack,
        invalid_due=tuple(sorted(invalid_due)),
        invalid_scheduled=tuple(invalid_scheduled),
    )
