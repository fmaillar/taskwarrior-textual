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
- human-readable due dates
- inspect a task with `Enter`
- add and edit tasks with Textual forms
- start/stop tasks (and therefore Timewarrior when the hook is installed)
- mark tasks done
- delete tasks with confirmation
- synchronize with `task sync`

### Key bindings

```text
Enter   inspect
r       refresh
a       add
e       edit
s       start
x       stop
d       done
D       delete
y       sync
q       quit
```

## Installation for development

```sh
git clone https://github.com/fmaillar/taskwarrior-textual.git
cd taskwarrior-textual
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
pytest
taskwarrior-textual
```

If the desired Taskwarrior binary is not the first `task` in `PATH`:

```sh
TASKWARRIOR_COMMAND=/usr/local/bin/task taskwarrior-textual
```

## Roadmap

Next: richer Taskwarrior fields and filters, dependency/project views, Timewarrior reports, Gantt, duration/effort metadata, and critical-path analysis.

## License

GPL-3.0-or-later.
