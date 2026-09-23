from taskwarrior_textual.models import Task
from taskwarrior_textual.planning import (
    build_absolute_schedule,
    build_planning_graph,
    build_relative_schedule,
    parse_taskwarrior_datetime,
)


def test_build_planning_graph_resolves_edges_and_orders_deterministically() -> None:
    first = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="First",
        status="pending",
    )
    parallel = Task(
        uuid="22222222-2222-2222-2222-222222222222",
        description="Parallel",
        status="pending",
    )
    last = Task(
        uuid="33333333-1111-1111-1111-111111111111",
        description="Last",
        status="pending",
        depends=(first.uuid, parallel.uuid),
    )

    graph = build_planning_graph([last, parallel, first])

    assert graph.order == (first.uuid, parallel.uuid, last.uuid)
    assert graph.dependencies[last.uuid] == frozenset({first.uuid, parallel.uuid})
    assert graph.successors[first.uuid] == frozenset({last.uuid})
    assert graph.successors[parallel.uuid] == frozenset({last.uuid})
    assert graph.unresolved == ()
    assert graph.cyclic is False


def test_build_planning_graph_keeps_external_dependencies_visible() -> None:
    task = Task(
        uuid="aaaaaaaa-1111-2222-3333-444444444444",
        description="External",
        status="pending",
        depends=("99999999-aaaa-bbbb-cccc-dddddddddddd",),
    )

    graph = build_planning_graph([task])

    assert graph.order == (task.uuid,)
    assert graph.dependencies[task.uuid] == frozenset()
    assert graph.unresolved == (("aaaaaaaa", "99999999"),)
    assert graph.cyclic is False


def test_build_planning_graph_reports_cycles_without_crashing() -> None:
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
    ready = Task(
        uuid="11111111-1111-2222-3333-444444444444",
        description="Ready",
        status="pending",
    )

    graph = build_planning_graph([second, first, ready])

    assert graph.order == (ready.uuid,)
    assert graph.remaining == (first.uuid, second.uuid)
    assert graph.cyclic is True


def test_build_planning_graph_handles_empty_input() -> None:
    graph = build_planning_graph([])

    assert graph.order == ()
    assert graph.remaining == ()
    assert graph.unresolved == ()
    assert graph.cyclic is False



