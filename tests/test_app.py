from __future__ import annotations

from textual.widgets import Button, Input

from taskwarrior_textual.app import ConfirmDelete, TaskForm, TaskwarriorApp
from taskwarrior_textual.models import Task
from taskwarrior_textual.taskwarrior import TaskwarriorError


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
        self.fail: str | None = None

    def _maybe_fail(self, action: str) -> None:
        if self.fail == action:
            raise TaskwarriorError(f"{action} failed")

    def pending(self) -> list[Task]:
        self._maybe_fail("pending")
        return [TASK]

    def information(self, uuid_prefix: str) -> str:
        self._maybe_fail("information")
        self.calls.append(("information", uuid_prefix))
        return "task information"

    def add(self, **values: str) -> str:
        self._maybe_fail("add")
        self.calls.append(("add", values["description"]))
        return "created"

    def modify(self, uuid_prefix: str, **values: str) -> str:
        self._maybe_fail("modify")
        self.calls.append(("modify", uuid_prefix))
        return "modified"

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
        form.on_button_pressed(Button.Pressed(form.query_one("#save", Button)))
        await pilot.pause()
    assert ("add", "New task") in client.calls


async def test_add_form_cancel_does_not_call_client() -> None:
    client = FakeUiClient()
    app = TaskwarriorApp(client=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        form = app.screen
        form.on_button_pressed(Button.Pressed(form.query_one("#cancel", Button)))
        await pilot.pause()
    assert not client.calls


async def test_edit_form_save_calls_modify() -> None:
    client = FakeUiClient()
    app = TaskwarriorApp(client=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        form = app.screen
        form.query_one("#description", Input).value = "Changed"
        form.on_button_pressed(Button.Pressed(form.query_one("#save", Button)))
        await pilot.pause()
    assert ("modify", TASK.short_uuid) in client.calls


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


async def test_delete_key_opens_confirmation_screen() -> None:
    app = TaskwarriorApp(client=FakeUiClient())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("D")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDelete)
        assert app.screen.target_task == TASK


async def test_delete_confirmation_calls_client() -> None:
    client = FakeUiClient()
    app = TaskwarriorApp(client=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("D")
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
        await pilot.press("D")
        await pilot.pause()
        screen = app.screen
        screen.on_button_pressed(Button.Pressed(screen.query_one("#cancel", Button)))
        await pilot.pause()
    assert ("delete", TASK.short_uuid) not in client.calls


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


async def test_backend_error_is_rendered_in_details() -> None:
    client = FakeUiClient()
    client.fail = "start"
    app = TaskwarriorApp(client=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()
        details = app.query_one("#details")
        assert "start failed" in str(details.render())


async def test_pending_error_does_not_crash_app() -> None:
    client = FakeUiClient()
    client.fail = "pending"
    app = TaskwarriorApp(client=client)
    async with app.run_test() as pilot:
        await pilot.pause()
        details = app.query_one("#details")
        assert "pending failed" in str(details.render())
