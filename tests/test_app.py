from __future__ import annotations

from textual.widgets import Button, Input

from taskwarrior_textual import app as app_module
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
    tags=("mail", "rms"),
    start="20260923T070000Z",
)


class FakeUiClient:
    def __init__(self, tasks: list[Task] | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.fail: str | None = None
        self.tasks = [TASK] if tasks is None else tasks

    def _maybe_fail(self, action: str) -> None:
        if self.fail == action:
            raise TaskwarriorError(f"{action} failed")

    def view(self, name: str) -> list[Task]:
        self._maybe_fail("view")
        self.calls.append(("view", name))
        return self.tasks

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
        assert app.current_view == "pending"
        assert ("view", "pending") in app.client.calls


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
        form.on_button_pressed(Button.Pressed(form.query_one("#save", Button)))
        await pilot.pause()
    assert ("modify", TASK.short_uuid) in client.calls


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
            ("1", "pending"),
        ]:
            await pilot.press(key)
            await pilot.pause()
            assert app.current_view == expected
            assert ("view", expected) in client.calls


def test_run_launches_application(monkeypatch) -> None:
    launched = []
    monkeypatch.setattr(app_module, "TaskwarriorClient", lambda: FakeUiClient())
    monkeypatch.setattr(TaskwarriorApp, "run", lambda self: launched.append(True))
    app_module.run()
    assert launched == [True]
