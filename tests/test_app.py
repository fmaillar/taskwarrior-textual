from __future__ import annotations

from datetime import UTC, datetime

import pytest
from textual.widgets import Button, Input

from taskwarrior_textual import app as app_module
from taskwarrior_textual.app import (
    CalendarPlanScreen,
    ConfirmDelete,
    ConstraintsScreen,
    CriticalPathScreen,
    DependencyOverviewScreen,
    DependencyScreen,
    GanttScreen,
    MilestonesScreen,
    PlanningForm,
    ProjectFilterForm,
    ProjectOverviewScreen,
    SearchForm,
    TagFilterForm,
    TaskForm,
    TaskwarriorApp,
    TimewarriorReportScreen,
    TimewarriorTrendScreen,
)
from taskwarrior_textual.config import PlanningSettings
from taskwarrior_textual.models import Task
from taskwarrior_textual.taskwarrior import TaskwarriorError, TimewarriorInterval

TASK = Task(
    uuid="1b17dac7-81c8-4aa0-955b-658b1663cce3",
    description="Vérifier mail de RMS",
    status="pending",
    priority="L",
    due="20260926T000000Z",
    urgency=9.38,
    tags=("mail", "rms"),
    depends=("11111111-1111-1111-1111-111111111111",),
    wait="20260924T080000Z",
    scheduled="20260924T090000Z",
    start="20260923T070000Z",
    estimate_hours=2.5,
)




SEARCH_TASKS = [
    Task(
        uuid="aaaaaaaa-1111-2222-3333-444444444444",
        description="Write release notes",
        status="pending",
        project="Docs",
        priority="M",
        due="20261002T000000Z",
        urgency=4.0,
        tags=("release", "writing"),
    ),
    Task(
        uuid="bbbbbbbb-1111-2222-3333-444444444444",
        description="Fix mail server",
        status="pending",
        project="Infra",
        priority="H",
        due="20260925T000000Z",
        urgency=12.0,
        tags=("mail", "server"),
        depends=("aaaaaaaa-1111-2222-3333-444444444444",),
    ),
    Task(
        uuid="cccccccc-1111-2222-3333-444444444444",
        description="Buy cable",
        status="pending",
        project="",
        priority="",
        due="",
        urgency=1.0,
        tags=("hardware",),
    ),
]


class FakeUiClient:
    def __init__(self, tasks: list[Task] | None = None) -> None:
        self.calls: list[tuple[str, object]] = []
        self.fail: str | None = None
        self.tasks = [TASK] if tasks is None else tasks
        self.expanded_tasks: list[Task] | None = None
        self.tracked_hours: dict[str, float] = {}
        self.tracked_intervals: tuple[TimewarriorInterval, ...] = ()
        self.add_values: list[dict[str, str]] = []
        self.modify_values: list[dict[str, object]] = []
        self.planning_values: list[dict[str, str]] = []

    def _maybe_fail(self, action: str) -> None:
        if self.fail == action:
            raise TaskwarriorError(f"{action} failed")

    def view(self, name: str) -> list[Task]:
        self._maybe_fail("view")
        self.calls.append(("view", name))
        return self.tasks

    def expand_dependencies(self, tasks: list[Task], depth: int) -> list[Task]:
        self._maybe_fail("expand_dependencies")
        self.calls.append(("expand_dependencies", depth))
        return list(tasks) if self.expanded_tasks is None else self.expanded_tasks

    def timewarrior_hours(
        self,
        tasks: list[Task],
        *,
        now=None,
    ) -> dict[str, float]:
        self._maybe_fail("timewarrior_hours")
        self.calls.append(("timewarrior_hours", len(tasks)))
        return dict(self.tracked_hours)

    def timewarrior_intervals(
        self,
        tasks: list[Task],
        *,
        now=None,
    ) -> tuple[TimewarriorInterval, ...]:
        self._maybe_fail("timewarrior_intervals")
        self.calls.append(("timewarrior_intervals", len(tasks)))
        return tuple(self.tracked_intervals)

    def information(self, uuid_prefix: str) -> str:
        self._maybe_fail("information")
        self.calls.append(("information", uuid_prefix))
        return "task information"

    def add(self, **values: str) -> str:
        self._maybe_fail("add")
        self.calls.append(("add", values["description"]))
        self.add_values.append(values)
        return "created"

    def modify(self, uuid_prefix: str, **values: object) -> str:
        self._maybe_fail("modify")
        self.calls.append(("modify", uuid_prefix))
        self.modify_values.append(values)
        return "modified"

    def modify_planning(self, uuid_prefix: str, **values: str) -> str:
        self._maybe_fail("modify_planning")
        self.calls.append(("modify_planning", uuid_prefix))
        self.planning_values.append(values)
        return "planned"

    def start(self, uuid_prefix: str) -> str:
        self._maybe_fail("start")
        self.calls.append(("start", uuid_prefix))
        return "started"

    def stop(self, uuid_prefix: str) -> str:
        self._maybe_fail("stop")
        self.calls.append(("stop", uuid_prefix))
        return "stopped"

    def done(self, uuid_prefix: str) -> str:
        self._maybe_fail("done")
        self.calls.append(("done", uuid_prefix))
        return "done"

    def delete(self, uuid_prefix: str) -> str:
        self._maybe_fail("delete")
        self.calls.append(("delete", uuid_prefix))
        return "deleted"

    def sync(self) -> str:
        self._maybe_fail("sync")
        self.calls.append(("sync", ""))
        return "synced"


def test_task_form_can_hold_an_existing_task() -> None:
    form = TaskForm(TASK)
    assert form.initial_task is TASK


def test_task_form_preserves_explicit_zero_estimate() -> None:
    task = Task(
        uuid="99999999-1111-2222-3333-444444444444",
        description="Milestone",
        status="pending",
        estimate_hours=0.0,
        estimate_defined=True,
    )
    form = TaskForm(task)

    async def check() -> None:
        app = TaskwarriorApp(client=FakeUiClient(tasks=[]))
        async with app.run_test() as pilot:
            await pilot.pause()
            app.push_screen(form)
            await pilot.pause()
            assert form.query_one("#estimate", Input).value == "0.0"

    import asyncio
    asyncio.run(check())


def test_delete_confirmation_can_hold_a_task() -> None:
    confirmation = ConfirmDelete(TASK)
    assert confirmation.target_task is TASK


async def test_app_mounts_and_displays_pending_task() -> None:
    app = TaskwarriorApp(client=FakeUiClient())
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#tasks")
        assert table.row_count == 1
        assert app._selected_task() == TASK
        assert app.current_view == "pending"
        assert ("view", "pending") in app.client.calls


def test_task_row_shows_active_marker_tags_and_due_in_pending_view() -> None:
    row = TaskwarriorApp._task_row(
        TASK,
        "pending",
        PlanningSettings(timezone="UTC"),
        now=datetime(2026, 9, 23, 8, 0, tzinfo=UTC),
        tracked_hours={TASK.uuid: 1.0},
    )

    assert row == (
        TASK.short_uuid,
        "▶",
        "◆",
        "L",
        "",
        "2026-09-26",
        "mail,rms",
        "Vérifier mail de RMS",
        "2.50h",
        "1.00h",
        "1.50h",
        "9.38",
    )


def test_task_row_leaves_tracked_blank_when_timewarrior_has_no_match() -> None:
    task = Task(
        uuid="abababab-bbbb-cccc-dddd-eeeeeeeeeeee",
        description="Estimated",
        status="pending",
        estimate_hours=3.0,
    )

    row = TaskwarriorApp._task_row(
        task,
        "pending",
        PlanningSettings(timezone="UTC"),
        now=datetime(2026, 9, 23, 8, 0, tzinfo=UTC),
        tracked_hours={},
    )

    assert row[8:11] == ("3.00h", "", "3.00h")


def test_task_row_uses_view_specific_date() -> None:
    task = Task(
        uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        description="Historical task",
        status="completed",
        wait="20260924T080000Z",
        end="20260925T170000Z",
        tags=("history",),
    )

    assert TaskwarriorApp._task_row(task, "waiting")[5] == "2026-09-24 08:00"
    assert TaskwarriorApp._task_row(task, "completed")[5] == "2026-09-25 17:00"
    assert TaskwarriorApp._task_row(task, "deleted")[5] == "2026-09-25 17:00"

    scheduled = Task(
        uuid="bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee",
        description="Scheduled task",
        status="pending",
        scheduled="20260924T093000Z",
    )
    assert TaskwarriorApp._task_row(scheduled, "scheduled")[5] == "2026-09-24 09:30"


def test_task_row_has_no_active_marker_for_inactive_task() -> None:
    task = Task(
        uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        description="Inactive",
        status="pending",
    )

    row = TaskwarriorApp._task_row(task, "pending")
    assert row[1] == ""
    assert row[2] == ""
    assert row[-2] == ""


async def test_table_uses_enriched_row_shape() -> None:
    app = TaskwarriorApp(client=FakeUiClient())
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#tasks")
        assert list(table.get_row_at(0)) == list(TaskwarriorApp._task_row(TASK, "pending"))


def test_dependency_summary_resolves_known_tasks_and_reverse_links() -> None:
    summary = TaskwarriorApp._dependency_summary(SEARCH_TASKS[1], SEARCH_TASKS)

    assert "Depends on" in summary
    assert "aaaaaaaa Write release notes" in summary
    assert "Required by" not in summary

    reverse = TaskwarriorApp._dependency_summary(SEARCH_TASKS[0], SEARCH_TASKS)
    assert "Required by" in reverse
    assert "bbbbbbbb Fix mail server" in reverse


def test_dependency_summary_keeps_unknown_dependencies_visible() -> None:
    task = Task(
        uuid="dddddddd-1111-2222-3333-444444444444",
        description="External dependency",
        status="pending",
        depends=("99999999-aaaa-bbbb-cccc-dddddddddddd",),
    )

    summary = TaskwarriorApp._dependency_summary(task, [task])

    assert "99999999" in summary
    assert "No dependencies" not in summary


def test_dependency_summary_reports_empty_neighborhood() -> None:
    summary = TaskwarriorApp._dependency_summary(SEARCH_TASKS[2], SEARCH_TASKS)
    assert "No dependencies in current view." in summary


async def test_dependency_action_is_noop_with_empty_table() -> None:
    app = TaskwarriorApp(client=FakeUiClient(tasks=[]))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen_before = app.screen
        app.action_show_dependencies()
        assert app.screen is screen_before
        assert not isinstance(app.screen, DependencyScreen)


async def test_dependency_key_opens_local_dependency_screen_without_refetch() -> None:
    client = FakeUiClient(tasks=SEARCH_TASKS)
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        initial_view_calls = client.calls.count(("view", "pending"))
        table = app.query_one("#tasks")
        table.move_cursor(row=1)

        await pilot.press("g")
        await pilot.pause()

        assert isinstance(app.screen, DependencyScreen)
        body = str(app.screen.query_one("#dependency-body").render())
        assert "aaaaaaaa Write release notes" in body
        assert client.calls.count(("view", "pending")) == initial_view_calls

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, DependencyScreen)


def test_dependency_overview_builds_topological_layers() -> None:
    first = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="Foundation",
        status="pending",
    )
    parallel = Task(
        uuid="22222222-2222-2222-2222-222222222222",
        description="Parallel",
        status="pending",
    )
    middle = Task(
        uuid="33333333-3333-3333-3333-333333333333",
        description="Middle",
        status="pending",
        depends=(first.uuid,),
    )
    last = Task(
        uuid="44444444-4444-4444-4444-444444444444",
        description="Last",
        status="pending",
        depends=(middle.uuid, parallel.uuid),
    )

    summary = TaskwarriorApp._dependency_overview([last, middle, parallel, first])

    assert "Tasks: 4 | Resolved edges: 3 | Unresolved: 0" in summary
    assert "Layer 0: 11111111 Foundation; 22222222 Parallel" in summary
    assert "Layer 1: 33333333 Middle" in summary
    assert "Layer 2: 44444444 Last" in summary
    assert "Cycle detected" not in summary


