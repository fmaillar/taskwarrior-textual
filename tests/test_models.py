from taskwarrior_textual.models import Task, format_taskwarrior_datetime


def test_task_from_export() -> None:
    task = Task.from_export(
        {
            "uuid": "34852993-caa1-4dd0-88ed-5089ef216a43",
            "description": "Réparer Transmission",
            "status": "pending",
            "project": "Torrent",
            "priority": "M",
            "due": "20260925T000000Z",
            "urgency": 18.71,
            "tags": ["network", "server"],
            "depends": [
                "11111111-1111-1111-1111-111111111111",
                "22222222-2222-2222-2222-222222222222",
            ],
            "wait": "20260924T080000Z",
            "scheduled": "20260924T090000Z",
            "start": "20260923T070000Z",
            "entry": "20260922T120000Z",
            "estimate": 2.5,
        }
    )

    assert task.short_uuid == "34852993"
    assert task.description == "Réparer Transmission"
    assert task.project == "Torrent"
    assert task.display_due == "2026-09-25"
    assert task.urgency == 18.71
    assert task.tags == ("network", "server")
    assert task.depends == (
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    )
    assert task.display_wait == "2026-09-24 08:00"
    assert task.display_scheduled == "2026-09-24 09:00"
    assert task.display_entry == "2026-09-22 12:00"
    assert task.display_end == ""
    assert task.estimate_hours == 2.5
    assert task.display_estimate == "2.50h"
    assert task.active is True


def test_task_defaults_for_optional_metadata() -> None:
    task = Task.from_export(
        {
            "uuid": "12345678-1234-1234-1234-123456789abc",
            "description": "Minimal",
            "status": "pending",
        }
    )

    assert task.tags == ()
    assert task.depends == ()
    assert task.wait == ""
    assert task.scheduled == ""
    assert task.start == ""
    assert task.end == ""
    assert task.entry == ""
    assert task.estimate_hours == 0.0
    assert task.display_estimate == ""
    assert task.active is False
    assert task.display_wait == ""
    assert task.display_scheduled == ""
    assert task.display_entry == ""
    assert task.display_end == ""


def test_completed_task_is_not_active_even_with_start() -> None:
    task = Task(
        uuid="12345678-1234-1234-1234-123456789abc",
        description="Completed",
        status="completed",
        start="20260923T070000Z",
        end="20260923T080000Z",
    )

    assert task.active is False
    assert task.display_end == "2026-09-23 08:00"


def test_format_taskwarrior_datetime_empty_value() -> None:
    assert format_taskwarrior_datetime("") == ""


def test_format_taskwarrior_datetime_preserves_unknown_values() -> None:
    assert format_taskwarrior_datetime("tomorrow") == "tomorrow"


def test_format_taskwarrior_datetime_keeps_time_when_present() -> None:
    assert format_taskwarrior_datetime("20260925T143000Z") == "2026-09-25 14:30"


def test_estimate_is_coerced_from_export_string() -> None:
    task = Task.from_export(
        {
            "uuid": "87654321-1234-1234-1234-123456789abc",
            "description": "Estimated",
            "status": "pending",
            "estimate": "1.25",
        }
    )

    assert task.estimate_hours == 1.25
    assert task.display_estimate == "1.25h"
