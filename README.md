# taskwarrior-textual

A Textual TUI for Taskwarrior 3, intended to grow from a fast task browser/editor into a project-planning cockpit with reports, Gantt views and critical-path analysis.

## Design

Taskwarrior remains the source of truth. This project talks to Taskwarrior through its CLI and does **not** read or modify `taskchampion.sqlite3` directly.

```text
Textual UI
    |
application / planning
    |
Taskwarrior CLI adapter
    |
task
    |
TaskChampion
```

## Current MVP

- discover the `task` executable from `PATH`
- override it with `TASKWARRIOR_COMMAND`
- read pending tasks using `task status:pending export`
- display tasks in a Textual `DataTable`
- refresh with `r`
- inspect the selected task with `Enter`

## Installation for development

```sh
git clone https://github.com/fmaillar/taskwarrior-textual.git
cd taskwarrior-textual
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
taskwarrior-textual
```

If the desired Taskwarrior binary is not the first `task` in `PATH`:

```sh
TASKWARRIOR_COMMAND=/usr/local/bin/task taskwarrior-textual
```

## Roadmap

Next: task editing and lifecycle actions, project/dependency views, Timewarrior integration, reports, Gantt, duration/effort metadata, and critical-path analysis.

## License

GPL-3.0-or-later.