def test_dependency_overview_breaks_short_uuid_ties_with_full_uuid() -> None:
    first = Task(
        uuid="aaaaaaaa-0000-0000-0000-000000000001",
        description="First collision",
        status="pending",
    )
    second = Task(
        uuid="aaaaaaaa-0000-0000-0000-000000000002",
        description="Second collision",
        status="pending",
    )

    summary = TaskwarriorApp._dependency_overview([second, first])

    assert "Layer 0: aaaaaaaa First collision; aaaaaaaa Second collision" in summary


def test_dependency_overview_reports_unresolved_dependencies() -> None:
    task = Task(
        uuid="aaaaaaaa-1111-2222-3333-444444444444",
        description="Needs external work",
        status="pending",
        depends=("99999999-aaaa-bbbb-cccc-dddddddddddd",),
    )

    summary = TaskwarriorApp._dependency_overview([task])

    assert "Tasks: 1 | Resolved edges: 0 | Unresolved: 1" in summary
    assert "Unresolved dependencies" in summary
    assert "aaaaaaaa -> 99999999" in summary
    assert "Layer 0: aaaaaaaa Needs external work" in summary


def test_dependency_overview_detects_cycles() -> None:
    first = Task(
        uuid="aaaaaaaa-1111-2222-3333-444444444444",
        description="First",
        status="pending",
        depends=("bbbbbbbb-1111-2222-3333-444444444444",),
    )
    second = Task(
        uuid="bbbbbbbb-1111-2222-3333-444444444444",
        description="Second",
        status="pending",
        depends=(first.uuid,),
    )
    downstream = Task(
        uuid="cccccccc-1111-2222-3333-444444444444",
        description="Downstream",
        status="pending",
        depends=(first.uuid,),
    )

    summary = TaskwarriorApp._dependency_overview([downstream, second, first])

    assert "Tasks: 3 | Resolved edges: 3 | Unresolved: 0" in summary
    assert "Cycle detected among: aaaaaaaa First; bbbbbbbb Second" in summary
    assert "Blocked by cycle: cccccccc Downstream" in summary
    assert "Layer 0:" not in summary


def test_dependency_overview_does_not_misclassify_bridge_between_cycles() -> None:
    a = Task(
        uuid="aaaaaaaa-1111-1111-1111-111111111111",
        description="A",
        status="pending",
        depends=("bbbbbbbb-1111-1111-1111-111111111111",),
    )
    b = Task(
        uuid="bbbbbbbb-1111-1111-1111-111111111111",
        description="B",
        status="pending",
        depends=(a.uuid,),
    )
    bridge = Task(
        uuid="cccccccc-1111-1111-1111-111111111111",
        description="Bridge",
        status="pending",
        depends=(a.uuid,),
    )
    c = Task(
        uuid="dddddddd-1111-1111-1111-111111111111",
        description="C",
        status="pending",
        depends=("eeeeeeee-1111-1111-1111-111111111111", bridge.uuid),
    )
    d = Task(
        uuid="eeeeeeee-1111-1111-1111-111111111111",
        description="D",
        status="pending",
        depends=(c.uuid,),
    )

    summary = TaskwarriorApp._dependency_overview([d, bridge, b, c, a])

    assert "Cycle detected among: aaaaaaaa A; bbbbbbbb B; dddddddd C; eeeeeeee D" in summary
    assert "Blocked by cycle: cccccccc Bridge" in summary
    assert "cccccccc Bridge" not in summary.split("Cycle detected among:", 1)[1].split("\n", 1)[0]


def test_dependency_overview_handles_empty_view() -> None:
    assert TaskwarriorApp._dependency_overview([]) == "No tasks in current view."


async def test_dependency_overview_key_opens_local_screen_without_refetch() -> None:
    client = FakeUiClient(tasks=SEARCH_TASKS)
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        initial_view_calls = client.calls.count(("view", "pending"))

        await pilot.press("shift+g")
        await pilot.pause()

        assert isinstance(app.screen, DependencyOverviewScreen)
        body = str(app.screen.query_one("#dependency-overview-body").render())
        assert "Tasks: 3 | Resolved edges: 1 | Unresolved: 0" in body
        assert "Layer 0:" in body
        assert client.calls.count(("view", "pending")) == initial_view_calls

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, DependencyOverviewScreen)


async def test_dependency_overview_expands_external_dependencies_to_configured_depth() -> None:
    root = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="Root",
        status="pending",
        depends=("22222222-2222-2222-2222-222222222222",),
    )
    external = Task(
        uuid="22222222-2222-2222-2222-222222222222",
        description="External dependency",
        status="completed",
    )
    client = FakeUiClient(tasks=[root])
    client.expanded_tasks = [root, external]
    app = TaskwarriorApp(
        client=client,
        planning_settings=PlanningSettings(timezone="UTC", dependency_depth=3),
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("shift+g")
        await pilot.pause()

        body = str(app.screen.query_one("#dependency-overview-body").render())
        assert "Tasks: 2 | Resolved edges: 1 | Unresolved: 0" in body
        assert ("expand_dependencies", 3) in client.calls


async def test_dependency_expansion_error_is_rendered_without_opening_planning_screen() -> None:
    client = FakeUiClient(tasks=SEARCH_TASKS)
    client.fail = "expand_dependencies"
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("shift+g")
        await pilot.pause()

        assert not isinstance(app.screen, DependencyOverviewScreen)
        assert "expand_dependencies failed" in str(app.query_one("#details").render())


@pytest.mark.parametrize(
    ("key", "screen_type"),
    [
        ("g", DependencyScreen),
        ("shift+c", CriticalPathScreen),
        ("shift+h", GanttScreen),
        ("shift+l", CalendarPlanScreen),
        ("shift+k", ConstraintsScreen),
    ],
)
async def test_planning_actions_stop_when_dependency_expansion_fails(
    key: str,
    screen_type: type,
) -> None:
    client = FakeUiClient(tasks=SEARCH_TASKS)
    client.fail = "expand_dependencies"
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press(key)
        await pilot.pause()

        assert not isinstance(app.screen, screen_type)
        assert "expand_dependencies failed" in str(app.query_one("#details").render())


@pytest.mark.parametrize(
    ("key", "screen_type"),
    [
        ("shift+h", GanttScreen),
        ("shift+l", CalendarPlanScreen),
        ("shift+k", ConstraintsScreen),
    ],
)
async def test_other_planning_actions_stop_when_timewarrior_fails(
    key: str,
    screen_type: type,
) -> None:
    client = FakeUiClient(tasks=SEARCH_TASKS)
    client.fail = "timewarrior_hours"
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press(key)
        await pilot.pause()

        assert not isinstance(app.screen, screen_type)
        assert "timewarrior_hours failed" in str(app.query_one("#details").render())


async def test_critical_path_action_uses_timewarrior_tracked_hours() -> None:
    active = Task(
        uuid="abababab-1111-2222-3333-444444444444",
        description="Tracked active",
        status="pending",
        start="20260923T080000Z",
        estimate_hours=4.0,
    )
    client = FakeUiClient(tasks=[active])
    client.tracked_hours = {active.uuid: 1.5}
    app = TaskwarriorApp(
        client=client,
        planning_settings=PlanningSettings(timezone="UTC"),
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("shift+c")
        await pilot.pause()

        body = str(app.screen.query_one("#critical-path-body").render())
        assert "Project duration: 2.50h" in body
        assert ("timewarrior_hours", 1) in client.calls


async def test_timewarrior_failure_is_rendered_without_opening_planning_screen() -> None:
    client = FakeUiClient(tasks=SEARCH_TASKS)
    client.fail = "timewarrior_hours"
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("shift+c")
        await pilot.pause()

        assert not isinstance(app.screen, CriticalPathScreen)
        assert "timewarrior_hours failed" in str(app.query_one("#details").render())


def test_critical_path_summary_computes_schedule_and_slack() -> None:
    foundation = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="Foundation",
        status="pending",
        estimate_hours=2.0,
    )
    long_branch = Task(
        uuid="22222222-2222-2222-2222-222222222222",
        description="Long branch",
        status="pending",
        depends=(foundation.uuid,),
        estimate_hours=3.0,
    )
    short_branch = Task(
        uuid="33333333-3333-3333-3333-333333333333",
        description="Short branch",
        status="pending",
        depends=(foundation.uuid,),
        estimate_hours=1.0,
    )
    finish = Task(
        uuid="44444444-4444-4444-4444-444444444444",
        description="Finish",
        status="pending",
        depends=(long_branch.uuid, short_branch.uuid),
        estimate_hours=4.0,
    )
    independent = Task(
        uuid="55555555-5555-5555-5555-555555555555",
        description="Independent",
        status="pending",
        estimate_hours=2.0,
    )

    summary = TaskwarriorApp._critical_path_summary(
        [finish, independent, short_branch, long_branch, foundation]
    )

    assert "Project duration: 9.00h" in summary
    assert "Critical path: 11111111 -> 22222222 -> 44444444" in summary
    assert "11111111 | 2.00h | 0.00 | 2.00 | 0.00 | yes" in summary
    assert "22222222 | 3.00h | 2.00 | 5.00 | 0.00 | yes" in summary
    assert "33333333 | 1.00h | 2.00 | 3.00 | 2.00 | no" in summary
    assert "44444444 | 4.00h | 5.00 | 9.00 | 0.00 | yes" in summary
    assert "55555555 | 2.00h | 0.00 | 2.00 | 7.00 | no" in summary


def test_critical_path_summary_treats_missing_estimates_as_zero() -> None:
    first = Task(
        uuid="aaaaaaaa-1111-2222-3333-444444444444",
        description="Unknown estimate",
        status="pending",
    )
    second = Task(
        uuid="bbbbbbbb-1111-2222-3333-444444444444",
        description="Known estimate",
        status="pending",
        depends=(first.uuid,),
        estimate_hours=1.5,
    )

    summary = TaskwarriorApp._critical_path_summary([second, first])

    assert "Project duration: 1.50h" in summary
    assert "Unestimated tasks treated as 0h: aaaaaaaa" in summary
    assert "Critical path: aaaaaaaa -> bbbbbbbb" in summary


def test_critical_path_summary_marks_milestones_and_deadline_pressure() -> None:
    start = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="Start",
        status="pending",
        scheduled="20260924T090000Z",
        estimate_hours=2.0,
    )
    milestone = Task(
        uuid="22222222-2222-2222-2222-222222222222",
        description="Gate",
        status="pending",
        depends=(start.uuid,),
        due="20260924T100000Z",
        estimate_hours=0.0,
        estimate_defined=True,
    )

    summary = TaskwarriorApp._critical_path_summary(
        [milestone, start], PlanningSettings(timezone="UTC")
    )

    assert "22222222 | 0.00h | 2.00 | 2.00 | 0.00 | yes | milestone" in summary
    assert "Deadline pressure" in summary
    assert (
        "22222222 | 2026-09-24 10:00 | 2026-09-24 11:00 | "
        "-1.00h | yes | milestone"
    ) in summary


def test_critical_path_summary_omits_deadline_pressure_without_calendar_anchor() -> None:
    task = Task(
        uuid="aaaaaaaa-1111-2222-3333-444444444444",
        description="Deadline only",
        status="pending",
        due="20260925T120000Z",
        estimate_hours=1.0,
    )

    summary = TaskwarriorApp._critical_path_summary([task])

    assert "Deadline pressure" not in summary
    assert "aaaaaaaa | 1.00h | 0.00 | 1.00 | 0.00 | yes | task" in summary


def test_critical_path_summary_omits_deadline_pressure_with_anchor_but_no_due() -> None:
    task = Task(
        uuid="12121212-1111-2222-3333-444444444444",
        description="Scheduled only",
        status="pending",
        scheduled="20260924T090000Z",
        estimate_hours=1.0,
    )

    summary = TaskwarriorApp._critical_path_summary([task])

    assert "Project duration: 1.00h" in summary
    assert "Deadline pressure" not in summary


