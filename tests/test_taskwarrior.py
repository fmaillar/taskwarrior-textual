import json

from taskwarrior_textual.taskwarrior import TaskwarriorClient


class FakeClient(TaskwarriorClient):
    def __post_init__(self) -> None:
        self.command = "task"

    def _run(self, args):  # type: ignore[override]
        assert args == ["status:pending", "export"]
        return json.dumps(
            [{"uuid": "12345678-1234-1234-1234-123456789abc", "description": "Example", "status": "pending"}]
        )


def test_pending_parses_export() -> None:
    tasks = FakeClient().pending()
    assert len(tasks) == 1
    assert tasks[0].short_uuid == "12345678"
    assert tasks[0].description == "Example"
