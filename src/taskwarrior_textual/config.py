"""Global planning configuration and validation."""

from __future__ import annotations

import itertools
import os
import tomllib
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class ConfigError(ValueError):
    """Invalid taskwarrior-textual configuration."""


def default_config_path() -> Path:
    """Return the configured or XDG-default TOML configuration path."""
    override = os.environ.get("TASKWARRIOR_TEXTUAL_CONFIG")
    if override:
        return Path(override).expanduser()
    root = Path(
        os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
    ).expanduser()
    return root / "taskwarrior-textual" / "config.toml"


@dataclass(frozen=True, slots=True)
class PlanningSettings:
    """Validated global scheduling semantics.

    Weekdays follow datetime.weekday(): Monday=0, Sunday=6.
    dependency_depth uses -1 for unlimited recursive expansion.
    capacity=None preserves unlimited CPM parallelism.
    """

    timezone: str = "local"
    workdays: tuple[int, ...] = (0, 1, 2, 3, 4)
    work_periods: tuple[tuple[str, str], ...] = (
        ("08:00", "12:00"),
        ("13:00", "17:00"),
    )
    holidays: tuple[str, ...] = ()
    dependency_depth: int = 10
    capacity: int | None = None

    def __post_init__(self) -> None:
        self._validate_timezone()
        self._validate_workdays()
        self._validate_work_periods()
        self._validate_holidays()
        if self.dependency_depth < -1:
            raise ValueError("dependency depth must be -1 (unlimited) or >= 0")
        if self.capacity is not None and self.capacity <= 0:
            raise ValueError("capacity must be None (unlimited) or a positive integer")

    def _validate_timezone(self) -> None:
        if self.timezone in {"local", "UTC"}:
            return
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown timezone: {self.timezone}") from exc

    def _validate_workdays(self) -> None:
        if not self.workdays:
            raise ValueError("workdays must not be empty")
        if (
            len(set(self.workdays)) != len(self.workdays)
            or any(day < 0 or day > 6 for day in self.workdays)
        ):
            raise ValueError("workdays must contain unique weekday numbers from 0 to 6")

    @staticmethod
    def _parse_clock(value: str) -> time:
        try:
            parsed = time.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"invalid work periods clock value: {value}") from exc
        if len(value) != 5 or value[2] != ":":
            raise ValueError(f"invalid work periods clock value: {value}")
        return parsed

    def _validate_work_periods(self) -> None:
        if not self.work_periods:
            raise ValueError("work periods must not be empty")
        parsed: list[tuple[time, time]] = []
        for start_text, end_text in self.work_periods:
            start = self._parse_clock(start_text)
            end = self._parse_clock(end_text)
            if end <= start:
                raise ValueError("work periods must end after they start")
            parsed.append((start, end))

        parsed.sort(key=lambda period: period[0])
        for (_, previous_end), (next_start, _) in itertools.pairwise(parsed):
            if next_start < previous_end:
                raise ValueError("work periods must not overlap")

    def _validate_holidays(self) -> None:
        for holiday in self.holidays:
            try:
                date.fromisoformat(holiday)
            except ValueError as exc:
                raise ValueError(f"invalid holiday date: {holiday}") from exc

    @property
    def hours_per_day(self) -> float:
        """Return total configured working hours in a standard workday."""
        total_seconds = 0.0
        for start_text, end_text in self.work_periods:
            start = self._parse_clock(start_text)
            end = self._parse_clock(end_text)
            total_seconds += (
                datetime.combine(date.min, end, tzinfo=UTC)
                - datetime.combine(date.min, start, tzinfo=UTC)
            ).total_seconds()
        return total_seconds / 3600