def test_critical_path_summary_reports_unresolved_dependencies() -> None:
    task = Task(
        uuid="aaaaaaaa-1111-2222-3333-444444444444",
        description="External dependency",
        status="pending",
        depends=("99999999-aaaa-bbbb-cccc-dddddddddddd",),
        estimate_hours=2.0,
    )

    summary = TaskwarriorApp._critical_path_summary([task])

    assert "Unresolved dependencies ignored: aaaaaaaa -> 99999999" in summary
    assert "Project duration: 2.00h" in summary


def test_critical_path_summary_refuses_cycles_and_handles_empty_view() -> None:
    first = Task(
        uuid="aaaaaaaa-1111-2222-3333-444444444444",
        description="First",
        status="pending",
        depends=("bbbbbbbb-1111-2222-3333-444444444444",),
        estimate_hours=1.0,
    )
    second = Task(
        uuid="bbbbbbbb-1111-2222-3333-444444444444",
        description="Second",
        status="pending",
        depends=(first.uuid,),
        estimate_hours=1.0,
    )

    summary = TaskwarriorApp._critical_path_summary([first, second])

    assert "Critical path unavailable: dependency cycle detected." in summary
    assert TaskwarriorApp._critical_path_summary([]) == "No tasks in current view."


async def test_critical_path_key_opens_local_screen_without_refetch() -> None:
    first = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="First",
        status="pending",
        estimate_hours=2.0,
    )
    second = Task(
        uuid="22222222-2222-2222-2222-222222222222",
        description="Second",
        status="pending",
        depends=(first.uuid,),
        estimate_hours=3.0,
    )
    client = FakeUiClient(tasks=[second, first])
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        initial_view_calls = client.calls.count(("view", "pending"))

        await pilot.press("shift+c")
        await pilot.pause()

        assert isinstance(app.screen, CriticalPathScreen)
        body = str(app.screen.query_one("#critical-path-body").render())
        assert "Project duration: 5.00h" in body
        assert "Critical path: 11111111 -> 22222222" in body
        assert client.calls.count(("view", "pending")) == initial_view_calls

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, CriticalPathScreen)


def test_critical_path_summary_uses_remaining_work_for_active_task() -> None:
    active = Task(
        uuid="abababab-1111-2222-3333-444444444444",
        description="Active",
        status="pending",
        start="20260923T090000Z",
        estimate_hours=4.0,
    )

    summary = TaskwarriorApp._critical_path_summary(
        [active],
        PlanningSettings(timezone="UTC"),
        now=datetime(2026, 9, 23, 11, 0, tzinfo=UTC),
    )

    assert "Project duration: 2.00h" in summary
    assert "abababab | 4.00h | 0.00 | 2.00 | 0.00 | yes | task" in summary


def test_gantt_summary_uses_remaining_work_for_active_task() -> None:
    active = Task(
        uuid="cdcdcdcd-1111-2222-3333-444444444444",
        description="Active",
        status="pending",
        start="20260923T090000Z",
        estimate_hours=4.0,
    )

    summary = TaskwarriorApp._gantt_summary(
        [active],
        PlanningSettings(timezone="UTC"),
        now=datetime(2026, 9, 23, 11, 0, tzinfo=UTC),
    )

    assert "Scale: 1 char = 1h | Project duration: 2.00h" in summary
    assert "cdcdcdcd | * | 0.00-2.00h | ██ | Active" in summary


def test_gantt_summary_renders_dependency_schedule() -> None:
    first = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="Foundation",
        status="pending",
        estimate_hours=2.0,
    )
    parallel = Task(
        uuid="22222222-2222-2222-2222-222222222222",
        description="Parallel",
        status="pending",
        estimate_hours=1.0,
    )
    middle = Task(
        uuid="33333333-3333-3333-3333-333333333333",
        description="Middle",
        status="pending",
        depends=(first.uuid,),
        estimate_hours=3.0,
    )
    finish = Task(
        uuid="44444444-4444-4444-4444-444444444444",
        description="Finish",
        status="pending",
        depends=(middle.uuid, parallel.uuid),
        estimate_hours=2.0,
    )

    summary = TaskwarriorApp._gantt_summary([finish, middle, parallel, first])

    assert "Scale: 1 char = 1h | Project duration: 7.00h" in summary
    assert "11111111 | * | 0.00-2.00h | ██ | Foundation" in summary
    assert "22222222 |   | 0.00-1.00h | █ | Parallel" in summary
    assert "33333333 | * | 2.00-5.00h |   ███ | Middle" in summary
    assert "44444444 | * | 5.00-7.00h |      ██ | Finish" in summary
    assert "Critical marker: *" in summary


def test_gantt_summary_marks_zero_estimates_and_unresolved_dependencies() -> None:
    first = Task(
        uuid="aaaaaaaa-1111-2222-3333-444444444444",
        description="Unknown estimate",
        status="pending",
    )
    second = Task(
        uuid="bbbbbbbb-1111-2222-3333-444444444444",
        description="External dependency",
        status="pending",
        depends=(first.uuid, "99999999-aaaa-bbbb-cccc-dddddddddddd"),
        estimate_hours=1.0,
    )

    summary = TaskwarriorApp._gantt_summary([second, first])

    assert "aaaaaaaa | * | 0.00-0.00h | · | Unknown estimate" in summary
    assert "bbbbbbbb | * | 0.00-1.00h | █ | External dependency" in summary
    assert "Unestimated tasks shown as ·: aaaaaaaa" in summary
    assert "Unresolved dependencies ignored: bbbbbbbb -> 99999999" in summary


def test_gantt_summary_refuses_cycles_and_handles_empty_view() -> None:
    first = Task(
        uuid="aaaaaaaa-1111-2222-3333-444444444444",
        description="First",
        status="pending",
        depends=("bbbbbbbb-1111-2222-3333-444444444444",),
        estimate_hours=1.0,
    )
    second = Task(
        uuid="bbbbbbbb-1111-2222-3333-444444444444",
        description="Second",
        status="pending",
        depends=(first.uuid,),
        estimate_hours=1.0,
    )

    assert (
        TaskwarriorApp._gantt_summary([first, second])
        == "Gantt unavailable: dependency cycle detected."
    )
    assert TaskwarriorApp._gantt_summary([]) == "No tasks in current view."


async def test_gantt_key_opens_local_screen_without_refetch() -> None:
    first = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="First",
        status="pending",
        estimate_hours=2.0,
    )
    second = Task(
        uuid="22222222-2222-2222-2222-222222222222",
        description="Second",
        status="pending",
        depends=(first.uuid,),
        estimate_hours=3.0,
    )
    client = FakeUiClient(tasks=[second, first])
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        initial_view_calls = client.calls.count(("view", "pending"))

        await pilot.press("shift+h")
        await pilot.pause()

        assert isinstance(app.screen, GanttScreen)
        body = str(app.screen.query_one("#gantt-body").render())
        assert "Project duration: 5.00h" in body
        assert "11111111 | * | 0.00-2.00h | ██ | First" in body
        assert "22222222 | * | 2.00-5.00h |   ███ | Second" in body
        assert client.calls.count(("view", "pending")) == initial_view_calls

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, GanttScreen)


def test_planning_datetime_parses_taskwarrior_utc_and_rejects_unknown() -> None:
    assert TaskwarriorApp._planning_datetime("") is None
    assert TaskwarriorApp._planning_datetime("tomorrow") is None
    parsed = TaskwarriorApp._planning_datetime("20260924T090000Z")
    assert parsed is not None
    assert parsed.strftime("%Y-%m-%d %H:%M") == "2026-09-24 09:00"


def test_gantt_breaks_same_start_short_uuid_ties_with_full_uuid() -> None:
    first = Task(
        uuid="aaaaaaaa-0000-0000-0000-000000000001",
        description="First collision",
        status="pending",
        estimate_hours=1.0,
    )
    second = Task(
        uuid="aaaaaaaa-0000-0000-0000-000000000002",
        description="Second collision",
        status="pending",
        estimate_hours=1.0,
    )

    summary = TaskwarriorApp._gantt_summary([second, first])

    assert summary.index("First collision") < summary.index("Second collision")


def test_calendar_plan_respects_dependencies_scheduled_constraints_and_due() -> None:
    first = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="Foundation",
        status="pending",
        scheduled="20260924T090000Z",
        due="20260924T000000Z",
        estimate_hours=2.0,
    )
    delayed = Task(
        uuid="22222222-2222-2222-2222-222222222222",
        description="Delayed branch",
        status="pending",
        scheduled="20260924T150000Z",
        due="20260924T160000Z",
        depends=(first.uuid,),
        estimate_hours=3.0,
    )
    normal = Task(
        uuid="33333333-3333-3333-3333-333333333333",
        description="Normal branch",
        status="pending",
        depends=(first.uuid,),
        estimate_hours=1.0,
    )

    summary = TaskwarriorApp._calendar_plan(
        [delayed, normal, first], PlanningSettings(timezone="UTC")
    )

    assert (
        "Calendar origin: 2026-09-24 09:00 UTC | "
        "Project finish: 2026-09-25 09:00 UTC"
    ) in summary
    assert (
        "11111111 | 2026-09-24 09:00 -> 2026-09-24 11:00 | "
        "2026-09-24 | on time | Foundation"
    ) in summary
    assert (
        "33333333 | 2026-09-24 11:00 -> 2026-09-24 12:00 | "
        "- | - | Normal branch"
    ) in summary
    assert (
        "22222222 | 2026-09-24 15:00 -> 2026-09-25 09:00 | "
        "2026-09-24 16:00 | LATE +17.00h | Delayed branch"
    ) in summary
    assert "Late tasks: 1" in summary


def test_calendar_plan_reports_unestimated_unresolved_and_invalid_due() -> None:
    first = Task(
        uuid="aaaaaaaa-1111-2222-3333-444444444444",
        description="Anchor",
        status="pending",
        scheduled="20260924T080000Z",
    )
    second = Task(
        uuid="bbbbbbbb-1111-2222-3333-444444444444",
        description="External",
        status="pending",
        depends=(first.uuid, "99999999-aaaa-bbbb-cccc-dddddddddddd"),
        due="not-a-date",
        estimate_hours=1.0,
    )
    invalid_start = Task(
        uuid="cccccccc-1111-2222-3333-444444444444",
        description="Bad start",
        status="pending",
        scheduled="tomorrow",
        estimate_hours=1.0,
    )

    summary = TaskwarriorApp._calendar_plan(
        [invalid_start, second, first], PlanningSettings(timezone="UTC")
    )

    assert "Unestimated tasks treated as 0h: aaaaaaaa" in summary
    assert "Unresolved dependencies ignored: bbbbbbbb -> 99999999" in summary
    assert "Invalid due dates ignored: bbbbbbbb" in summary
    assert "Invalid scheduled dates ignored: cccccccc" in summary
    assert "Late tasks: 0" in summary


def test_calendar_plan_requires_anchor_and_refuses_cycles() -> None:
    no_anchor = Task(
        uuid="aaaaaaaa-1111-2222-3333-444444444444",
        description="No anchor",
        status="pending",
        estimate_hours=1.0,
    )
    assert (
        TaskwarriorApp._calendar_plan([no_anchor], PlanningSettings(timezone="UTC"))
        == "Calendar plan unavailable: no valid scheduled date in current view."
    )
    assert TaskwarriorApp._calendar_plan([]) == "No tasks in current view."

    first = Task(
        uuid="bbbbbbbb-1111-2222-3333-444444444444",
        description="First",
        status="pending",
        scheduled="20260924T080000Z",
        depends=("cccccccc-1111-2222-3333-444444444444",),
        estimate_hours=1.0,
    )
    second = Task(
        uuid="cccccccc-1111-2222-3333-444444444444",
        description="Second",
        status="pending",
        depends=(first.uuid,),
        estimate_hours=1.0,
    )
    assert (
        TaskwarriorApp._calendar_plan([first, second], PlanningSettings(timezone="UTC"))
        == "Calendar plan unavailable: dependency cycle detected."
    )


