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
        }
    )

    assert task.short_uuid == "34852993"
    assert task.description == "Réparer Transmission"
    assert task.project == "Torrent"
    assert task.display_due == "2026-09-25"
    assert task.urgency == 18.71


def test_format_taskwarrior_datetime_empty_value() -> None:
    assert format_taskwarrior_datetime("") == ""


def test_format_taskwarrior_datetime_preserves_unknown_values() -> None:
    assert format_taskwarrior_datetime("tomorrow") == "tomorrow"


def test_format_taskwarrior_datetime_keeps_time_when_present() -> None:
    assert format_taskwarrior_datetime("20260925T143000Z") == "2026-09-25 14:30"