def load_planning_settings(path: Path | None = None) -> PlanningSettings:
    """Load validated planning settings from TOML, or return defaults if absent."""
    config_path = default_config_path() if path is None else Path(path)
    if not config_path.exists():
        return PlanningSettings()

    try:
        payload: Any = tomllib.loads(config_path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"invalid TOML configuration: {config_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ConfigError("configuration root must be a TOML table")

    planning = payload.get("planning", {})
    if not isinstance(planning, dict):
        raise ConfigError("planning must be a TOML table")

    allowed = {
        "timezone",
        "workdays",
        "work_periods",
        "holidays",
        "dependency_depth",
        "capacity",
    }
    unknown = sorted(set(planning) - allowed)
    if unknown:
        raise ConfigError(f"unknown planning key: {unknown[0]}")

    values: dict[str, Any] = {}
    if "timezone" in planning:
        timezone = planning["timezone"]
        if not isinstance(timezone, str):
            raise ConfigError("timezone must be a string")
        values["timezone"] = timezone

    if "workdays" in planning:
        workdays = planning["workdays"]
        if (
            not isinstance(workdays, list)
            or any(not isinstance(day, int) or isinstance(day, bool) for day in workdays)
        ):
            raise ConfigError("workdays must be an array of integers")
        values["workdays"] = tuple(workdays)

    if "work_periods" in planning:
        work_periods = planning["work_periods"]
        if not isinstance(work_periods, list):
            raise ConfigError("work_periods must be an array of [start, end] pairs")
        parsed_periods: list[tuple[str, str]] = []
        for period in work_periods:
            if (
                not isinstance(period, list)
                or len(period) != 2
                or any(not isinstance(value, str) for value in period)
            ):
                raise ConfigError("work_periods must be an array of [start, end] pairs")
            parsed_periods.append((period[0], period[1]))
        values["work_periods"] = tuple(parsed_periods)

    if "holidays" in planning:
        holidays = planning["holidays"]
        if (
            not isinstance(holidays, list)
            or any(not isinstance(value, str) for value in holidays)
        ):
            raise ConfigError("holidays must be an array of ISO date strings")
        values["holidays"] = tuple(holidays)

    if "dependency_depth" in planning:
        depth = planning["dependency_depth"]
        if not isinstance(depth, int) or isinstance(depth, bool):
            raise ConfigError("dependency_depth must be an integer")
        values["dependency_depth"] = depth

    if "capacity" in planning:
        capacity = planning["capacity"]
        if not isinstance(capacity, int) or isinstance(capacity, bool):
            raise ConfigError("capacity must be an integer")
        values["capacity"] = capacity

    try:
        return PlanningSettings(**values)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class WorkingCalendar:
    """Working-time arithmetic driven by global planning settings."""

    settings: PlanningSettings

    def _timezone(self) -> tzinfo:
        if self.settings.timezone == "UTC":
            return UTC
        if self.settings.timezone != "local":
            return ZoneInfo(self.settings.timezone)

        zoneinfo_root = Path("/usr/share/zoneinfo").resolve()
        localtime = Path("/etc/localtime").resolve()
        key = str(localtime.relative_to(zoneinfo_root))
        return ZoneInfo(key)

    @property
    def timezone(self) -> tzinfo:
        """Return the configured concrete timezone."""
        return self._timezone()

    def _localize(self, value: date, clock: time) -> datetime:
        zone = self._timezone()
        naive = datetime.combine(value, clock)
        first = naive.replace(tzinfo=zone, fold=0)
        second = naive.replace(tzinfo=zone, fold=1)

        def valid(candidate: datetime) -> bool:
            return (
                candidate.astimezone(UTC)
                .astimezone(zone)
                .replace(tzinfo=None)
                == naive
            )

        first_valid = valid(first)
        second_valid = valid(second)
        if not first_valid and not second_valid:
            raise ValueError(f"DST-nonexistent local time: {naive.isoformat()}")
        if first_valid and second_valid and first.utcoffset() != second.utcoffset():
            raise ValueError(f"DST-ambiguous local time: {naive.isoformat()}")
        return first

    def _local_date(self, value: datetime) -> date:
        return value.astimezone(self._timezone()).date()

    def _is_working_date(self, value: date) -> bool:
        return (
            value.weekday() in self.settings.workdays
            and value.isoformat() not in self.settings.holidays
        )

    def _periods_for_date(self, value: date) -> tuple[tuple[datetime, datetime], ...]:
        if not self._is_working_date(value):
            return ()
        periods = []
        for start_text, end_text in self.settings.work_periods:
            start_time = self.settings._parse_clock(start_text)
            end_time = self.settings._parse_clock(end_text)
            periods.append(
                (
                    self._localize(value, start_time).astimezone(UTC),
                    self._localize(value, end_time).astimezone(UTC),
                )
            )
        return tuple(sorted(periods))

    def is_working_time(self, value: datetime) -> bool:
        """Return whether a datetime lies inside a configured working period."""
        instant = value.astimezone(UTC)
        return any(
            start <= instant < end
            for start, end in self._periods_for_date(self._local_date(value))
        )

    def next_working_time(self, value: datetime) -> datetime:
        """Return value itself when valid, otherwise the next working instant."""
        if self.is_working_time(value):
            return value

        day = self._local_date(value)
        probe: datetime | None = value.astimezone(UTC)
        while True:
            for start, _ in self._periods_for_date(day):
                if probe is None or start >= probe:
                    return start
            day += timedelta(days=1)
            probe = None

    def working_hours_between(self, start: datetime, end: datetime) -> float:
        """Return configured working hours inside [start, end)."""
        if end <= start:
            return 0.0

        start_utc = start.astimezone(UTC)
        end_utc = end.astimezone(UTC)
        day = self._local_date(start_utc)
        last_day = self._local_date(end_utc)
        total_seconds = 0.0

        while day <= last_day:
            for period_start, period_end in self._periods_for_date(day):
                overlap_start = max(start_utc, period_start)
                overlap_end = min(end_utc, period_end)
                if overlap_end > overlap_start:
                    total_seconds += (overlap_end - overlap_start).total_seconds()
            day += timedelta(days=1)

        return total_seconds / 3600


    def add_working_hours(self, start: datetime, hours: float) -> datetime:
        """Add non-negative work duration, skipping breaks and non-working days."""
        if hours < 0:
            raise ValueError("working duration must be non-negative")

        current = self.next_working_time(start)
        if hours == 0:
            return current

        remaining = hours
        while True:
            period_end = next(
                end
                for period_start, end in self._periods_for_date(self._local_date(current))
                if period_start <= current < end
            )
            available = (period_end - current).total_seconds() / 3600
            if remaining <= available:
                return current + timedelta(hours=remaining)
            remaining -= available
            current = self.next_working_time(period_end)

    def deadline_for_date(self, value: str) -> datetime:
        """Return the end of the last work period for an ISO date."""
        target = date.fromisoformat(value)
        periods = self._periods_for_date(target)
        if not periods:
            raise ValueError(f"deadline date is non-working: {value}")
        return periods[-1][1]
