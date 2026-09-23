"""Domain models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Task:
    """Small, UI-oriented representation of a Taskwarrior task."""

    uuid: str
    description: str
    status: str
    project: str = ""
    priority: str = ""
    due: str = ""
    urgency: float = 0.0

    @property
    def short_uuid(self) -> str:
        """Return an eight-character UUID prefix, Git-style."""
        return self.uuid[:8]

    @classmethod
    def from_export(cls, value: dict[str, Any]) -> "Task":
        """Build a task from one object returned by task export."""
        return cls(
            uuid=str(value["uuid"]),
            description=str(value.get("description", "")),
            status=str(value.get("status", "")),
            project=str(value.get("project", "")),
            priority=str(value.get("priority", "")),
            due=str(value.get("due", "")),
            urgency=float(value.get("urgency", 0.0)),
        )
