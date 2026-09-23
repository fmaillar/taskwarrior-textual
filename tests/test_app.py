from __future__ import annotations

from taskwarrior_textual.app import ConfirmDelete, TaskForm, TaskwarriorApp
from taskwarrior_textual.models import Task


TASK = Task(
    uuid="1b17dac7-81c8-4aa0-955b-658b1663cce3",
    description="Vérifier mail de RMS",
    status="pending",
    priority="L",
    due="20260926T000000Z",
    urgency=9.38,
)


class FakeUiClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def pending(self) -> list[Task]:
        return [TASK]

    def information(self, uuid_prefix: str) -> str:
        self.calls.append(("information", uuid_prefix))
        return "task information"

    def add(self, **values: str) -> str:
        self.calls.append(("add", values["description"]))
        return "created"

    def modify(self, uuid_prefix: str, **values: str) -> str:
        self.calls.append(("modify", uuid_prefix))
        return "modified"

    def start(self, uuid_prefix: str) -> str:
        self.calls.append(("start", uuid_prefix))
        return "started"

    def stop(self, uuid_prefix: str) -> str:
        self.calls.append(("stop", uuid_prefix))
        return "stopped"

    def done(self, uuid_prefix: str) -> str:
        self.calls.append(("done", uuid_prefix))
        return "done"

    def delete(self, uuid_prefix: str) -> str:
        self.calls.append(("delete", uuid_prefix))
        return "deleted"

    def sync(self) -> str:
        self.calls.append(("sync", ""))
        return "synced"


def test_task_form_can_hold_an_existing_task() -> None:
    form = TaskForm(TASK)

    assert form.initial_task is TASK


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


async def test_delete_key_opens_confirmation_screen() -> None:
    app = TaskwarriorApp(client=FakeUiClient())

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("D")
        await pilot.pause()

        assert isinstance(app.screen, ConfirmDelete)
        assert app.screen.target_task == TASK


async def test_lifecycle_keys_call_client_with_short_uuid() -> None:
    client = FakeUiClient()
    app = TaskwarriorApp(client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("s")
        await pilot.press("x")
        await pilot.press("d")
        await pilot.press("enter")
        await pilot.press("y")
        await pilot.pause()

    assert ("start", TASK.short_uuid) in client.calls
    assert ("stop", TASK.short_uuid) in client.calls
    assert ("done", TASK.short_uuid) in client.calls
    assert ("information", TASK.short_uuid) in client.calls
    assert ("sync", "") in client.calls