async def test_calendar_plan_key_opens_local_screen_without_refetch() -> None:
    first = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="First",
        status="pending",
        scheduled="20260924T090000Z",
        estimate_hours=2.0,
    )
    second = Task(
        uuid="22222222-2222-2222-2222-222222222222",
        description="Second",
        status="pending",
        depends=(first.uuid,),
        estimate_hours=3.0,
    )
    client = FakeUiClient(tasks=[second, first])
    app = TaskwarriorApp(
        client=client,
        planning_settings=PlanningSettings(timezone="UTC"),
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        initial_view_calls = client.calls.count(("view", "pending"))

        await pilot.press("shift+l")
        await pilot.pause()

        assert isinstance(app.screen, CalendarPlanScreen)
        body = str(app.screen.query_one("#calendar-plan-body").render())
        assert "Calendar origin: 2026-09-24 09:00 UTC" in body
        assert "Project finish: 2026-09-24 15:00 UTC" in body
        assert client.calls.count(("view", "pending")) == initial_view_calls

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, CalendarPlanScreen)


def test_constraints_summary_reports_scheduled_deadlines_and_lateness() -> None:
    anchor = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="Anchor",
        status="pending",
        scheduled="20260924T090000Z",
        estimate_hours=2.0,
    )
    late = Task(
        uuid="22222222-2222-2222-2222-222222222222",
        description="Late",
        status="pending",
        depends=(anchor.uuid,),
        due="20260924T100000Z",
        estimate_hours=1.0,
    )
    due_only = Task(
        uuid="33333333-3333-3333-3333-333333333333",
        description="Deadline only",
        status="pending",
        due="20260925T000000Z",
    )

    summary = TaskwarriorApp._constraints_summary(
        [late, due_only, anchor],
        PlanningSettings(timezone="UTC"),
    )

    assert "Constraints: 3 | Scheduled: 1 | Due: 2" in summary
    assert (
        "11111111 | 2026-09-24 09:00 | - | 2026-09-24 11:00 | "
        "scheduled | Anchor"
    ) in summary
    assert (
        "22222222 | - | 2026-09-24 10:00 | 2026-09-24 12:00 | "
        "LATE +2.00h | Late"
    ) in summary
    assert (
        "33333333 | - | 2026-09-25 | 2026-09-24 09:00 | "
        "on time | Deadline only"
    ) in summary


def test_constraints_summary_handles_invalid_values_and_no_anchor() -> None:
    invalid_scheduled = Task(
        uuid="aaaaaaaa-1111-2222-3333-444444444444",
        description="Bad scheduled",
        status="pending",
        scheduled="tomorrow",
    )
    invalid_due = Task(
        uuid="bbbbbbbb-1111-2222-3333-444444444444",
        description="Bad due",
        status="pending",
        due="not-a-date",
    )
    due_only = Task(
        uuid="cccccccc-1111-2222-3333-444444444444",
        description="Due only",
        status="pending",
        due="20260925T120000Z",
    )

    summary = TaskwarriorApp._constraints_summary(
        [due_only, invalid_due, invalid_scheduled],
        PlanningSettings(timezone="UTC"),
    )

    assert "Constraints: 3 | Scheduled: 1 | Due: 2" in summary
    assert "aaaaaaaa | tomorrow | - | - | invalid scheduled | Bad scheduled" in summary
    assert "bbbbbbbb | - | not-a-date | - | invalid due | Bad due" in summary
    assert "cccccccc | - | 2026-09-25 12:00 | - | deadline | Due only" in summary


def test_constraints_summary_reports_cycles_and_empty_constraints() -> None:
    unconstrained = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="Free",
        status="pending",
    )
    assert (
        TaskwarriorApp._constraints_summary([unconstrained])
        == "No scheduled or due constraints in current view."
    )
    assert TaskwarriorApp._constraints_summary([]) == "No tasks in current view."

    first = Task(
        uuid="aaaaaaaa-1111-2222-3333-444444444444",
        description="First",
        status="pending",
        scheduled="20260924T090000Z",
        depends=("bbbbbbbb-1111-2222-3333-444444444444",),
    )
    second = Task(
        uuid="bbbbbbbb-1111-2222-3333-444444444444",
        description="Second",
        status="pending",
        due="20260924T120000Z",
        depends=(first.uuid,),
    )

    summary = TaskwarriorApp._constraints_summary(
        [first, second],
        PlanningSettings(timezone="UTC"),
    )

    assert "aaaaaaaa | 2026-09-24 09:00 | - | - | cycle | First" in summary
    assert "bbbbbbbb | - | 2026-09-24 12:00 | - | cycle | Second" in summary


async def test_constraints_key_opens_local_screen_without_refetch() -> None:
    task = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="Constrained",
        status="pending",
        scheduled="20260924T090000Z",
        due="20260924T120000Z",
        estimate_hours=1.0,
    )
    client = FakeUiClient(tasks=[task])
    app = TaskwarriorApp(
        client=client,
        planning_settings=PlanningSettings(timezone="UTC"),
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        initial_view_calls = client.calls.count(("view", "pending"))

        await pilot.press("shift+k")
        await pilot.pause()

        assert isinstance(app.screen, ConstraintsScreen)
        body = str(app.screen.query_one("#constraints-body").render())
        assert "Constraints: 1 | Scheduled: 1 | Due: 1" in body
        assert "on time" in body
        assert client.calls.count(("view", "pending")) == initial_view_calls

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, ConstraintsScreen)


def test_milestones_summary_lists_only_explicit_zero_estimates() -> None:
    milestone = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="Release gate",
        status="pending",
        due="20260925T000000Z",
        estimate_hours=0.0,
        estimate_defined=True,
    )
    missing = Task(
        uuid="22222222-2222-2222-2222-222222222222",
        description="Unknown duration",
        status="pending",
    )
    work = Task(
        uuid="33333333-3333-3333-3333-333333333333",
        description="Implementation",
        status="pending",
        estimate_hours=2.0,
    )

    summary = TaskwarriorApp._milestones_summary([work, missing, milestone])

    assert "Milestones: 1" in summary
    assert "11111111 | 2026-09-25 | Release gate" in summary
    assert "22222222" not in summary
    assert "33333333" not in summary


def test_milestones_summary_handles_empty_cases() -> None:
    assert TaskwarriorApp._milestones_summary([]) == "No tasks in current view."
    task = Task(
        uuid="aaaaaaaa-1111-2222-3333-444444444444",
        description="Regular",
        status="pending",
        estimate_hours=1.0,
    )
    assert (
        TaskwarriorApp._milestones_summary([task])
        == "No explicit zero-duration milestones in current view."
    )


async def test_milestones_key_opens_local_screen_without_refetch() -> None:
    milestone = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="Release gate",
        status="pending",
        scheduled="20260924T090000Z",
        estimate_hours=0.0,
        estimate_defined=True,
    )
    client = FakeUiClient(tasks=[milestone])
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        initial_view_calls = client.calls.count(("view", "pending"))

        await pilot.press("shift+m")
        await pilot.pause()

        assert isinstance(app.screen, MilestonesScreen)
        body = str(app.screen.query_one("#milestones-body").render())
        assert "Milestones: 1" in body
        assert "Release gate" in body
        assert client.calls.count(("view", "pending")) == initial_view_calls

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, MilestonesScreen)


def test_gantt_distinguishes_milestone_from_missing_estimate() -> None:
    milestone = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="Gate",
        status="pending",
        estimate_hours=0.0,
        estimate_defined=True,
    )
    missing = Task(
        uuid="22222222-2222-2222-2222-222222222222",
        description="Unknown",
        status="pending",
    )

    summary = TaskwarriorApp._gantt_summary([missing, milestone])

    assert "11111111 | * | 0.00-0.00h | ◆ | Gate" in summary
    assert "22222222 | * | 0.00-0.00h | · | Unknown" in summary
    assert "Unestimated tasks shown as ·: 22222222" in summary


def test_timewarrior_trend_supports_30_day_current_week_and_current_month() -> None:
    task = Task(
        uuid="81818181-1111-1111-1111-111111111111",
        description="Tracked",
        status="pending",
        project="Work",
    )
    intervals = (
        TimewarriorInterval(
            task_uuid=task.uuid,
            start=datetime(2026, 9, 1, 8, 0, tzinfo=UTC),
            end=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
        ),
        TimewarriorInterval(
            task_uuid=task.uuid,
            start=datetime(2026, 9, 21, 8, 0, tzinfo=UTC),
            end=datetime(2026, 9, 21, 9, 0, tzinfo=UTC),
        ),
        TimewarriorInterval(
            task_uuid=task.uuid,
            start=datetime(2026, 9, 23, 8, 0, tzinfo=UTC),
            end=datetime(2026, 9, 23, 11, 0, tzinfo=UTC),
        ),
    )
    settings = PlanningSettings(timezone="UTC")
    now = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)

    last_30 = TaskwarriorApp._timewarrior_trend(
        [task], intervals, settings, now=now, period="30d"
    )
    current_week = TaskwarriorApp._timewarrior_trend(
        [task], intervals, settings, now=now, period="week"
    )
    current_month = TaskwarriorApp._timewarrior_trend(
        [task], intervals, settings, now=now, period="month"
    )

    assert "Last 30 local days through 2026-09-23 (UTC)" in last_30
    assert "Tracked in window: 6.00h" in last_30
    assert "Current week 2026-09-21 through 2026-09-27 (UTC)" in current_week
    assert "Tracked in window: 4.00h" in current_week
    assert "Current month 2026-09-01 through 2026-09-30 (UTC)" in current_month
    assert "Tracked in window: 6.00h" in current_month


def test_timewarrior_trend_compares_with_previous_equivalent_window() -> None:
    task = Task(
        uuid="91919191-1111-1111-1111-111111111111",
        description="Tracked",
        status="pending",
        project="Work",
    )
    intervals = (
        TimewarriorInterval(
            task_uuid=task.uuid,
            start=datetime(2026, 9, 10, 8, 0, tzinfo=UTC),
            end=datetime(2026, 9, 10, 10, 0, tzinfo=UTC),
        ),
        TimewarriorInterval(
            task_uuid=task.uuid,
            start=datetime(2026, 9, 23, 8, 0, tzinfo=UTC),
            end=datetime(2026, 9, 23, 12, 0, tzinfo=UTC),
        ),
    )

    summary = TaskwarriorApp._timewarrior_trend(
        [task],
        intervals,
        PlanningSettings(timezone="UTC"),
        now=datetime(2026, 9, 23, 12, 0, tzinfo=UTC),
        period="7d",
    )

    assert "Tracked in window: 4.00h" in summary
    assert "Previous comparable: 2.00h" in summary
    assert "Change: +2.00h (+100.0%)" in summary
    assert "Work | 4.00h | 2.00h | +2.00h" in summary


def test_timewarrior_trend_reports_new_activity_when_previous_is_zero() -> None:
    task = Task(
        uuid="92929292-1111-1111-1111-111111111111",
        description="New work",
        status="pending",
        project="New",
    )
    interval = TimewarriorInterval(
        task_uuid=task.uuid,
        start=datetime(2026, 9, 23, 8, 0, tzinfo=UTC),
        end=datetime(2026, 9, 23, 9, 0, tzinfo=UTC),
    )

    summary = TaskwarriorApp._timewarrior_trend(
        [task],
        (interval,),
        PlanningSettings(timezone="UTC"),
        now=datetime(2026, 9, 23, 12, 0, tzinfo=UTC),
        period="7d",
    )

    assert "Previous comparable: 0.00h" in summary
    assert "Change: +1.00h (new)" in summary
    assert "New | 1.00h | 0.00h | +1.00h" in summary


