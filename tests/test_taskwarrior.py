import json
from datetime import UTC, datetime

import pytest

from taskwarrior_textual.models import Task
from taskwarrior_textual.taskwarrior import TaskwarriorClient, TaskwarriorError


class FakeClient(TaskwarriorClient):
    def __post_init__(self) -> None:
        self.command = "task"

    def _run(self, args):  # type: ignore[override]
        assert args == ["status:pending", "export"]
        return json.dumps(
            [
                {
                    "uuid": "12345678-1234-1234-1234-123456789abc",
                    "description": "Example",
                    "status": "pending",
                }
            ]
        )


class RecordingClient(TaskwarriorClient):
    def __post_init__(self) -> None:
        self.command = "task"
        self.calls = []

    def _run(self, args):  # type: ignore[override]
        self.calls.append(list(args))
        if list(args) == ["_udas"]:
            return "estimate\n"
        return "ok"


class TimewarriorRecordingClient(TaskwarriorClient):
    def __post_init__(self) -> None:
        self.command = "task"
        self.timewarrior_command = "timew"
        self.timewarrior_output = "[]"
        self.timewarrior_calls: list[list[str]] = []

    def _run_timewarrior(self, args):  # type: ignore[override]
        self.timewarrior_calls.append(list(args))
        return self.timewarrior_output


def test_timewarrior_hours_sums_closed_and_open_intervals_for_unique_task_signature() -> None:
    task = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="Implement planner",
        status="pending",
        project="Work",
        tags=("python",),
        estimate_hours=8.0,
    )
    client = TimewarriorRecordingClient()
    client.timewarrior_output = json.dumps(
        [
            {
                "start": "20260923T080000Z",
                "end": "20260923T090000Z",
                "tags": ["Implement planner", "Work", "python"],
            },
            {
                "start": "20260923T100000Z",
                "tags": ["python", "Work", "Implement planner"],
            },
        ]
    )

    hours = client.timewarrior_hours(
        [task],
        now=datetime(2026, 9, 23, 11, 30, tzinfo=UTC),
    )

    assert hours == {task.uuid: 2.5}
    assert client.timewarrior_calls == [["export"]]


def test_timewarrior_hours_ignores_unmatched_and_ambiguous_task_signatures() -> None:
    first = Task(
        uuid="aaaaaaaa-1111-1111-1111-111111111111",
        description="Same",
        status="pending",
        project="P",
    )
    second = Task(
        uuid="bbbbbbbb-1111-1111-1111-111111111111",
        description="Same",
        status="pending",
        project="P",
    )
    unique = Task(
        uuid="cccccccc-1111-1111-1111-111111111111",
        description="Unique",
        status="pending",
    )
    client = TimewarriorRecordingClient()
    client.timewarrior_output = json.dumps(
        [
            {
                "start": "20260923T080000Z",
                "end": "20260923T090000Z",
                "tags": ["Same", "P"],
            },
            {
                "start": "20260923T090000Z",
                "end": "20260923T100000Z",
                "tags": ["Other"],
            },
            {
                "start": "20260923T100000Z",
                "end": "20260923T103000Z",
                "tags": ["Unique"],
            },
        ]
    )

    hours = client.timewarrior_hours(
        [first, second, unique],
        now=datetime(2026, 9, 23, 11, 0, tzinfo=UTC),
    )

    assert hours == {unique.uuid: 0.5}


def test_timewarrior_hours_returns_empty_when_timewarrior_is_unavailable() -> None:
    client = RecordingClient()
    client.timewarrior_command = None

    assert client.timewarrior_hours([Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="Task",
        status="pending",
    )]) == {}


@pytest.mark.parametrize("payload", ["not-json", "{}"])
def test_timewarrior_hours_rejects_invalid_export(payload: str) -> None:
    client = TimewarriorRecordingClient()
    client.timewarrior_output = payload

    with pytest.raises(TaskwarriorError, match="Timewarrior"):
        client.timewarrior_hours([])


def test_pending_parses_export() -> None:
    tasks = FakeClient().pending()
    assert len(tasks) == 1
    assert tasks[0].short_uuid == "12345678"
    assert tasks[0].description == "Example"


def test_export_rejects_invalid_json() -> None:
    client = RecordingClient()
    client._run = lambda args: "not-json"  # type: ignore[method-assign]
    with pytest.raises(TaskwarriorError, match="invalid JSON"):
        client.export()


