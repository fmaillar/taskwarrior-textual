import pytest

from taskwarrior_textual.config import PlanningSettings


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