def test_timewarrior_trend_week_and_month_compare_period_to_date() -> None:
    task = Task(
        uuid="93939393-1111-1111-1111-111111111111",
        description="Period work",
        status="pending",
        project="Work",
    )
    intervals = (
        TimewarriorInterval(
            task_uuid=task.uuid,
            start=datetime(2026, 9, 14, 8, 0, tzinfo=UTC),
            end=datetime(2026, 9, 14, 9, 0, tzinfo=UTC),
        ),
        TimewarriorInterval(
            task_uuid=task.uuid,
            start=datetime(2026, 9, 16, 8, 0, tzinfo=UTC),
            end=datetime(2026, 9, 16, 9, 0, tzinfo=UTC),
        ),
        TimewarriorInterval(
            task_uuid=task.uuid,
            start=datetime(2026, 8, 1, 8, 0, tzinfo=UTC),
            end=datetime(2026, 8, 1, 11, 0, tzinfo=UTC),
        ),
        TimewarriorInterval(
            task_uuid=task.uuid,
            start=datetime(2026, 8, 23, 8, 0, tzinfo=UTC),
            end=datetime(2026, 8, 23, 9, 0, tzinfo=UTC),
        ),
        TimewarriorInterval(
            task_uuid=task.uuid,
            start=datetime(2026, 9, 21, 8, 0, tzinfo=UTC),
            end=datetime(2026, 9, 21, 12, 0, tzinfo=UTC),
        ),
        TimewarriorInterval(
            task_uuid=task.uuid,
            start=datetime(2026, 9, 1, 8, 0, tzinfo=UTC),
            end=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
        ),
    )
    settings = PlanningSettings(timezone="UTC")
    now = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)

    week = TaskwarriorApp._timewarrior_trend(
        [task], intervals, settings, now=now, period="week"
    )
    month = TaskwarriorApp._timewarrior_trend(
        [task], intervals, settings, now=now, period="month"
    )

    assert "Tracked in window: 4.00h" in week
    assert "Previous comparable: 2.00h" in week
    assert "Tracked in window: 8.00h" in month
    assert "Previous comparable: 4.00h" in month
    assert "Change: +4.00h (+100.0%)" in month


def test_timewarrior_trend_current_month_handles_december_year_boundary() -> None:
    summary = TaskwarriorApp._timewarrior_trend(
        [],
        (),
        PlanningSettings(timezone="UTC"),
        now=datetime(2026, 12, 15, 12, 0, tzinfo=UTC),
        period="month",
    )

    assert "Current month 2026-12-01 through 2026-12-31 (UTC)" in summary


@pytest.mark.parametrize("period", ["", "14d", "quarter"])
def test_timewarrior_trend_rejects_unknown_period(period: str) -> None:
    with pytest.raises(ValueError, match="period"):
        TaskwarriorApp._timewarrior_trend(
            [],
            (),
            PlanningSettings(timezone="UTC"),
            now=datetime(2026, 9, 23, 12, 0, tzinfo=UTC),
            period=period,
        )


def test_timewarrior_trend_splits_intervals_by_local_day_and_projects() -> None:
    infra = Task(
        uuid="51515151-1111-1111-1111-111111111111",
        description="Infra",
        status="pending",
        project="Infra",
    )
    docs = Task(
        uuid="61616161-1111-1111-1111-111111111111",
        description="Docs",
        status="pending",
        project="Docs",
    )
    intervals = (
        TimewarriorInterval(
            task_uuid=infra.uuid,
            start=datetime(2026, 9, 22, 21, 30, tzinfo=UTC),
            end=datetime(2026, 9, 22, 22, 30, tzinfo=UTC),
        ),
        TimewarriorInterval(
            task_uuid=docs.uuid,
            start=datetime(2026, 9, 23, 8, 0, tzinfo=UTC),
            end=datetime(2026, 9, 23, 10, 0, tzinfo=UTC),
        ),
    )

    summary = TaskwarriorApp._timewarrior_trend(
        [infra, docs],
        intervals,
        PlanningSettings(timezone="Europe/Paris"),
        now=datetime(2026, 9, 23, 12, 0, tzinfo=UTC),
        period="7d",
    )

    assert "Last 7 local days through 2026-09-23 (Europe/Paris)" in summary
    assert "2026-09-22 | 0.50h" in summary
    assert "2026-09-23 | 2.50h" in summary
    assert summary.count("| 0.00h") >= 5
    assert "Docs | 2.00h" in summary
    assert "Infra | 1.00h" in summary
    project_section = summary.split("Projects\n", 1)[1]
    assert project_section.index("Docs | 2.00h") < project_section.index("Infra | 1.00h")


def test_timewarrior_trend_clips_to_requested_window_and_handles_no_activity() -> None:
    task = Task(
        uuid="71717171-1111-1111-1111-111111111111",
        description="Old",
        status="pending",
        project="Archive",
    )
    old = TimewarriorInterval(
        task_uuid=task.uuid,
        start=datetime(2026, 9, 15, 8, 0, tzinfo=UTC),
        end=datetime(2026, 9, 15, 10, 0, tzinfo=UTC),
    )

    unknown = TimewarriorInterval(
        task_uuid="99999999-1111-1111-1111-111111111111",
        start=datetime(2026, 9, 23, 8, 0, tzinfo=UTC),
        end=datetime(2026, 9, 23, 9, 0, tzinfo=UTC),
    )

    summary = TaskwarriorApp._timewarrior_trend(
        [task],
        (old, unknown),
        PlanningSettings(timezone="UTC"),
        now=datetime(2026, 9, 23, 12, 0, tzinfo=UTC),
        days=7,
    )

    assert "Tracked in window: 0.00h" in summary
    assert "Previous comparable: 2.00h" in summary
    assert "Change: -2.00h (-100.0%)" in summary
    assert "Archive | 0.00h | 2.00h | -2.00h" in summary.split("Projects\n", 1)[1]


def test_timewarrior_trend_rejects_nonpositive_window() -> None:
    with pytest.raises(ValueError, match="days"):
        TaskwarriorApp._timewarrior_trend(
            [],
            (),
            PlanningSettings(timezone="UTC"),
            now=datetime(2026, 9, 23, 12, 0, tzinfo=UTC),
            days=0,
        )


async def test_timewarrior_trend_key_opens_screen_without_task_refetch() -> None:
    client = FakeUiClient(tasks=[TASK])
    client.tracked_intervals = (
        TimewarriorInterval(
            task_uuid=TASK.uuid,
            start=datetime(2026, 9, 23, 7, 0, tzinfo=UTC),
            end=datetime(2026, 9, 23, 8, 0, tzinfo=UTC),
        ),
    )
    app = TaskwarriorApp(
        client=client,
        planning_settings=PlanningSettings(timezone="UTC"),
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        initial_view_calls = client.calls.count(("view", "pending"))

        await pilot.press("shift+r")
        await pilot.pause()

        assert isinstance(app.screen, TimewarriorTrendScreen)
        body = str(app.screen.query_one("#timewarrior-trend-body").render())
        assert "Tracked in window: 1.00h" in body
        assert ("timewarrior_intervals", 1) in client.calls
        assert client.calls.count(("view", "pending")) == initial_view_calls

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, TimewarriorTrendScreen)


async def test_timewarrior_trend_screen_switches_period_without_refetch() -> None:
    client = FakeUiClient(tasks=[TASK])
    client.tracked_intervals = (
        TimewarriorInterval(
            task_uuid=TASK.uuid,
            start=datetime(2026, 9, 23, 7, 0, tzinfo=UTC),
            end=datetime(2026, 9, 23, 8, 0, tzinfo=UTC),
        ),
    )
    app = TaskwarriorApp(
        client=client,
        planning_settings=PlanningSettings(timezone="UTC"),
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("shift+r")
        await pilot.pause()

        assert isinstance(app.screen, TimewarriorTrendScreen)
        initial_calls = client.calls.count(("timewarrior_intervals", 1))

        await pilot.press("3")
        await pilot.pause()
        body = str(app.screen.query_one("#timewarrior-trend-body").render())
        assert "Last 30 local days" in body

        await pilot.press("w")
        await pilot.pause()
        body = str(app.screen.query_one("#timewarrior-trend-body").render())
        assert "Current week" in body

        await pilot.press("m")
        await pilot.pause()
        body = str(app.screen.query_one("#timewarrior-trend-body").render())
        assert "Current month" in body

        await pilot.press("7")
        await pilot.pause()
        body = str(app.screen.query_one("#timewarrior-trend-body").render())
        assert "Last 7 local days" in body

        assert client.calls.count(("timewarrior_intervals", 1)) == initial_calls


async def test_timewarrior_trend_does_not_open_when_timewarrior_fails() -> None:
    client = FakeUiClient(tasks=SEARCH_TASKS)
    client.fail = "timewarrior_intervals"
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("shift+r")
        await pilot.pause()

        assert not isinstance(app.screen, TimewarriorTrendScreen)
        assert "timewarrior_intervals failed" in str(app.query_one("#details").render())


def test_timewarrior_report_summarizes_tracked_remaining_and_progress() -> None:
    active = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="Active work",
        status="pending",
        project="Infra",
        estimate_hours=4.0,
    )
    overrun = Task(
        uuid="22222222-1111-1111-1111-111111111111",
        description="Overrun",
        status="pending",
        project="Docs",
        estimate_hours=1.0,
    )
    missing = Task(
        uuid="33333333-1111-1111-1111-111111111111",
        description="Unestimated",
        status="pending",
        project="Docs",
    )
    milestone = Task(
        uuid="44444444-1111-1111-1111-111111111111",
        description="Gate",
        status="pending",
        project="Infra",
        estimate_hours=0.0,
        estimate_defined=True,
    )
    tracked = {
        active.uuid: 1.5,
        overrun.uuid: 1.25,
        missing.uuid: 0.5,
    }

    summary = TaskwarriorApp._timewarrior_report(
        [missing, milestone, active, overrun],
        PlanningSettings(timezone="UTC"),
        now=datetime(2026, 9, 23, 12, 0, tzinfo=UTC),
        tracked_hours=tracked,
    )

    assert summary.splitlines()[0] == (
        "Tracked total: 3.25h | Estimated total: 5.00h | Remaining total: 2.50h"
    )
    assert (
        "11111111 | Infra | 4.00h | 1.50h | 2.50h | 37.5% | Active work"
        in summary
    )
    assert (
        "22222222 | Docs | 1.00h | 1.25h | 0.00h | 125.0% | Overrun"
        in summary
    )
    assert "33333333 | Docs | — | 0.50h | — | — | Unestimated" in summary
    assert "44444444 | Infra | 0.00h | 0.00h | 0.00h | milestone | Gate" in summary

    rows = summary.splitlines()[3:]
    assert rows[0].startswith("11111111 |")
    assert rows[1].startswith("22222222 |")


def test_timewarrior_report_handles_empty_view() -> None:
    assert (
        TaskwarriorApp._timewarrior_report(
            [],
            PlanningSettings(timezone="UTC"),
            now=datetime(2026, 9, 23, 12, 0, tzinfo=UTC),
            tracked_hours={},
        )
        == "No tasks in current view."
    )


async def test_timewarrior_report_key_opens_report_without_refetch() -> None:
    client = FakeUiClient(tasks=[TASK])
    client.tracked_hours = {TASK.uuid: 1.0}
    app = TaskwarriorApp(
        client=client,
        planning_settings=PlanningSettings(timezone="UTC"),
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        initial_view_calls = client.calls.count(("view", "pending"))

        await pilot.press("shift+t")
        await pilot.pause()

        assert isinstance(app.screen, TimewarriorReportScreen)
        body = str(app.screen.query_one("#timewarrior-report-body").render())
        assert "Tracked total: 1.00h" in body
        assert "2.50h | 1.00h | 1.50h | 40.0%" in body
        assert client.calls.count(("view", "pending")) == initial_view_calls

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, TimewarriorReportScreen)


def test_resolve_planning_dependencies_expands_unique_prefixes_and_deduplicates() -> None:
    target = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="Target",
        status="pending",
    )
    first = Task(
        uuid="aaaaaaaa-1111-1111-1111-111111111111",
        description="First",
        status="pending",
    )
    second = Task(
        uuid="bbbbbbbb-1111-1111-1111-111111111111",
        description="Second",
        status="pending",
    )

    resolved = TaskwarriorApp._resolve_planning_dependencies(
        "aaaaaaaa, bbbbbbbb, aaaaaaaa",
        target,
        [target, first, second],
    )

    assert resolved == f"{first.uuid},{second.uuid}"


