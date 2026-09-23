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

## Development

```sh
git clone https://github.com/fmaillar/taskwarrior-textual.git
cd taskwarrior-textual
make install
make check
```

If the desired Taskwarrior binary is not the first `task` in `PATH`:

```sh
TASKWARRIOR_COMMAND=/usr/local/bin/task taskwarrior-textual
```

### Tests and coverage reports

The project requires at least 95% branch-aware coverage. Generate reviewable reports with:

```sh
make report
```

This writes compact, Git-friendly artifacts to `reports/`:

- `pytest.txt`: human-readable pytest and coverage output
- `junit.xml`: machine-readable test results
- `coverage.xml`: Cobertura coverage report
- `coverage.json`: detailed coverage data
- `pytest-exit-status.txt`: pytest exit status

To generate, commit and push those reports in one command:

```sh
make push-reports
```

The local HTML report remains available via `make coverage` in `htmlcov/`, but is intentionally not committed.

## Roadmap

Next: richer Taskwarrior fields and filters, dependency/project views, Timewarrior reports, Gantt, duration/effort metadata, and critical-path analysis.

## License

GPL-3.0-or-later.
