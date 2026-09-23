from datetime import UTC, datetime

import pytest

from taskwarrior_textual.config import PlanningSettings, WorkingCalendar


def test_planning_settings_defaults_match_defined_global_semantics() -> None:
    settings = PlanningSettings()

    assert settings.timezone == "local"
    assert settings.workdays == (0, 1, 2, 3, 4)
    assert settings.work_periods == (("08:00", "12:00"), ("13:00", "17:00"))
    assert settings.holidays == ()
    assert settings.dependency_depth == 10
    assert settings.capacity is None
    assert settings.hours_per_day == 8.0


@pytest.mark.parametrize("timezone", ["local", "UTC", "Europe/Paris"])
def test_planning_settings_accept_supported_timezone_names(timezone: str) -> None:
    assert PlanningSettings(timezone=timezone).timezone == timezone


def test_planning_settings_rejects_unknown_timezone() -> None:
    with pytest.raises(ValueError, match="timezone"):
        PlanningSettings(timezone="Mars/Olympus")


@pytest.mark.parametrize(
    "workdays",
    [
        (-1, 0, 1),
        (0, 1, 7),
        (0, 1, 1),
    ],
)


def test_planning_settings_rejects_invalid_workdays(workdays: tuple[int, ...]) -> None:
    with pytest.raises(ValueError, match="workdays"):
        PlanningSettings(workdays=workdays)


@pytest.mark.parametrize(
    "work_periods",
    [
        (("12:00", "08:00"),),
        (("08:00", "12:00"), ("11:00", "13:00")),
        (("8am", "12:00"),),
    ],
)


def test_planning_settings_rejects_invalid_work_periods(
    work_periods: tuple[tuple[str, str], ...],
) -> None:
    with pytest.raises(ValueError, match="work periods"):
        PlanningSettings(work_periods=work_periods)


def test_planning_settings_accepts_configurable_holidays() -> None:
    settings = PlanningSettings(holidays=("2026-12-25", "2026-12-31"))
    assert settings.holidays == ("2026-12-25", "2026-12-31")


def test_planning_settings_rejects_invalid_holiday() -> None:
    with pytest.raises(ValueError, match="holiday"):
        PlanningSettings(holidays=("25/12/2026",))


@pytest.mark.parametrize("depth", [-1, 0, 1, 10])
def test_planning_settings_accepts_dependency_depth_modes(depth: int) -> None:
    assert PlanningSettings(dependency_depth=depth).dependency_depth == depth


def test_planning_settings_rejects_dependency_depth_below_unlimited_sentinel() -> None:
    with pytest.raises(ValueError, match="dependency depth"):
        PlanningSettings(dependency_depth=-2)


@pytest.mark.parametrize("capacity", [None, 1, 2, 8])
def test_planning_settings_accepts_unlimited_or_positive_capacity(
    capacity: int | None,
) -> None:
    assert PlanningSettings(capacity=capacity).capacity == capacity


@pytest.mark.parametrize("capacity", [0, -1])
def test_planning_settings_rejects_nonpositive_capacity(capacity: int) -> None:
    with pytest.raises(ValueError, match="capacity"):
        PlanningSettings(capacity=capacity)


def test_working_calendar_recognizes_work_periods_and_holidays() -> None:
    calendar = WorkingCalendar(
        PlanningSettings(
            timezone="UTC",
            holidays=("2026-09-24",),
        )
    )

    assert calendar.is_working_time(datetime(2026, 9, 23, 8, 0, tzinfo=UTC)) is True
    assert calendar.is_working_time(datetime(2026, 9, 23, 12, 30, tzinfo=UTC)) is False
    assert calendar.is_working_time(datetime(2026, 9, 23, 17, 0, tzinfo=UTC)) is False
    assert calendar.is_working_time(datetime(2026, 9, 24, 9, 0, tzinfo=UTC)) is False
    assert calendar.is_working_time(datetime(2026, 9, 26, 9, 0, tzinfo=UTC)) is False


def test_working_calendar_moves_to_next_valid_work_instant() -> None:
    calendar = WorkingCalendar(PlanningSettings(timezone="UTC"))

    assert calendar.next_working_time(datetime(2026, 9, 23, 12, 30, tzinfo=UTC)) == datetime(
        2026, 9, 23, 13, 0, tzinfo=UTC
    )
    assert calendar.next_working_time(datetime(2026, 9, 25, 17, 30, tzinfo=UTC)) == datetime(
        2026, 9, 28, 8, 0, tzinfo=UTC
    )


def test_working_calendar_adds_hours_across_breaks_and_weekends() -> None:
    calendar = WorkingCalendar(PlanningSettings(timezone="UTC"))

    assert calendar.add_working_hours(datetime(2026, 9, 25, 15, 0, tzinfo=UTC), 8) == datetime(
        2026, 9, 28, 15, 0, tzinfo=UTC
    )
    assert calendar.add_working_hours(datetime(2026, 9, 23, 11, 0, tzinfo=UTC), 3) == datetime(
        2026, 9, 23, 15, 0, tzinfo=UTC
    )


def test_working_calendar_zero_duration_keeps_valid_instant_and_normalizes_invalid_one() -> None:
    calendar = WorkingCalendar(PlanningSettings(timezone="UTC"))

    assert calendar.add_working_hours(datetime(2026, 9, 23, 10, 0, tzinfo=UTC), 0) == datetime(
        2026, 9, 23, 10, 0, tzinfo=UTC
    )
    assert calendar.add_working_hours(datetime(2026, 9, 23, 12, 30, tzinfo=UTC), 0) == datetime(
        2026, 9, 23, 13, 0, tzinfo=UTC
    )


def test_working_calendar_rejects_negative_work_duration() -> None:
    calendar = WorkingCalendar(PlanningSettings(timezone="UTC"))

    with pytest.raises(ValueError, match="non-negative"):
        calendar.add_working_hours(datetime(2026, 9, 23, 10, 0, tzinfo=UTC), -1)


def test_working_calendar_date_deadline_is_end_of_last_work_period() -> None:
    calendar = WorkingCalendar(PlanningSettings(timezone="UTC"))

    assert calendar.deadline_for_date("2026-09-25") == datetime(2026, 9, 25, 17, 0, tzinfo=UTC)


def test_working_calendar_rejects_nonworking_date_deadline() -> None:
    calendar = WorkingCalendar(PlanningSettings(timezone="UTC"))

    with pytest.raises(ValueError, match="non-working"):
        calendar.deadline_for_date("2026-09-27")


def test_planning_settings_requires_workdays_and_work_periods() -> None:
    with pytest.raises(ValueError, match="workdays"):
        PlanningSettings(workdays=())

    with pytest.raises(ValueError, match="work periods"):
        PlanningSettings(work_periods=())
