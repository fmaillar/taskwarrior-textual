from datetime import UTC, datetime
from pathlib import Path

import pytest

from taskwarrior_textual.config import (
    ConfigError,
    PlanningSettings,
    WorkingCalendar,
    default_config_path,
    load_planning_settings,
)


def test_default_config_path_uses_explicit_env_override(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "custom.toml"
    monkeypatch.setenv("TASKWARRIOR_TEXTUAL_CONFIG", str(path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    assert default_config_path() == path


def test_default_config_path_uses_xdg_config_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("TASKWARRIOR_TEXTUAL_CONFIG", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    assert default_config_path() == tmp_path / "taskwarrior-textual" / "config.toml"


def test_load_planning_settings_returns_defaults_when_config_missing(tmp_path: Path) -> None:
    assert load_planning_settings(tmp_path / "missing.toml") == PlanningSettings()


def test_load_planning_settings_reads_planning_table(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        """
[planning]
timezone = "Europe/Paris"
workdays = [0, 1, 2, 3]
work_periods = [["07:30", "12:00"], ["13:00", "16:30"]]
holidays = ["2026-12-25"]
dependency_depth = -1
capacity = 2
""".strip()
    )

    settings = load_planning_settings(path)

    assert settings == PlanningSettings(
        timezone="Europe/Paris",
        workdays=(0, 1, 2, 3),
        work_periods=(("07:30", "12:00"), ("13:00", "16:30")),
        holidays=("2026-12-25",),
        dependency_depth=-1,
        capacity=2,
    )


def test_load_planning_settings_accepts_partial_planning_table(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[planning]\ntimezone = "UTC"\n')

    settings = load_planning_settings(path)

    assert settings.timezone == "UTC"
    assert settings.workdays == PlanningSettings().workdays
    assert settings.capacity is None


def test_load_planning_settings_ignores_other_top_level_tables(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[ui]\ncompact = true\n')

    assert load_planning_settings(path) == PlanningSettings()


@pytest.mark.parametrize(
    "content, message",
    [
        ("not = [valid", "TOML"),
        ('planning = "wrong"', "planning"),
        ('[planning]\nunknown = 1', "unknown planning key"),
        ('[planning]\ntimezone = 1', "timezone"),
        ('[planning]\nworkdays = "0,1,2"', "workdays"),
        ('[planning]\nwork_periods = "08:00-12:00"', "work_periods"),
        ('[planning]\nwork_periods = ["08:00-12:00"]', "work_periods"),
        ('[planning]\nholidays = [1]', "holidays"),
        ('[planning]\ndependency_depth = "ten"', "dependency_depth"),
        ('[planning]\ncapacity = "two"', "capacity"),
        ('[planning]\ntimezone = "Mars/Olympus"', "timezone"),
    ],
)
def test_load_planning_settings_rejects_invalid_config(
    tmp_path: Path,
    content: str,
    message: str,
) -> None:
    path = tmp_path / "config.toml"
    path.write_text(content)

    with pytest.raises(ConfigError, match=message):
        load_planning_settings(path)


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
        (("0800", "12:00"),),
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


def test_working_calendar_interprets_periods_in_configured_timezone() -> None:
    calendar = WorkingCalendar(PlanningSettings(timezone="Europe/Paris"))

    assert calendar.is_working_time(datetime(2026, 9, 23, 6, 0, tzinfo=UTC)) is True
    assert calendar.is_working_time(datetime(2026, 9, 23, 5, 59, tzinfo=UTC)) is False
    assert calendar.next_working_time(
        datetime(2026, 9, 23, 5, 30, tzinfo=UTC)
    ) == datetime(2026, 9, 23, 6, 0, tzinfo=UTC)
    assert calendar.deadline_for_date("2026-09-25") == datetime(
        2026, 9, 25, 15, 0, tzinfo=UTC
    )


def test_working_calendar_adds_local_work_hours_and_returns_utc() -> None:
    calendar = WorkingCalendar(PlanningSettings(timezone="Europe/Paris"))

    assert calendar.add_working_hours(
        datetime(2026, 9, 25, 13, 0, tzinfo=UTC),
        8,
    ) == datetime(2026, 9, 28, 13, 0, tzinfo=UTC)


@pytest.mark.parametrize("target", ["2026-03-29", "2026-10-25"])
def test_working_calendar_rejects_dst_ambiguous_or_nonexistent_period_boundaries(
    target: str,
) -> None:
    calendar = WorkingCalendar(
        PlanningSettings(
            timezone="Europe/Paris",
            workdays=(6,),
            work_periods=(("02:30", "04:00"),),
        )
    )

    with pytest.raises(ValueError, match="DST"):
        calendar.deadline_for_date(target)


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


def test_working_calendar_counts_working_hours_between_instants() -> None:
    calendar = WorkingCalendar(PlanningSettings(timezone="UTC"))

    assert calendar.working_hours_between(
        datetime(2026, 9, 23, 10, 0, tzinfo=UTC),
        datetime(2026, 9, 23, 15, 0, tzinfo=UTC),
    ) == 4.0
    assert calendar.working_hours_between(
        datetime(2026, 9, 25, 16, 0, tzinfo=UTC),
        datetime(2026, 9, 28, 10, 0, tzinfo=UTC),
    ) == 3.0


def test_working_calendar_working_hours_between_clamps_empty_or_reversed_interval() -> None:
    calendar = WorkingCalendar(PlanningSettings(timezone="UTC"))
    instant = datetime(2026, 9, 23, 10, 0, tzinfo=UTC)

    assert calendar.working_hours_between(instant, instant) == 0.0
    assert calendar.working_hours_between(
        datetime(2026, 9, 23, 11, 0, tzinfo=UTC),
        instant,
    ) == 0.0


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
