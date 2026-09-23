import json

from taskwarrior_textual.taskwarrior import TaskwarriorClient


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
        return "ok"


def test_pending_parses_export() -> None:
    tasks = FakeClient().pending()

    assert len(tasks) == 1
    assert tasks[0].short_uuid == "12345678"
    assert tasks[0].description == "Example"


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


def test_modify_replaces_editable_fields() -> None:
    client = RecordingClient()

    client.modify(
        "12345678",
        "Example task",
        project="Project",
        priority="H",
        due="2026-09-25",
    )

    assert client.calls == [
        [
            "12345678",
            "modify",
            "description:Example task",
            "project:Project",
            "priority:H",
            "due:2026-09-25",
        ]
    ]