def test_export_rejects_non_array_json() -> None:
    client = RecordingClient()
    client._run = lambda args: "{}"  # type: ignore[method-assign]
    with pytest.raises(TaskwarriorError, match="JSON array"):
        client.export()


def test_lifecycle_commands_use_uuid_prefix() -> None:
    client = RecordingClient()
    client.start("12345678")
    client.stop("12345678")
    client.done("12345678")
    client.delete("12345678")
    client.sync()
    assert client.calls == [
        ["12345678", "start"],
        ["12345678", "stop"],
        ["12345678", "done"],
        ["12345678", "delete", "rc.confirmation=off"],
        ["sync"],
    ]


def test_information_uses_uuid_prefix() -> None:
    client = RecordingClient()
    assert client.information("12345678") == "ok"
    assert client.calls == [["12345678"]]


def test_add_builds_attributes() -> None:
    client = RecordingClient()
    client.add(
        "Example",
        project="P",
        priority="M",
        due="2026-09-25",
        tags="home, next,home",
        wait="2026-09-24 08:00",
        scheduled="2026-09-24 09:00",
        depends="11111111, 22222222",
        estimate="2.5",
    )
    assert client.calls == [
        ["_udas"],
        [
        "add",
        "Example",
        "project:P",
        "priority:M",
        "due:2026-09-25",
        "wait:2026-09-24 08:00",
        "scheduled:2026-09-24 09:00",
        "depends:11111111,22222222",
        "estimate:2.5",
        "+home",
        "+next",
        ],
    ]


def test_add_omits_empty_attributes() -> None:
    client = RecordingClient()
    client.add("Example")
    assert client.calls == [["add", "Example"]]


def test_modify_replaces_editable_fields() -> None:
    client = RecordingClient()
    client.modify(
        "12345678",
        "Example task",
        project="Project",
        priority="H",
        due="2026-09-25",
        tags="mail,work",
        previous_tags=("mail", "rms"),
        wait="2026-09-24 08:00",
        scheduled="2026-09-24 09:00",
        depends="11111111,22222222",
        estimate="3.75",
    )
    assert client.calls == [
        ["_udas"],
        [
        "12345678",
        "modify",
        "description:Example task",
        "project:Project",
        "priority:H",
        "due:2026-09-25",
        "wait:2026-09-24 08:00",
        "scheduled:2026-09-24 09:00",
        "depends:11111111,22222222",
        "estimate:3.75",
        "-rms",
        "+work",
        ],
    ]


def test_modify_can_clear_optional_fields() -> None:
    client = RecordingClient()
    client.modify(
        "12345678",
        "Example",
        previous_tags=("home", "next"),
    )
    assert client.calls == [
        ["_udas"],
        [
        "12345678",
        "modify",
        "description:Example",
        "project:",
        "priority:",
        "due:",
        "wait:",
        "scheduled:",
        "depends:",
        "estimate:",
        "-home",
        "-next",
        ],
    ]


def test_client_uses_environment_override(monkeypatch) -> None:
    monkeypatch.setenv("TASKWARRIOR_COMMAND", "/custom/task")
    client = TaskwarriorClient()
    assert client.command == "/custom/task"


def test_client_uses_path_when_no_override(monkeypatch) -> None:
    monkeypatch.delenv("TASKWARRIOR_COMMAND", raising=False)
    monkeypatch.setattr("taskwarrior_textual.taskwarrior.shutil.which", lambda name: "/bin/task")
    client = TaskwarriorClient()
    assert client.command == "/bin/task"


def test_client_errors_when_task_is_missing(monkeypatch) -> None:
    monkeypatch.delenv("TASKWARRIOR_COMMAND", raising=False)
    monkeypatch.setattr("taskwarrior_textual.taskwarrior.shutil.which", lambda name: None)
    with pytest.raises(TaskwarriorError, match="not found"):
        TaskwarriorClient()


def test_run_returns_stdout(monkeypatch) -> None:
    class Result:
        returncode = 0
        stdout = "ok\n"
        stderr = ""

    monkeypatch.setattr(
        "taskwarrior_textual.taskwarrior.subprocess.run",
        lambda *args, **kwargs: Result(),
    )
    client = TaskwarriorClient(command="/bin/task")
    assert client._run(["list"]) == "ok\n"


