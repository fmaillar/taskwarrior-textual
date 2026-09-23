"""Global planning configuration and validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


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
        if (
            len(set(self.workdays)) != len(self.workdays)
            or any(day < 0 or day > 6 for day in self.workdays)
        ):
            raise ValueError("workdays must contain unique weekday numbers from 0 to 6")

    @staticmethod
    def _parse_clock(value: str) -> datetime:
        try:
            return datetime.strptime(value, "%H:%M")
        except ValueError as exc:
            raise ValueError(f"invalid work periods clock value: {value}") from exc

    def _validate_work_periods(self) -> None:
        parsed: list[tuple[datetime, datetime]] = []
        for start_text, end_text in self.work_periods:
            start = self._parse_clock(start_text)
            end = self._parse_clock(end_text)
            if end <= start:
                raise ValueError("work periods must end after they start")
            parsed.append((start, end))

        parsed.sort(key=lambda period: period[0])
        for (_, previous_end), (next_start, _) in zip(parsed, parsed[1:]):
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
            total_seconds += (end - start).total_seconds()
        return total_seconds / 3600
