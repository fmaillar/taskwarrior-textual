from taskwarrior_textual.models import Task


def test_task_from_export() -> None:
    task = Task.from_export(
        {
            "uuid": "34852993-caa1-4dd0-88ed-5089ef216a43",
            "description": "Réparer Transmission",
            "status": "pending",
            "project": "Torrent",
            "priority": "M",
            "urgency": 18.71,
        }
    )
    assert task.short_uuid == "34852993"
    assert task.description == "Réparer Transmission"
    assert task.project == "Torrent"
    assert task.urgency == 18.71