def test_build_relative_schedule_computes_cpm_values() -> None:
    foundation = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="Foundation",
        status="pending",
        estimate_hours=2.0,
    )
    long_branch = Task(
        uuid="22222222-2222-2222-2222-222222222222",
        description="Long",
        status="pending",
        depends=(foundation.uuid,),
        estimate_hours=3.0,
    )
    short_branch = Task(
        uuid="33333333-3333-3333-3333-333333333333",
        description="Short",
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

    schedule = build_relative_schedule(
        build_planning_graph([finish, short_branch, long_branch, foundation])
    )

    assert schedule is not None
    assert schedule.duration == 9.0
    assert schedule.earliest_start[foundation.uuid] == 0.0
    assert schedule.earliest_finish[foundation.uuid] == 2.0
    assert schedule.earliest_start[finish.uuid] == 5.0
    assert schedule.earliest_finish[finish.uuid] == 9.0
    assert schedule.slack[long_branch.uuid] == 0.0
    assert schedule.slack[short_branch.uuid] == 2.0
    assert schedule.critical == frozenset(
        {foundation.uuid, long_branch.uuid, finish.uuid}
    )


def test_build_relative_schedule_handles_independent_and_zero_duration_tasks() -> None:
    zero = Task(
        uuid="aaaaaaaa-1111-2222-3333-444444444444",
        description="Zero",
        status="pending",
    )
    long = Task(
        uuid="bbbbbbbb-1111-2222-3333-444444444444",
        description="Long",
        status="pending",
        estimate_hours=2.0,
    )

    schedule = build_relative_schedule(build_planning_graph([long, zero]))

    assert schedule is not None
    assert schedule.duration == 2.0
    assert schedule.earliest_finish[zero.uuid] == 0.0
    assert schedule.slack[zero.uuid] == 2.0
    assert schedule.critical == frozenset({long.uuid})


def test_build_relative_schedule_returns_none_for_cycles() -> None:
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

    assert build_relative_schedule(build_planning_graph([first, second])) is None


def test_build_relative_schedule_handles_empty_graph() -> None:
    schedule = build_relative_schedule(build_planning_graph([]))

    assert schedule is not None
    assert schedule.duration == 0.0
    assert schedule.earliest_start == {}
    assert schedule.earliest_finish == {}
    assert schedule.latest_start == {}
    assert schedule.slack == {}
    assert schedule.critical == frozenset()



def test_parse_taskwarrior_datetime_accepts_utc_and_rejects_unknown() -> None:
    assert parse_taskwarrior_datetime("") is None
    assert parse_taskwarrior_datetime("tomorrow") is None
    parsed = parse_taskwarrior_datetime("20260924T090000Z")
    assert parsed is not None
    assert parsed.strftime("%Y-%m-%d %H:%M") == "2026-09-24 09:00"


def test_build_absolute_schedule_applies_dependencies_scheduled_and_due() -> None:
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
        description="Delayed",
        status="pending",
        scheduled="20260924T150000Z",
        due="20260924T160000Z",
        depends=(first.uuid,),
        estimate_hours=3.0,
    )
    normal = Task(
        uuid="33333333-3333-3333-3333-333333333333",
        description="Normal",
        status="pending",
        depends=(first.uuid,),
        estimate_hours=1.0,
    )

    schedule = build_absolute_schedule(
        build_planning_graph([delayed, normal, first])
    )

    assert schedule is not None
    assert schedule.origin.strftime("%Y-%m-%d %H:%M") == "2026-09-24 09:00"
    assert schedule.starts[first.uuid].strftime("%H:%M") == "09:00"
    assert schedule.finishes[first.uuid].strftime("%H:%M") == "11:00"
    assert schedule.starts[normal.uuid].strftime("%H:%M") == "11:00"
    assert schedule.starts[delayed.uuid].strftime("%H:%M") == "15:00"
    assert schedule.finishes[delayed.uuid].strftime("%H:%M") == "18:00"
    assert schedule.late_by[delayed.uuid] == 2.0
    assert first.uuid not in schedule.late_by
    assert schedule.due_slack[first.uuid] == 13.0
    assert schedule.due_slack[delayed.uuid] == -2.0
    assert schedule.invalid_due == ()


def test_build_absolute_schedule_tracks_invalid_due_and_no_anchor() -> None:
    no_anchor = Task(
        uuid="aaaaaaaa-1111-2222-3333-444444444444",
        description="No anchor",
        status="pending",
        due="not-a-date",
        estimate_hours=1.0,
    )
    assert build_absolute_schedule(build_planning_graph([no_anchor])) is None

    anchor = Task(
        uuid="bbbbbbbb-1111-2222-3333-444444444444",
        description="Anchor",
        status="pending",
        scheduled="20260924T080000Z",
    )
    invalid = Task(
        uuid="cccccccc-1111-2222-3333-444444444444",
        description="Invalid due",
        status="pending",
        depends=(anchor.uuid,),
        due="not-a-date",
        estimate_hours=1.0,
    )

    schedule = build_absolute_schedule(build_planning_graph([invalid, anchor]))

    assert schedule is not None
    assert schedule.invalid_due == ("cccccccc",)
    assert schedule.late_by == {}
    assert schedule.due_slack == {}


def test_build_absolute_schedule_returns_none_for_cycles() -> None:
    first = Task(
        uuid="aaaaaaaa-1111-2222-3333-444444444444",
        description="First",
        status="pending",
        scheduled="20260924T080000Z",
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

    assert build_absolute_schedule(build_planning_graph([first, second])) is None
