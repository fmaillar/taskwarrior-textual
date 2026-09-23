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
