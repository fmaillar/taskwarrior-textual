from __future__ import annotations

from textual.widgets import Button, Input

from taskwarrior_textual import app as app_module
from taskwarrior_textual.app import (
    ConfirmDelete,
    ProjectFilterForm,
    SearchForm,
    TaskForm,
    TaskwarriorApp,
)
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
    depends=("11111111-1111-1111-1111-111111111111",),
    wait="20260924T080000Z",
    scheduled="20260924T090000Z",
    start="20260923T070000Z",
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
        self.calls: list[tuple[str, str]] = []
        self.fail: str | None = None
        self.tasks = [TASK] if tasks is None else tasks
        self.modify_values: list[dict[str, object]] = []

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

    def modify(self, uuid_prefix: str, **values: object) -> str:
        self._maybe_fail("modify")
        self.calls.append(("modify", uuid_prefix))
        self.modify_values.append(values)
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


def test_task_row_shows_active_marker_tags_and_due_in_pending_view() -> None:
    row = TaskwarriorApp._task_row(TASK, "pending")

    assert row == (
        TASK.short_uuid,
        "▶",
        "◆",
        "L",
        "",
        "2026-09-26",
        "mail,rms",
        "Vérifier mail de RMS",
        "9.38",
    )


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


def test_task_row_has_no_active_marker_for_inactive_task() -> None:
    task = Task(
        uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        description="Inactive",
        status="pending",
    )

    row = TaskwarriorApp._task_row(task, "pending")
    assert row[1] == ""
    assert row[2] == ""


async def test_table_uses_enriched_row_shape() -> None:
    app = TaskwarriorApp(client=FakeUiClient())
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#tasks")
        assert list(table.get_row_at(0)) == list(TaskwarriorApp._task_row(TASK, "pending"))


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
        form.query_one("#tags", Input).value = "mail,work"
        form.query_one("#wait", Input).value = ""
        form.query_one("#scheduled", Input).value = "tomorrow 09:00"
        form.query_one("#depends", Input).value = "22222222"
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


def test_run_launches_application(monkeypatch) -> None:
    launched = []
    monkeypatch.setattr(app_module, "TaskwarriorClient", lambda: FakeUiClient())
    monkeypatch.setattr(TaskwarriorApp, "run", lambda self: launched.append(True))
    app_module.run()
    assert launched == [True]
