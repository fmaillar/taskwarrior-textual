"""Global planning configuration and validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
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
            total_seconds += (
                datetime.combine(date.min, end, tzinfo=UTC)
                - datetime.combine(date.min, start, tzinfo=UTC)
            ).total_seconds()
        return total_seconds / 3600



@dataclass(frozen=True, slots=True)
class WorkingCalendar:
    """Working-time arithmetic driven by global planning settings."""

    settings: PlanningSettings

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
                    datetime.combine(value, start_time, tzinfo=UTC),
                    datetime.combine(value, end_time, tzinfo=UTC),
                )
            )
        return tuple(sorted(periods))

    def is_working_time(self, value: datetime) -> bool:
        """Return whether a datetime lies inside a configured working period."""
        return any(start <= value < end for start, end in self._periods_for_date(value.date()))

    def next_working_time(self, value: datetime) -> datetime:
        """Return value itself when valid, otherwise the next working instant."""
        if self.is_working_time(value):
            return value

        day = value.date()
        probe = value
        while True:
            for start, _ in self._periods_for_date(day):
                if start >= probe:
                    return start
            day += timedelta(days=1)
            probe = datetime.combine(day, time.min, tzinfo=UTC)

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
                for period_start, end in self._periods_for_date(current.date())
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
