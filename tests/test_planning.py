from taskwarrior_textual.models import Task
from taskwarrior_textual.planning import build_planning_graph


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
