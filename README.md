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
- edit planning metadata separately from ordinary task fields
- resolve dependency UUID prefixes against the expanded planning graph
- reject self-dependencies, ambiguous/unknown prefixes, and dependency cycles before modification
- analyze dependency graphs, critical path, calendar plans, constraints, milestones and project totals
- use Timewarrior tracked effort for remaining-work calculations and historical trend reports

### Key bindings

```text
Enter   inspect
r       refresh
a       add
e       edit ordinary task fields
E       edit planning fields (due/wait/scheduled/dependencies/estimate)
s       start
x       stop
d       done
D       delete
y       sync
g       selected-task dependencies
G       dependency graph
C       critical path
H       Gantt
L       calendar plan
K       scheduling constraints
M       milestones
P       project overview
O       selected-project planning dashboard
T       Timewarrior effort report
R       Timewarrior trend (7/30 days, week, month)
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

- `ruff.txt`: Ruff output
- `ruff-exit-status.txt`: Ruff exit status
- `pytest.txt`: human-readable pytest and coverage output
- `junit.xml`: machine-readable test results
- `coverage.xml`: Cobertura coverage report
- `coverage.json`: detailed coverage data
- `pytest-exit-status.txt`: pytest exit status

The reported quality gate now runs Ruff before pytest, so the normal report workflow
checks both lint and branch-aware test coverage.

To generate, commit and push those reports in one command:

```sh
make push-reports
```

The local HTML report remains available via `make coverage` in `htmlcov/`, but is intentionally not committed.

## Planning editor

Press `E` on a selected task to edit only its planning metadata. This path deliberately
uses a separate Taskwarrior CLI modification command, so description, project, priority
and tags are left untouched.

Dependency input accepts comma-separated UUIDs or unique UUID prefixes. The editor shows
the dependency candidates available from the expanded planning graph, resolves prefixes
to full UUIDs, and rejects self-dependencies, unknown or ambiguous prefixes, and edits
that would introduce a dependency cycle.

## Project dashboard

Press `O` on a selected task to open a consolidated dashboard for that task's
project (or the unprojected scope). The dashboard keeps the current Taskwarrior
view as its project scope, recursively expands external dependencies according to
`dependency_depth`, and reads Timewarrior once for the expanded graph.

It reports project-only task/effort totals, external dependency count, graph
health, unresolved edges, remaining critical-path duration, the critical path,
calendar finish and late-task count when a valid calendar anchor exists, plus a
per-task table that distinguishes project tasks from external prerequisites.

## Persistent planning configuration

Planning defaults can be overridden in:

```text
~/.config/taskwarrior-textual/config.toml
```

or, when set, under `$XDG_CONFIG_HOME/taskwarrior-textual/config.toml`.
`TASKWARRIOR_TEXTUAL_CONFIG` can point at an explicit file.

Example:

```toml
[planning]
timezone = "Europe/Paris"
workdays = [0, 1, 2, 3, 4]
work_periods = [["08:00", "12:00"], ["13:00", "17:00"]]
holidays = ["2026-12-25"]
dependency_depth = 10
capacity = 2
```

Omitted keys keep the built-in defaults. Invalid values and unknown `[planning]`
keys are rejected at startup instead of being silently ignored.

## Roadmap

Next: richer planning navigation/editing, packaging, release hardening, and a stable
tagged release.

## License

GPL-3.0-or-later.
