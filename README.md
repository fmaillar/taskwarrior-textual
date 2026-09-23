# taskwarrior-textual

A Textual TUI for Taskwarrior 3 with task management, project planning, dependency analysis, calendar scheduling, Timewarrior effort tracking, and an interactive project cockpit.

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

## Documentation

The README is the short project overview. Full documentation lives in
[`docs/`](docs/README.md):

- [Tutorial](docs/tutorial.md) — installation, configuration, interface basics,
  and a complete first planning workflow.
- [Use cases](docs/use-cases.md) — practical workflows for daily triage, project
  planning, dependencies, auto-scheduling, Timewarrior, and diagnostics.
- [Maintainer guide](docs/maintainer-guide.md) — architecture, invariants,
  extension patterns, tests, quality gates, and release/maintenance procedures.

The in-application key reference is always available with `?`.

Project files:

- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [License](LICENSE)

## Features

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
?       help
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
I       planning health report
S       auto-schedule selected project (preview/apply)
L       calendar plan
K       scheduling constraints
M       milestones
P       project overview
O       selected-project planning dashboard
T       Timewarrior effort report
R       Timewarrior trend (7/30 days, week, month)
q       quit
```

## In-application help

Press `?` at any time in the main task view to open the scrollable help screen.
It summarizes task actions, local views and filters, planning reports, project
cockpit commands, Timewarrior commands, and general navigation. Press `?`
again or `Esc` to close it.

## Command-line checks

The executable can perform release/configuration checks without starting Textual:

```sh
taskwarrior-textual --version
taskwarrior-textual --config-path
taskwarrior-textual --check-config
```

`--check-config` validates the resolved TOML file and exits nonzero with a concise
configuration error when it is invalid.

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

The project requires 100% branch-aware coverage. Generate reviewable reports with:

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

The reported quality gate runs Ruff, mypy, pytest with branch-aware coverage, and a wheel/sdist build. `make check` is therefore the single local/CI gate for lint, static typing, tests, coverage, and packaging.

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

## Auto-scheduling and planning health

Press `S` on a selected task to build an auto-schedule proposal for that task's
project. The proposal starts from the current working instant, honors dependency
order, existing later `scheduled` constraints, configured working periods and
capacity, and uses Timewarrior remaining effort. Only unscheduled, inactive
project tasks are proposed for modification; external dependencies participate
in the calculation but are never modified. Nothing is written until the proposal
is explicitly applied.

Press `I` for a planning-health report over the expanded current view. It checks
dependency cycles and cycle-blocked tasks, unresolved dependencies, missing
estimates, invalid `scheduled`/`due` values, projected deadline lateness and
Timewarrior effort overruns.

## Project cockpit

Press `O` on a selected task to open the interactive cockpit for that task's
project (or the unprojected scope). The cockpit keeps the current Taskwarrior
view as its project scope, recursively expands external dependencies according to
`dependency_depth`, and reads Timewarrior once for the expanded graph.

It reports project-only task/effort totals, external dependency count, graph
health, unresolved edges, remaining critical-path duration, the critical path,
calendar finish and late-task count when a valid calendar anchor exists.

The task table is directly actionable, including for external prerequisites:
`Enter` inspects, `e` edits ordinary fields, `E` edits planning metadata,
`g` opens dependencies, `s`/`x` start or stop work, `d` completes the
task, and `S` opens the project's auto-schedule proposal. This makes the
dashboard the main project-navigation surface rather than a read-only report.

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

## Status

Version `0.1.0` is the first release line. Development happens in a private
development repository; the public repository is a clean publication mirror of
validated `main` and release tags.

## License

GPL-3.0-or-later.