def test_run_raises_on_nonzero_exit(monkeypatch) -> None:
    class Result:
        returncode = 2
        stdout = ""
        stderr = "boom"

    monkeypatch.setattr(
        "taskwarrior_textual.taskwarrior.subprocess.run",
        lambda *args, **kwargs: Result(),
    )
    client = TaskwarriorClient(command="/bin/task")
    with pytest.raises(TaskwarriorError, match="boom"):
        client._run(["list"])


def test_run_wraps_oserror(monkeypatch) -> None:
    def explode(*args, **kwargs):
        raise OSError("noexec")

    monkeypatch.setattr("taskwarrior_textual.taskwarrior.subprocess.run", explode)
    client = TaskwarriorClient(command="/bin/task")
    with pytest.raises(TaskwarriorError, match="Cannot execute"):
        client._run(["list"])


class DependencyExpansionClient(TaskwarriorClient):
    def __post_init__(self) -> None:
        self.command = "task"
        self.exports: list[str] = []
        self.by_filter: dict[str, list[Task]] = {}

    def export(self, *filters: str) -> list[Task]:
        assert len(filters) == 1
        dependency = filters[0]
        self.exports.append(dependency)
        return self.by_filter.get(dependency, [])


def test_expand_dependencies_rejects_depth_below_unlimited_sentinel() -> None:
    client = DependencyExpansionClient()

    with pytest.raises(ValueError, match="dependency depth"):
        client.expand_dependencies([], -2)


def test_expand_dependencies_respects_depth_and_fetches_only_missing_tasks() -> None:
    root = Task(
        uuid="11111111-1111-1111-1111-111111111111",
        description="Root",
        status="pending",
        depends=("22222222-2222-2222-2222-222222222222",),
    )
    direct = Task(
        uuid="22222222-2222-2222-2222-222222222222",
        description="Direct",
        status="completed",
        depends=("33333333-3333-3333-3333-333333333333",),
    )
    indirect = Task(
        uuid="33333333-3333-3333-3333-333333333333",
        description="Indirect",
        status="completed",
    )
    client = DependencyExpansionClient()
    client.by_filter = {
        direct.uuid: [direct],
        indirect.uuid: [indirect],
    }

    assert client.expand_dependencies([root], 0) == [root]
    assert client.exports == []

    depth_one = client.expand_dependencies([root], 1)
    assert [task.uuid for task in depth_one] == [root.uuid, direct.uuid]
    assert client.exports == [direct.uuid]

    client.exports.clear()
    depth_two = client.expand_dependencies([root], 2)
    assert [task.uuid for task in depth_two] == [root.uuid, direct.uuid, indirect.uuid]
    assert client.exports == [direct.uuid, indirect.uuid]


def test_expand_dependencies_unlimited_stops_on_cycles_duplicates_and_missing_tasks() -> None:
    root = Task(
        uuid="aaaaaaaa-1111-1111-1111-111111111111",
        description="Root",
        status="pending",
        depends=(
            "bbbbbbbb-1111-1111-1111-111111111111",
            "cccccccc-1111-1111-1111-111111111111",
        ),
    )
    dependency = Task(
        uuid="bbbbbbbb-1111-1111-1111-111111111111",
        description="Dependency",
        status="completed",
        depends=(root.uuid, "dddddddd-1111-1111-1111-111111111111"),
    )
    client = DependencyExpansionClient()
    client.by_filter = {dependency.uuid: [dependency]}

    expanded = client.expand_dependencies([root], -1)

    assert [task.uuid for task in expanded] == [root.uuid, dependency.uuid]
    assert client.exports == [
        dependency.uuid,
        "cccccccc-1111-1111-1111-111111111111",
        "dddddddd-1111-1111-1111-111111111111",
    ]


class ViewRecordingClient(TaskwarriorClient):
    def __post_init__(self) -> None:
        self.command = "task"
        self.filters = []

    def export(self, *filters: str):
        self.filters.append(filters)
        return []


@pytest.mark.parametrize(
    ("view_name", "expected_filter"),
    [
        ("pending", "status:pending"),
        ("waiting", "status:waiting"),
        ("completed", "status:completed"),
        ("deleted", "status:deleted"),
        ("scheduled", "+SCHEDULED"),
    ],
)
def test_named_views_map_to_explicit_taskwarrior_filters(
    view_name: str, expected_filter: str
) -> None:
    client = ViewRecordingClient()

    assert client.view(view_name) == []
    assert client.filters == [(expected_filter,)]