def test_resolve_planning_dependencies_rejects_self_unknown_and_ambiguous_prefixes() -> None:
    target = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="Target",
        status="pending",
    )
    ambiguous_a = Task(
        uuid="aaaaaaaa-1111-1111-1111-111111111111",
        description="A",
        status="pending",
    )
    ambiguous_b = Task(
        uuid="aaaaaaab-1111-1111-1111-111111111111",
        description="B",
        status="pending",
    )

    with pytest.raises(TaskwarriorError, match="itself"):
        TaskwarriorApp._resolve_planning_dependencies(
            target.short_uuid,
            target,
            [target, ambiguous_a, ambiguous_b],
        )
    with pytest.raises(TaskwarriorError, match="unknown"):
        TaskwarriorApp._resolve_planning_dependencies(
            "deadbeef",
            target,
            [target, ambiguous_a, ambiguous_b],
        )
    with pytest.raises(TaskwarriorError, match="ambiguous"):
        TaskwarriorApp._resolve_planning_dependencies(
            "aaaa",
            target,
            [target, ambiguous_a, ambiguous_b],
        )


def test_validate_planning_dependency_update_rejects_new_cycle() -> None:
    first = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="First",
        status="pending",
        depends=("22222222-1111-1111-1111-111111111111",),
    )
    second = Task(
        uuid="22222222-1111-1111-1111-111111111111",
        description="Second",
        status="pending",
    )

    with pytest.raises(TaskwarriorError, match="cycle"):
        TaskwarriorApp._validate_planning_dependency_update(
            second,
            first.uuid,
            [first, second],
        )


def test_validate_planning_dependency_update_accepts_acyclic_change() -> None:
    first = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="First",
        status="pending",
    )
    second = Task(
        uuid="22222222-1111-1111-1111-111111111111",
        description="Second",
        status="pending",
    )

    TaskwarriorApp._validate_planning_dependency_update(
        second,
        first.uuid,
        [first, second],
    )


def test_planning_form_initializes_fields_and_candidate_reference() -> None:
    target = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="Target",
        status="pending",
        due="20261001T000000Z",
        wait="20260925T080000Z",
        scheduled="20260926T090000Z",
        depends=("aaaaaaaa-1111-1111-1111-111111111111",),
        estimate_hours=3.5,
    )
    candidate = Task(
        uuid="aaaaaaaa-1111-1111-1111-111111111111",
        description="Dependency",
        status="pending",
        project="Infra",
    )
    form = PlanningForm(target, [target, candidate])

    assert "aaaaaaaa | Infra | Dependency" in form.candidate_body


async def test_planning_form_submits_planning_values() -> None:
    target = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="Target",
        status="pending",
        depends=("aaaaaaaa-1111-1111-1111-111111111111",),
        estimate_hours=3.5,
    )
    candidate = Task(
        uuid="aaaaaaaa-1111-1111-1111-111111111111",
        description="Dependency",
        status="pending",
    )
    app = TaskwarriorApp(client=FakeUiClient(tasks=[target, candidate]))

    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(PlanningForm(target, [target, candidate]))
        await pilot.pause()

        form = app.screen
        assert isinstance(form, PlanningForm)
        form.query_one("#planning-due", Input).value = "2026-10-01"
        form.query_one("#planning-wait", Input).value = "2026-09-25 08:00"
        form.query_one("#planning-scheduled", Input).value = "2026-09-26 09:00"
        form.query_one("#planning-depends", Input).value = "aaaaaaaa"
        form.query_one("#planning-estimate", Input).value = "5.5"
        form.on_button_pressed(Button.Pressed(form.query_one("#planning-save", Button)))
        await pilot.pause()

        assert not isinstance(app.screen, PlanningForm)


async def test_planning_form_cancel_returns_none_and_handles_no_candidates() -> None:
    target = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="Target",
        status="pending",
    )
    client = FakeUiClient(tasks=[target])
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("shift+e")
        await pilot.pause()

        assert isinstance(app.screen, PlanningForm)
        assert "(none)" in app.screen.candidate_body
        app.screen.on_button_pressed(
            Button.Pressed(app.screen.query_one("#planning-cancel", Button))
        )
        await pilot.pause()

        assert not isinstance(app.screen, PlanningForm)
        assert ("modify_planning", target.short_uuid) not in client.calls


async def test_planning_editor_noops_without_selected_task() -> None:
    client = FakeUiClient(tasks=[])
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("shift+e")
        await pilot.pause()

        assert not isinstance(app.screen, PlanningForm)
        assert not any(call[0] == "expand_dependencies" for call in client.calls)


async def test_planning_editor_updates_only_planning_fields_and_refreshes() -> None:
    target = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="Target",
        status="pending",
        depends=("aaaaaaaa-1111-1111-1111-111111111111",),
        estimate_hours=3.5,
    )
    dependency = Task(
        uuid="aaaaaaaa-1111-1111-1111-111111111111",
        description="Dependency",
        status="pending",
    )
    client = FakeUiClient(tasks=[target, dependency])
    client.expanded_tasks = [target, dependency]
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("shift+e")
        await pilot.pause()

        assert isinstance(app.screen, PlanningForm)
        app.screen.query_one("#planning-due", Input).value = "2026-10-01"
        app.screen.query_one("#planning-wait", Input).value = ""
        app.screen.query_one("#planning-scheduled", Input).value = "2026-09-26 09:00"
        app.screen.query_one("#planning-depends", Input).value = "aaaaaaaa"
        app.screen.query_one("#planning-estimate", Input).value = "5.5"
        app.screen.on_button_pressed(
            Button.Pressed(app.screen.query_one("#planning-save", Button))
        )
        await pilot.pause()

        assert ("expand_dependencies", app.planning_settings.dependency_depth) in client.calls
        assert ("modify_planning", target.short_uuid) in client.calls
        assert client.planning_values[-1] == {
            "due": "2026-10-01",
            "wait": "",
            "scheduled": "2026-09-26 09:00",
            "depends": dependency.uuid,
            "estimate": "5.5",
        }
        assert client.calls.count(("view", "pending")) >= 2


async def test_planning_editor_rejects_dependency_cycle_without_modification() -> None:
    first = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="First",
        status="pending",
        depends=("22222222-1111-1111-1111-111111111111",),
    )
    second = Task(
        uuid="22222222-1111-1111-1111-111111111111",
        description="Second",
        status="pending",
    )
    client = FakeUiClient(tasks=[second, first])
    client.expanded_tasks = [second, first]
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("shift+e")
        await pilot.pause()

        assert isinstance(app.screen, PlanningForm)
        app.screen.query_one("#planning-depends", Input).value = first.short_uuid
        app.screen.on_button_pressed(
            Button.Pressed(app.screen.query_one("#planning-save", Button))
        )
        await pilot.pause()

        assert ("modify_planning", second.short_uuid) not in client.calls
        assert "dependency cycle" in str(app.query_one("#details").render())


async def test_planning_editor_rejects_invalid_dependency_without_modification() -> None:
    target = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="Target",
        status="pending",
    )
    client = FakeUiClient(tasks=[target])
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("shift+e")
        await pilot.pause()

        assert isinstance(app.screen, PlanningForm)
        app.screen.query_one("#planning-depends", Input).value = "deadbeef"
        app.screen.on_button_pressed(
            Button.Pressed(app.screen.query_one("#planning-save", Button))
        )
        await pilot.pause()

        assert ("modify_planning", target.short_uuid) not in client.calls
        assert "unknown dependency" in str(app.query_one("#details").render())


async def test_planning_editor_does_not_open_when_dependency_expansion_fails() -> None:
    client = FakeUiClient(tasks=SEARCH_TASKS)
    client.fail = "expand_dependencies"
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("shift+e")
        await pilot.pause()

        assert not isinstance(app.screen, PlanningForm)
        assert "expand_dependencies failed" in str(app.query_one("#details").render())


async def test_planning_editor_handles_modify_failure_without_refresh() -> None:
    target = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="Target",
        status="pending",
    )
    client = FakeUiClient(tasks=[target])
    client.fail = "modify_planning"
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        initial_view_calls = client.calls.count(("view", "pending"))
        await pilot.press("shift+e")
        await pilot.pause()

        assert isinstance(app.screen, PlanningForm)
        app.screen.on_button_pressed(
            Button.Pressed(app.screen.query_one("#planning-save", Button))
        )
        await pilot.pause()

        assert client.calls.count(("view", "pending")) == initial_view_calls
        assert "modify_planning failed" in str(app.query_one("#details").render())


async def test_timewarrior_report_does_not_open_when_timewarrior_fails() -> None:
    client = FakeUiClient(tasks=SEARCH_TASKS)
    client.fail = "timewarrior_hours"
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("shift+t")
        await pilot.pause()

        assert not isinstance(app.screen, TimewarriorReportScreen)
        assert "timewarrior_hours failed" in str(app.query_one("#details").render())


def test_project_overview_does_not_count_milestones_as_unestimated() -> None:
    milestone = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="Gate",
        status="pending",
        project="Release",
        estimate_hours=0.0,
        estimate_defined=True,
    )
    missing = Task(
        uuid="22222222-2222-2222-2222-222222222222",
        description="Unknown",
        status="pending",
        project="Release",
    )

    summary = TaskwarriorApp._project_overview(
        [milestone, missing],
        PlanningSettings(timezone="UTC"),
        now=datetime(2026, 9, 23, 8, 0, tzinfo=UTC),
        tracked_hours={},
    )

    assert "Release | 2 | 0 | 0 | 0.00h | 0.00h | 0.00h | 1 | 0.00" in summary


def test_project_overview_groups_current_view_deterministically() -> None:
    summary = TaskwarriorApp._project_overview(
        SEARCH_TASKS,
        PlanningSettings(timezone="UTC"),
        now=datetime(2026, 9, 23, 8, 0, tzinfo=UTC),
        tracked_hours={},
    )

    assert summary.splitlines() == [
        "Project | Tasks | Active | Blocked | Estimate | Tracked | Remaining | Unestimated | Urgency",
        "Docs | 1 | 0 | 0 | 0.00h | 0.00h | 0.00h | 1 | 4.00",
        "Infra | 1 | 0 | 1 | 0.00h | 0.00h | 0.00h | 1 | 12.00",
        "(none) | 1 | 0 | 0 | 0.00h | 0.00h | 0.00h | 1 | 1.00",
    ]


def test_project_overview_counts_active_tasks() -> None:
    active = Task(
        uuid="dddddddd-1111-2222-3333-444444444444",
        description="Active project task",
        status="pending",
        project="Infra",
        start="20260923T070000Z",
        urgency=3.5,
    )

    summary = TaskwarriorApp._project_overview(
        [*SEARCH_TASKS, active],
        PlanningSettings(timezone="UTC"),
        now=datetime(2026, 9, 23, 8, 0, tzinfo=UTC),
        tracked_hours={},
    )

    assert "Infra | 2 | 1 | 1 | 0.00h | 0.00h | 0.00h | 2 | 15.50" in summary


def test_project_overview_sums_estimates_and_counts_missing() -> None:
    estimated = Task(
        uuid="eeeeeeee-1111-2222-3333-444444444444",
        description="Estimated",
        status="pending",
        project="Infra",
        estimate_hours=2.5,
        urgency=2.0,
    )
    unestimated = Task(
        uuid="ffffffff-1111-2222-3333-444444444444",
        description="Missing estimate",
        status="pending",
        project="Infra",
        urgency=1.0,
    )

    summary = TaskwarriorApp._project_overview(
        [estimated, unestimated],
        PlanningSettings(timezone="UTC"),
        now=datetime(2026, 9, 23, 8, 0, tzinfo=UTC),
        tracked_hours={estimated.uuid: 1.0},
    )

    assert "Infra | 2 | 0 | 0 | 2.50h | 1.00h | 1.50h | 1 | 3.00" in summary


