"""Taskwarrior CLI adapter."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Sequence

from .models import Task


class TaskwarriorError(RuntimeError):
    """Raised when the Taskwarrior CLI cannot be used successfully."""


@dataclass(slots=True)
class TaskwarriorClient:
    """Thin adapter around the public Taskwarrior CLI."""

    command: str | None = None

    def __post_init__(self) -> None:
        if self.command is None:
            self.command = os.environ.get("TASKWARRIOR_COMMAND") or shutil.which("task")
        if not self.command:
            raise TaskwarriorError(
                "Taskwarrior executable not found. Put 'task' in PATH or set "
                "TASKWARRIOR_COMMAND."
            )

    def _run(self, args: Sequence[str]) -> str:
        command = [self.command, *args]
        try:
            completed = subprocess.run(command, check=False, capture_output=True, text=True)
        except OSError as exc:
            raise TaskwarriorError(f"Cannot execute {shlex.join(command)}: {exc}") from exc

        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip()
            raise TaskwarriorError(
                f"{shlex.join(command)} failed with status {completed.returncode}: {message}"
            )
        return completed.stdout

    def export(self, *filters: str) -> list[Task]:
        """Return tasks matching Taskwarrior filters."""
        raw = self._run([*filters, "export"])
        try:
            payload: Any = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise TaskwarriorError("Taskwarrior returned invalid JSON") from exc
        if not isinstance(payload, list):
            raise TaskwarriorError("Taskwarrior export did not return a JSON array")
        return [Task.from_export(item) for item in payload]

    def pending(self) -> list[Task]:
        """Return pending tasks."""
        return self.export("status:pending")

    def information(self, uuid_prefix: str) -> str:
        """Return Taskwarrior's human-readable task information."""
        return self._run([uuid_prefix])

    @staticmethod
    def _attributes(
        *,
        project: str = "",
        priority: str = "",
        due: str = "",
        include_empty: bool = False,
    ) -> list[str]:
        values = {"project": project, "priority": priority, "due": due}
        return [
            f"{name}:{value}"
            for name, value in values.items()
            if include_empty or value
        ]

    def add(
        self,
        description: str,
        *,
        project: str = "",
        priority: str = "",
        due: str = "",
    ) -> str:
        """Create a task and return Taskwarrior's response."""
        return self._run(
            [
                "add",
                description,
                *self._attributes(project=project, priority=priority, due=due),
            ]
        )

    def modify(
        self,
        uuid_prefix: str,
        description: str,
        *,
        project: str = "",
        priority: str = "",
        due: str = "",
    ) -> str:
        """Replace the main editable fields of a task."""
        return self._run(
            [
                uuid_prefix,
                "modify",
                f"description:{description}",
                *self._attributes(
                    project=project,
                    priority=priority,
                    due=due,
                    include_empty=True,
                ),
            ]
        )

    def start(self, uuid_prefix: str) -> str:
        """Start a task (and Timewarrior when its hook is installed)."""
        return self._run([uuid_prefix, "start"])

    def stop(self, uuid_prefix: str) -> str:
        """Stop a task."""
        return self._run([uuid_prefix, "stop"])

    def done(self, uuid_prefix: str) -> str:
        """Mark a task as completed."""
        return self._run([uuid_prefix, "done"])

    def delete(self, uuid_prefix: str) -> str:
        """Mark a task as deleted without Taskwarrior's CLI prompt."""
        return self._run([uuid_prefix, "delete", "rc.confirmation=off"])

    def sync(self) -> str:
        """Synchronize the local Taskwarrior replica."""
        return self._run(["sync"])
