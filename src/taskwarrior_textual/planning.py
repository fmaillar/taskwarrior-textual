"""Shared dependency graph primitives for planning views."""

from __future__ import annotations

from dataclasses import dataclass

from .models import Task


@dataclass(frozen=True, slots=True)
class PlanningGraph:
    """Resolved dependency graph plus deterministic topological information."""

    by_uuid: dict[str, Task]
    dependencies: dict[str, frozenset[str]]
    successors: dict[str, frozenset[str]]
    order: tuple[str, ...]
    remaining: tuple[str, ...]
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

    remaining = set(by_uuid)
    order: list[str] = []
    while remaining:
        ready = sorted(
            (
                uuid
                for uuid in remaining
                if not (dependency_sets[uuid] & remaining)
            ),
            key=lambda uuid: by_uuid[uuid].short_uuid,
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
            sorted(remaining, key=lambda uuid: by_uuid[uuid].short_uuid)
        ),
        unresolved=tuple(sorted(unresolved)),
    )



def build_relative_schedule(graph: PlanningGraph) -> RelativeSchedule | None:
    """Compute earliest/latest timing and slack for an acyclic graph."""
    if graph.cyclic:
        return None

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
        earliest_finish[uuid] = start + graph.by_uuid[uuid].estimate_hours

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
        latest_start[uuid] = finish - graph.by_uuid[uuid].estimate_hours

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