def test_project_overview_uses_tracked_hours_for_stopped_partial_work() -> None:
    task = Task(
        uuid="12121212-1111-2222-3333-444444444444",
        description="Partial",
        status="pending",
        project="Infra",
        estimate_hours=4.0,
    )

    summary = TaskwarriorApp._project_overview(
        [task],
        PlanningSettings(timezone="UTC"),
        now=datetime(2026, 9, 23, 8, 0, tzinfo=UTC),
        tracked_hours={task.uuid: 1.25},
    )

    assert "Infra | 1 | 0 | 0 | 4.00h | 1.25h | 2.75h | 0 | 0.00" in summary


def test_project_overview_handles_empty_view() -> None:
    assert TaskwarriorApp._project_overview([]) == "No tasks in current view."


async def test_project_overview_does_not_open_when_timewarrior_fails() -> None:
    client = FakeUiClient(tasks=SEARCH_TASKS)
    client.fail = "timewarrior_hours"
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("shift+p")
        await pilot.pause()

        assert not isinstance(app.screen, ProjectOverviewScreen)
        assert "timewarrior_hours failed" in str(app.query_one("#details").render())


async def test_project_overview_key_opens_local_screen_without_refetch() -> None:
    client = FakeUiClient(tasks=SEARCH_TASKS)
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        initial_view_calls = client.calls.count(("view", "pending"))

        await pilot.press("shift+p")
        await pilot.pause()

        assert isinstance(app.screen, ProjectOverviewScreen)
        body = str(app.screen.query_one("#project-overview-body").render())
        assert "Docs | 1 | 0 | 0 | 0.00h | 0.00h | 0.00h | 1 | 4.00" in body
        assert "Infra | 1 | 0 | 1 | 0.00h | 0.00h | 0.00h | 1 | 12.00" in body
        assert ("timewarrior_hours", 3) in client.calls
        assert client.calls.count(("view", "pending")) == initial_view_calls

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, ProjectOverviewScreen)


async def test_selected_task_is_none_with_empty_table() -> None:
    app = TaskwarriorApp(client=FakeUiClient(tasks=[]))
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app._selected_task() is None
        app.action_start_task()
        app.action_edit_task()
        app.action_delete_task()
        app.action_inspect_task()


async def test_edit_key_opens_prefilled_task_form() -> None:
    app = TaskwarriorApp(client=FakeUiClient())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        assert isinstance(app.screen, TaskForm)
        assert app.screen.initial_task == TASK
        assert app.screen.query_one("#description").value == "Vérifier mail de RMS"
        assert app.screen.query_one("#priority").value == "L"
        assert app.screen.query_one("#due").value == "2026-09-26"
        assert app.screen.query_one("#tags").value == "mail,rms"
        assert app.screen.query_one("#wait").value == "2026-09-24 08:00"
        assert app.screen.query_one("#scheduled").value == "2026-09-24 09:00"
        assert app.screen.query_one("#depends").value == (
            "11111111-1111-1111-1111-111111111111"
        )
        assert app.screen.query_one("#estimate").value == "2.5"


