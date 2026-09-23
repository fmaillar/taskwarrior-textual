"""Domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


def format_taskwarrior_datetime(value: str) -> str:
    """Format Taskwarrior's compact UTC timestamp for humans."""
    if not value:
        return ""
    try:
        dt = datetime.strptime(value, "%Y%m%dT%H%M%SZ")
    except ValueError:
        return value
    if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
        return dt.strftime("%Y-%m-%d")
    return dt.strftime("%Y-%m-%d %H:%M")


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

    @property
    def display_due(self) -> str:
        """Return a compact human-readable due date."""
        return format_taskwarrior_datetime(self.due)

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
