"""Taskwarrior CLI adapter."""

from __future__ import annotations

import json
import math
import os
import shlex
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from .models import Task


class TaskwarriorError(RuntimeError):
    """Raised when the Taskwarrior CLI cannot be used successfully."""


VIEW_FILTERS = {
    "pending": "status:pending",
    "waiting": "status:waiting",
    "completed": "status:completed",
    "deleted": "status:deleted",
    "scheduled": "+SCHEDULED",
}


@dataclass(slots=True)
class TaskwarriorClient:
    """Thin adapter around the public Taskwarrior CLI."""

    command: str | None = None
    _udas_cache: frozenset[str] | None = field(default=None, init=False, repr=False)

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

    def view(self, name: str) -> list[Task]:
        """Return tasks from one of the supported named views."""
        try:
            task_filter = VIEW_FILTERS[name]
        except KeyError as exc:
            raise ValueError(f"Unknown task view: {name}") from exc
        return self.export(task_filter)

    def pending(self) -> list[Task]:
        """Return pending tasks."""
        return self.view("pending")

    def information(self, uuid_prefix: str) -> str:
        """Return Taskwarrior's human-readable task information."""
        return self._run([uuid_prefix])

    def udas(self) -> frozenset[str]:
        """Return configured Taskwarrior UDA names."""
        if self._udas_cache is None:
            self._udas_cache = frozenset(self._run(["_udas"]).split())
        return self._udas_cache

    def has_uda(self, name: str) -> bool:
        """Return whether a named UDA is configured."""
        return name in self.udas()

    @staticmethod
    def _parse_list(value: str) -> tuple[str, ...]:
        """Parse a comma-separated field, trimming and deduplicating entries."""
        return tuple(dict.fromkeys(part.strip() for part in value.split(",") if part.strip()))

    @classmethod
    def _attributes(
        cls,
        *,
        project: str = "",
        priority: str = "",
        due: str = "",
        wait: str = "",
        scheduled: str = "",
        depends: str = "",
        estimate: str = "",
        include_empty: bool = False,
        include_estimate: bool = True,
    ) -> list[str]:
        values = {
            "project": project,
            "priority": priority,
            "due": due,
            "wait": wait,
            "scheduled": scheduled,
            "depends": ",".join(cls._parse_list(depends)),
        }
        if include_estimate:
            values["estimate"] = estimate
        return [
            f"{name}:{value}"
            for name, value in values.items()
            if include_empty or value
        ]

    @classmethod
    def _tag_modifications(
        cls,
        tags: str,
        previous_tags: Sequence[str] = (),
    ) -> list[str]:
        """Return the minimal Taskwarrior +/- tag changes for a replacement set."""
        desired = cls._parse_list(tags)
        previous = tuple(dict.fromkeys(previous_tags))
        removed = [f"-{tag}" for tag in previous if tag not in desired]
        added = [f"+{tag}" for tag in desired if tag not in previous]
        return [*removed, *added]

    def _require_estimate_uda(self) -> None:
        if not self.has_uda("estimate"):
            raise TaskwarriorError(
                "The estimate UDA is not configured in Taskwarrior. "
                "Define uda.estimate before editing estimates."
            )

    @staticmethod
    def _validate_estimate(estimate: str) -> None:
        """Reject invalid, non-finite, or negative planning estimates."""
        try:
            value = float(estimate)
        except ValueError as exc:
            raise TaskwarriorError(
                "estimate must be a finite non-negative number of hours."
            ) from exc
        if not math.isfinite(value) or value < 0:
            raise TaskwarriorError(
                "estimate must be a finite non-negative number of hours."
            )

    def add(
        self,
        description: str,
        *,
        project: str = "",
        priority: str = "",
        due: str = "",
        tags: str = "",
        wait: str = "",
        scheduled: str = "",
        depends: str = "",
        estimate: str = "",
    ) -> str:
        """Create a task and return Taskwarrior's response."""
        include_estimate = bool(estimate)
        if include_estimate:
            self._require_estimate_uda()
            self._validate_estimate(estimate)
        return self._run(
            [
                "add",
                description,
                *self._attributes(
                    project=project,
                    priority=priority,
                    due=due,
                    wait=wait,
                    scheduled=scheduled,
                    depends=depends,
                    estimate=estimate,
                    include_estimate=include_estimate,
                ),
                *self._tag_modifications(tags),
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
        tags: str = "",
        previous_tags: Sequence[str] = (),
        wait: str = "",
        scheduled: str = "",
        depends: str = "",
        estimate: str = "",
    ) -> str:
        """Replace the editable fields of a task."""
        include_estimate = self.has_uda("estimate")
        if estimate and not include_estimate:
            self._require_estimate_uda()
        if estimate:
            self._validate_estimate(estimate)
        return self._run(
            [
                uuid_prefix,
                "modify",
                f"description:{description}",
                *self._attributes(
                    project=project,
                    priority=priority,
                    due=due,
                    wait=wait,
                    scheduled=scheduled,
                    depends=depends,
                    estimate=estimate,
                    include_empty=True,
                    include_estimate=include_estimate,
                ),
                *self._tag_modifications(tags, previous_tags),
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