async def test_add_form_save_calls_client() -> None:
    client = FakeUiClient()
    app = TaskwarriorApp(client=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        form = app.screen
        form.query_one("#description", Input).value = "New task"
        form.query_one("#project", Input).value = "Project"
        form.query_one("#priority", Input).value = "m"
        form.query_one("#due", Input).value = "2026-10-01"
        form.query_one("#tags", Input).value = "home, next"
        form.query_one("#wait", Input).value = "2026-09-30 08:00"
        form.query_one("#scheduled", Input).value = "2026-09-30 09:00"
        form.query_one("#depends", Input).value = "aaaaaaaa, bbbbbbbb"
        form.query_one("#estimate", Input).value = "1.5"
        form.on_button_pressed(Button.Pressed(form.query_one("#save", Button)))
        await pilot.pause()
    assert ("add", "New task") in client.calls
    assert client.add_values[-1]["estimate"] == "1.5"


async def test_add_form_cancel_does_not_create_task() -> None:
    client = FakeUiClient()
    app = TaskwarriorApp(client=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        form = app.screen
        form.on_button_pressed(Button.Pressed(form.query_one("#cancel", Button)))
        await pilot.pause()

    assert ("view", "pending") in client.calls
    assert not any(action == "add" for action, _ in client.calls)


async def test_add_error_is_rendered() -> None:
    client = FakeUiClient()
    client.fail = "add"
    app = TaskwarriorApp(client=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        form = app.screen
        form.query_one("#description", Input).value = "New task"
        form.on_button_pressed(Button.Pressed(form.query_one("#save", Button)))
        await pilot.pause()
        assert "add failed" in str(app.query_one("#details").render())


async def test_edit_form_save_calls_modify() -> None:
    client = FakeUiClient()
    app = TaskwarriorApp(client=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        form = app.screen
        form.query_one("#description", Input).value = "Changed"
        form.query_one("#tags", Input).value = "mail,work"
        form.query_one("#wait", Input).value = ""
        form.query_one("#scheduled", Input).value = "tomorrow 09:00"
        form.query_one("#depends", Input).value = "22222222"
        form.query_one("#estimate", Input).value = "4"
        form.on_button_pressed(Button.Pressed(form.query_one("#save", Button)))
        await pilot.pause()

    assert ("modify", TASK.short_uuid) in client.calls
    assert client.modify_values[-1] == {
        "description": "Changed",
        "project": "",
        "priority": "L",
        "due": "2026-09-26",
        "tags": "mail,work",
        "wait": "",
        "scheduled": "tomorrow 09:00",
        "depends": "22222222",
        "estimate": "4",
        "previous_tags": ("mail", "rms"),
    }


async def test_edit_form_cancel_does_not_modify() -> None:
    client = FakeUiClient()
    app = TaskwarriorApp(client=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        form = app.screen
        form.on_button_pressed(Button.Pressed(form.query_one("#cancel", Button)))
        await pilot.pause()
    assert ("modify", TASK.short_uuid) not in client.calls


async def test_edit_error_is_rendered() -> None:
    client = FakeUiClient()
    client.fail = "modify"
    app = TaskwarriorApp(client=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        form = app.screen
        form.query_one("#description", Input).value = "Changed"
        form.on_button_pressed(Button.Pressed(form.query_one("#save", Button)))
        await pilot.pause()
        assert "modify failed" in str(app.query_one("#details").render())


async def test_empty_description_does_not_close_form() -> None:
    app = TaskwarriorApp(client=FakeUiClient())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        form = app.screen
        form.query_one("#description", Input).value = "   "
        form.on_button_pressed(Button.Pressed(form.query_one("#save", Button)))
        await pilot.pause()
        assert isinstance(app.screen, TaskForm)


async def test_form_ignores_unrelated_button() -> None:
    app = TaskwarriorApp(client=FakeUiClient())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        form = app.screen
        form.on_button_pressed(Button.Pressed(Button("Other", id="other")))
        assert isinstance(app.screen, TaskForm)


async def test_inspect_success() -> None:
    client = FakeUiClient()
    app = TaskwarriorApp(client=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert ("information", TASK.short_uuid) in client.calls
        assert "task information" in str(app.query_one("#details").render())


async def test_inspect_error_is_rendered() -> None:
    client = FakeUiClient()
    client.fail = "information"
    app = TaskwarriorApp(client=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert "information failed" in str(app.query_one("#details").render())


async def test_delete_key_opens_confirmation_screen() -> None:
    app = TaskwarriorApp(client=FakeUiClient())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("shift+d")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDelete)
        assert app.screen.target_task == TASK


async def test_delete_confirmation_calls_client() -> None:
    client = FakeUiClient()
    app = TaskwarriorApp(client=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("shift+d")
        await pilot.pause()
        screen = app.screen
        screen.on_button_pressed(Button.Pressed(screen.query_one("#delete", Button)))
        await pilot.pause()
    assert ("delete", TASK.short_uuid) in client.calls


async def test_delete_cancel_does_not_call_client() -> None:
    client = FakeUiClient()
    app = TaskwarriorApp(client=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("shift+d")
        await pilot.pause()
        screen = app.screen
        screen.on_button_pressed(Button.Pressed(screen.query_one("#cancel", Button)))
        await pilot.pause()
    assert ("delete", TASK.short_uuid) not in client.calls


async def test_delete_error_is_rendered() -> None:
    client = FakeUiClient()
    client.fail = "delete"
    app = TaskwarriorApp(client=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("shift+d")
        await pilot.pause()
        screen = app.screen
        screen.on_button_pressed(Button.Pressed(screen.query_one("#delete", Button)))
        await pilot.pause()
        assert "delete failed" in str(app.query_one("#details").render())


async def test_lifecycle_keys_call_client_with_short_uuid() -> None:
    client = FakeUiClient()
    app = TaskwarriorApp(client=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("s")
        await pilot.press("x")
        await pilot.press("enter")
        await pilot.press("y")
        await pilot.press("d")
        await pilot.pause()
    assert ("start", TASK.short_uuid) in client.calls
    assert ("stop", TASK.short_uuid) in client.calls
    assert ("information", TASK.short_uuid) in client.calls
    assert ("sync", "") in client.calls
    assert ("done", TASK.short_uuid) in client.calls


async def test_backend_error_is_rendered_in_details() -> None:
    client = FakeUiClient()
    client.fail = "start"
    app = TaskwarriorApp(client=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()
        assert "start failed" in str(app.query_one("#details").render())


async def test_sync_error_is_rendered() -> None:
    client = FakeUiClient()
    client.fail = "sync"
    app = TaskwarriorApp(client=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
        assert "sync failed" in str(app.query_one("#details").render())


async def test_view_error_does_not_crash_app() -> None:
    client = FakeUiClient()
    client.fail = "view"
    app = TaskwarriorApp(client=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert "view failed" in str(app.query_one("#details").render())


async def test_numeric_keys_switch_views_and_refresh() -> None:
    client = FakeUiClient()
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        for key, expected in [
            ("2", "waiting"),
            ("3", "completed"),
            ("4", "deleted"),
            ("5", "scheduled"),
            ("1", "pending"),
        ]:
            await pilot.press(key)
            await pilot.pause()
            assert app.current_view == expected
            assert ("view", expected) in client.calls



def test_search_matches_description_project_and_tags_case_insensitively() -> None:
    assert TaskwarriorApp._matches_search(SEARCH_TASKS[0], "RELEASE") is True
    assert TaskwarriorApp._matches_search(SEARCH_TASKS[1], "infra") is True
    assert TaskwarriorApp._matches_search(SEARCH_TASKS[1], "MAIL") is True
    assert TaskwarriorApp._matches_search(SEARCH_TASKS[2], "database") is False


@pytest.mark.parametrize("sort_key", ["urgency", "when", "project", "priority"])
def test_sort_cycle_breaks_short_uuid_ties_with_full_uuid(sort_key: str) -> None:
    first = Task(
        uuid="aaaaaaaa-0000-0000-0000-000000000001",
        description="First collision",
        status="pending",
        urgency=1.0,
        due="20260925T080000Z",
        project="same",
        priority="M",
    )
    second = Task(
        uuid="aaaaaaaa-0000-0000-0000-000000000002",
        description="Second collision",
        status="pending",
        urgency=1.0,
        due="20260925T080000Z",
        project="same",
        priority="M",
    )

    ordered = TaskwarriorApp._sort_tasks([second, first], sort_key)

    assert [task.uuid for task in ordered] == [first.uuid, second.uuid]


def test_sort_cycle_is_deterministic() -> None:
    assert [task.short_uuid for task in TaskwarriorApp._sort_tasks(SEARCH_TASKS, "urgency")] == [
        "bbbbbbbb",
        "aaaaaaaa",
        "cccccccc",
    ]
    assert [task.short_uuid for task in TaskwarriorApp._sort_tasks(SEARCH_TASKS, "when")] == [
        "bbbbbbbb",
        "aaaaaaaa",
        "cccccccc",
    ]

    waiting_tasks = [
        Task(
            uuid="dddddddd-1111-2222-3333-444444444444",
            description="Wait first",
            status="waiting",
            wait="20260924T080000Z",
        ),
        Task(
            uuid="eeeeeeee-1111-2222-3333-444444444444",
            description="Wait later",
            status="waiting",
            wait="20260925T080000Z",
        ),
    ]
    assert [
        task.short_uuid
        for task in TaskwarriorApp._sort_tasks(waiting_tasks, "when", "waiting")
    ] == ["dddddddd", "eeeeeeee"]

    completed_tasks = [
        Task(
            uuid="ffffffff-1111-2222-3333-444444444444",
            description="Completed first",
            status="completed",
            end="20260924T080000Z",
        ),
        Task(
            uuid="99999999-1111-2222-3333-444444444444",
            description="Completed later",
            status="completed",
            end="20260925T080000Z",
        ),
    ]
    assert [
        task.short_uuid
        for task in TaskwarriorApp._sort_tasks(completed_tasks, "when", "completed")
    ] == ["ffffffff", "99999999"]
    assert [
        task.short_uuid
        for task in TaskwarriorApp._sort_tasks(completed_tasks, "when", "deleted")
    ] == ["ffffffff", "99999999"]

    scheduled_tasks = [
        Task(
            uuid="12121212-1111-2222-3333-444444444444",
            description="Scheduled first",
            status="pending",
            scheduled="20260924T080000Z",
        ),
        Task(
            uuid="34343434-1111-2222-3333-444444444444",
            description="Scheduled later",
            status="pending",
            scheduled="20260925T080000Z",
        ),
    ]
    assert [
        task.short_uuid
        for task in TaskwarriorApp._sort_tasks(scheduled_tasks, "when", "scheduled")
    ] == ["12121212", "34343434"]
    assert [task.short_uuid for task in TaskwarriorApp._sort_tasks(SEARCH_TASKS, "project")] == [
        "aaaaaaaa",
        "bbbbbbbb",
        "cccccccc",
    ]
    assert [task.short_uuid for task in TaskwarriorApp._sort_tasks(SEARCH_TASKS, "priority")] == [
        "bbbbbbbb",
        "aaaaaaaa",
        "cccccccc",
    ]
    assert TaskwarriorApp._sort_tasks(SEARCH_TASKS, None) == SEARCH_TASKS


async def test_search_key_opens_search_form_and_enter_filters_locally() -> None:
    client = FakeUiClient(tasks=SEARCH_TASKS)
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        initial_view_calls = client.calls.count(("view", "pending"))
        await pilot.press("/")
        await pilot.pause()
        assert isinstance(app.screen, SearchForm)
        search = app.screen.query_one("#search", Input)
        search.value = "mail"
        app.screen.on_input_submitted(Input.Submitted(search, search.value))
        await pilot.pause()

        assert app.search_query == "mail"
        assert app.query_one("#tasks").row_count == 1
        assert app._selected_task() == SEARCH_TASKS[1]
        assert client.calls.count(("view", "pending")) == initial_view_calls


async def test_empty_search_restores_full_current_view_without_refetch() -> None:
    client = FakeUiClient(tasks=SEARCH_TASKS)
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        app._apply_search("mail")
        assert app.query_one("#tasks").row_count == 1
        initial_view_calls = client.calls.count(("view", "pending"))

        app._apply_search("")

        assert app.search_query == ""
        assert app.query_one("#tasks").row_count == 3
        assert client.calls.count(("view", "pending")) == initial_view_calls


async def test_escape_in_search_restores_full_current_view() -> None:
    client = FakeUiClient(tasks=SEARCH_TASKS)
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        app._apply_search("mail")
        await pilot.press("/")
        await pilot.pause()
        assert isinstance(app.screen, SearchForm)
        await pilot.press("escape")
        await pilot.pause()

        assert app.search_query == ""
        assert app.query_one("#tasks").row_count == 3


async def test_sort_key_cycles_locally_without_refetch() -> None:
    client = FakeUiClient(tasks=SEARCH_TASKS)
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        initial_view_calls = client.calls.count(("view", "pending"))
        expected = ["urgency", "when", "project", "priority", None]
        for sort_key in expected:
            await pilot.press("t")
            await pilot.pause()
            assert app.sort_key == sort_key
        assert client.calls.count(("view", "pending")) == initial_view_calls



def test_dependency_marker_reflects_unresolved_dependencies() -> None:
    blocked = SEARCH_TASKS[1]
    ready = SEARCH_TASKS[0]

    assert TaskwarriorApp._task_row(blocked, "pending")[2] == "◆"
    assert TaskwarriorApp._task_row(ready, "pending")[2] == ""


def test_project_filter_is_exact_and_case_insensitive() -> None:
    assert TaskwarriorApp._matches_project(SEARCH_TASKS[1], "infra") is True
    assert TaskwarriorApp._matches_project(SEARCH_TASKS[1], "INFRA") is True
    assert TaskwarriorApp._matches_project(SEARCH_TASKS[1], "inf") is False
    assert TaskwarriorApp._matches_project(SEARCH_TASKS[2], "") is True


async def test_blocked_filter_toggles_locally_without_refetch() -> None:
    client = FakeUiClient(tasks=SEARCH_TASKS)
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        initial_view_calls = client.calls.count(("view", "pending"))

        await pilot.press("b")
        await pilot.pause()
        assert app.blocked_only is True
        assert app.query_one("#tasks").row_count == 1
        assert app._selected_task() == SEARCH_TASKS[1]

        await pilot.press("b")
        await pilot.pause()
        assert app.blocked_only is False
        assert app.query_one("#tasks").row_count == 3
        assert client.calls.count(("view", "pending")) == initial_view_calls


async def test_escape_in_project_filter_clears_filter() -> None:
    client = FakeUiClient(tasks=SEARCH_TASKS)
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        app._apply_project_filter("infra")
        assert app.project_filter == "infra"
        assert app.query_one("#tasks").row_count == 1

        await pilot.press("p")
        await pilot.pause()
        assert isinstance(app.screen, ProjectFilterForm)
        await pilot.press("escape")
        await pilot.pause()

        assert app.project_filter == ""
        assert app.query_one("#tasks").row_count == 3


async def test_project_filter_form_applies_and_clears_locally() -> None:
    client = FakeUiClient(tasks=SEARCH_TASKS)
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        initial_view_calls = client.calls.count(("view", "pending"))

        await pilot.press("p")
        await pilot.pause()
        assert isinstance(app.screen, ProjectFilterForm)
        project = app.screen.query_one("#project-filter", Input)
        project.value = "infra"
        app.screen.on_input_submitted(Input.Submitted(project, project.value))
        await pilot.pause()

        assert app.project_filter == "infra"
        assert app.query_one("#tasks").row_count == 1
        assert app._selected_task() == SEARCH_TASKS[1]

        await pilot.press("p")
        await pilot.pause()
        project = app.screen.query_one("#project-filter", Input)
        project.value = ""
        app.screen.on_input_submitted(Input.Submitted(project, project.value))
        await pilot.pause()

        assert app.project_filter == ""
        assert app.query_one("#tasks").row_count == 3
        assert client.calls.count(("view", "pending")) == initial_view_calls


async def test_local_filters_combine_and_status_describes_state() -> None:
    client = FakeUiClient(tasks=SEARCH_TASKS)
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        app._apply_search("mail")
        app._apply_project_filter("infra")
        app.action_toggle_blocked()
        app.action_cycle_sort()

        assert app.query_one("#tasks").row_count == 1
        details = str(app.query_one("#details").render())
        assert "search=mail" in details
        assert "project=infra" in details
        assert "blocked" in details
        assert "sort=urgency" in details


def test_tag_filter_is_exact_and_case_insensitive() -> None:
    assert TaskwarriorApp._matches_tag(SEARCH_TASKS[1], "mail") is True
    assert TaskwarriorApp._matches_tag(SEARCH_TASKS[1], "MAIL") is True
    assert TaskwarriorApp._matches_tag(SEARCH_TASKS[1], "mai") is False
    assert TaskwarriorApp._matches_tag(SEARCH_TASKS[2], "") is True


async def test_tag_filter_form_applies_and_clears_locally() -> None:
    client = FakeUiClient(tasks=SEARCH_TASKS)
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        initial_view_calls = client.calls.count(("view", "pending"))

        await pilot.press("f")
        await pilot.pause()
        assert isinstance(app.screen, TagFilterForm)
        tag = app.screen.query_one("#tag-filter", Input)
        tag.value = "mail"
        app.screen.on_input_submitted(Input.Submitted(tag, tag.value))
        await pilot.pause()

        assert app.tag_filter == "mail"
        assert app.query_one("#tasks").row_count == 1
        assert app._selected_task() == SEARCH_TASKS[1]

        await pilot.press("f")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert app.tag_filter == ""
        assert app.query_one("#tasks").row_count == 3
        assert client.calls.count(("view", "pending")) == initial_view_calls


async def test_active_filter_toggles_locally_without_refetch() -> None:
    active = Task(
        uuid="dddddddd-1111-2222-3333-444444444444",
        description="Active work",
        status="pending",
        project="Infra",
        start="20260923T070000Z",
        tags=("work",),
    )
    client = FakeUiClient(tasks=[*SEARCH_TASKS, active])
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        initial_view_calls = client.calls.count(("view", "pending"))

        await pilot.press("v")
        await pilot.pause()
        assert app.active_only is True
        assert app.query_one("#tasks").row_count == 1
        assert app._selected_task() == active

        await pilot.press("v")
        await pilot.pause()
        assert app.active_only is False
        assert app.query_one("#tasks").row_count == 4
        assert client.calls.count(("view", "pending")) == initial_view_calls


async def test_clear_local_state_resets_all_filters_and_sort_without_refetch() -> None:
    active = Task(
        uuid="dddddddd-1111-2222-3333-444444444444",
        description="Active mail",
        status="pending",
        project="Infra",
        start="20260923T070000Z",
        urgency=7.0,
        tags=("mail",),
        depends=("aaaaaaaa-1111-2222-3333-444444444444",),
    )
    client = FakeUiClient(tasks=[*SEARCH_TASKS, active])
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        initial_view_calls = client.calls.count(("view", "pending"))
        app._apply_search("mail")
        app._apply_project_filter("infra")
        app._apply_tag_filter("mail")
        app.action_toggle_blocked()
        app.action_toggle_active()
        app.action_cycle_sort()

        assert app.query_one("#tasks").row_count == 1

        await pilot.press("c")
        await pilot.pause()

        assert app.search_query == ""
        assert app.project_filter == ""
        assert app.tag_filter == ""
        assert app.blocked_only is False
        assert app.active_only is False
        assert app.sort_key is None
        assert app.query_one("#tasks").row_count == 4
        assert client.calls.count(("view", "pending")) == initial_view_calls


async def test_status_describes_tag_and_active_filters() -> None:
    active = Task(
        uuid="dddddddd-1111-2222-3333-444444444444",
        description="Active mail",
        status="pending",
        project="Infra",
        start="20260923T070000Z",
        tags=("mail",),
    )
    app = TaskwarriorApp(client=FakeUiClient(tasks=[active]))

    async with app.run_test() as pilot:
        await pilot.pause()
        app._apply_tag_filter("mail")
        app.action_toggle_active()

        details = str(app.query_one("#details").render())
        assert "tag=mail" in details
        assert "active" in details


async def test_view_change_refetches_then_reapplies_search_and_sort() -> None:
    client = FakeUiClient(tasks=SEARCH_TASKS)
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        app._apply_search("mail")
        app.action_cycle_sort()
        assert app.sort_key == "urgency"

        await pilot.press("2")
        await pilot.pause()

        assert app.current_view == "waiting"
        assert app.search_query == "mail"
        assert app.sort_key == "urgency"
        assert app.query_one("#tasks").row_count == 1
        assert ("view", "waiting") in client.calls


def test_run_launches_application_with_loaded_planning_settings(monkeypatch) -> None:
    launched = []
    settings = PlanningSettings(timezone="UTC", capacity=2)
    monkeypatch.setattr(app_module, "load_planning_settings", lambda: settings)
    monkeypatch.setattr(app_module, "TaskwarriorClient", lambda: FakeUiClient())
    monkeypatch.setattr(
        TaskwarriorApp,
        "run",
        lambda self: launched.append(self.planning_settings),
    )

    app_module.run()

    assert launched == [settings]