def test_unknown_view_is_rejected() -> None:
    client = ViewRecordingClient()

    with pytest.raises(ValueError, match="Unknown task view"):
        client.view("nonsense")


def test_tag_parser_trims_deduplicates_and_preserves_order() -> None:
    assert TaskwarriorClient._parse_list(" home, next,home ,, work ") == (
        "home",
        "next",
        "work",
    )


def test_tag_delta_does_not_touch_unchanged_tags() -> None:
    assert TaskwarriorClient._tag_modifications(
        "mail,rms", ("mail", "rms")
    ) == []



class UdaRecordingClient(RecordingClient):
    def __init__(self, udas: str) -> None:
        super().__init__()
        self.udas_output = udas

    def _run(self, args):  # type: ignore[override]
        self.calls.append(list(args))
        if list(args) == ["_udas"]:
            return self.udas_output
        return "ok"


def test_udas_parses_helper_output() -> None:
    client = UdaRecordingClient("estimate\nfoo.bar\n")

    assert client.udas() == frozenset({"estimate", "foo.bar"})
    assert client.calls == [["_udas"]]


def test_add_estimate_requires_configured_uda() -> None:
    client = UdaRecordingClient("other\n")

    with pytest.raises(TaskwarriorError, match="estimate UDA"):
        client.add("Example", estimate="2.5")

    assert client.calls == [["_udas"]]


def test_add_estimate_uses_configured_uda() -> None:
    client = UdaRecordingClient("estimate\n")

    client.add("Example", estimate="0")

    assert client.calls == [
        ["_udas"],
        ["add", "Example", "estimate:0"],
    ]


def test_modify_without_estimate_uda_does_not_touch_estimate() -> None:
    client = UdaRecordingClient("other\n")

    client.modify("12345678", "Example")

    assert client.calls == [
        ["_udas"],
        [
            "12345678",
            "modify",
            "description:Example",
            "project:",
            "priority:",
            "due:",
            "wait:",
            "scheduled:",
            "depends:",
        ],
    ]


def test_modify_with_estimate_uda_can_clear_estimate() -> None:
    client = UdaRecordingClient("estimate\n")

    client.modify("12345678", "Example", estimate="")

    assert client.calls == [
        ["_udas"],
        [
            "12345678",
            "modify",
            "description:Example",
            "project:",
            "priority:",
            "due:",
            "wait:",
            "scheduled:",
            "depends:",
            "estimate:",
        ],
    ]


def test_modify_nonempty_estimate_requires_configured_uda() -> None:
    client = UdaRecordingClient("")

    with pytest.raises(TaskwarriorError, match="estimate UDA"):
        client.modify("12345678", "Example", estimate="1.5")

    assert client.calls == [["_udas"]]


def test_udas_result_is_cached() -> None:
    client = UdaRecordingClient("estimate\n")

    assert client.has_uda("estimate") is True
    assert client.has_uda("estimate") is True
    assert client.calls == [["_udas"]]



@pytest.mark.parametrize("estimate", ["nope", "-1", "-0.5", "nan", "inf", "-inf"])
def test_add_rejects_invalid_estimate_values(estimate: str) -> None:
    client = UdaRecordingClient("estimate\n")

    with pytest.raises(TaskwarriorError, match="estimate"):
        client.add("Example", estimate=estimate)

    assert client.calls == [["_udas"]]


@pytest.mark.parametrize("estimate", ["nope", "-1", "-0.5", "nan", "inf", "-inf"])
def test_modify_rejects_invalid_estimate_values(estimate: str) -> None:
    client = UdaRecordingClient("estimate\n")

    with pytest.raises(TaskwarriorError, match="estimate"):
        client.modify("12345678", "Example", estimate=estimate)

    assert client.calls == [["_udas"]]


@pytest.mark.parametrize("estimate", ["0", "0.0", "1", "2.5"])
def test_valid_nonnegative_estimates_are_forwarded(estimate: str) -> None:
    client = UdaRecordingClient("estimate\n")

    client.add("Example", estimate=estimate)

    assert client.calls == [
        ["_udas"],
        ["add", "Example", f"estimate:{estimate}"],
    ]
