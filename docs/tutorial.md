# Tutorial

This tutorial takes a new user from an existing Taskwarrior installation to a
first project-planning workflow in `taskwarrior-textual`.

## 1. Mental model

`taskwarrior-textual` is a terminal user interface around Taskwarrior. It is
not another task database.

```text
taskwarrior-textual
        |
        v
Taskwarrior CLI
        |
        v
TaskChampion / Taskwarrior data
```

Taskwarrior remains the source of truth. Changes made in the TUI are ordinary
Taskwarrior operations and remain visible from the `task` command line.

Timewarrior is optional. When available, tracked intervals are used to calculate
tracked and remaining effort and to produce trend reports.

## 2. Prerequisites

You need:

- Python 3.11 or newer;
- Taskwarrior 3 available as `task`;
- a working Taskwarrior configuration;
- optionally Timewarrior, available as `timew`;
- optionally the usual Taskwarrior → Timewarrior hook if you want `start` and
  `stop` to track time automatically.

Verify Taskwarrior first:

```sh
task --version
task status:pending count
```

If Taskwarrior itself cannot read the task database, fix that before starting
the TUI.

## 3. Install from the repository

Clone the project and create its virtual environment:

```sh
git clone https://github.com/fmaillar/taskwarrior-textual.git
cd taskwarrior-textual
make install
```

Run the application with:

```sh
.venv/bin/taskwarrior-textual
```

To use another Taskwarrior executable:

```sh
TASKWARRIOR_COMMAND=/usr/local/bin/task .venv/bin/taskwarrior-textual
```

The Timewarrior executable can similarly be overridden with
`TIMEWARRIOR_COMMAND`.

## 4. Check configuration before starting

Useful non-interactive commands are:

```sh
.venv/bin/taskwarrior-textual --version
.venv/bin/taskwarrior-textual --config-path
.venv/bin/taskwarrior-textual --check-config
```

The last command validates the resolved planning configuration without launching
Textual.

## 5. First launch

The main screen contains:

- a task table on the left;
- a detail/status pane on the right;
- a Textual footer showing bindings.

Press `?` for the complete in-application help. Press `?` again or `Esc`
to close it.

The five top-level Taskwarrior views are:

```text
1  pending
2  waiting
3  completed
4  deleted
5  scheduled
```

Changing view causes a Taskwarrior query. Search, filtering, and sorting within
an already loaded view are local operations.

## 6. Navigate and inspect

Move the cursor through the task table with the normal Textual navigation keys.

Press:

```text
Enter   inspect selected task
r       refresh current Taskwarrior view
```

Inspection displays Taskwarrior's human-readable information for the selected
task in the details pane.

## 7. Add and edit tasks

Press `a` to add a task. The form supports:

- description;
- project;
- priority;
- due date;
- tags;
- wait date;
- scheduled date;
- dependencies;
- effort estimate.

Press `e` to edit ordinary task fields.

Press `E` for the dedicated planning editor. Keeping planning edits separate
is deliberate: it reduces the chance of accidentally changing unrelated task
metadata while working on dependencies and schedules.

### Estimates

Planning uses an `estimate` Taskwarrior UDA expressed in hours.

For example, a two-hour task has:

```text
estimate:2
```

An estimate of `0` represents a milestone.

If the UDA is absent, the application refuses operations that require writing an
estimate rather than silently inventing incompatible Taskwarrior data.

## 8. Search, filter, and sort

The following operations work on the currently loaded view:

```text
/   search description, project, or tags
p   exact project filter
f   exact tag filter
b   only tasks with dependencies
v   only active tasks
t   cycle sort order
c   clear all local filters and sorting
```

These operations do not re-query Taskwarrior. This makes them suitable for
interactive triage.

## 9. Work on a task

The basic execution workflow is:

```text
s   start
x   stop
d   mark done
D   delete, with confirmation
y   task sync
```

If the standard Timewarrior hook is installed, Taskwarrior start/stop operations
can also create Timewarrior tracking intervals.

## 10. Create a small project

Suppose a project called `release` contains three tasks:

```text
Write documentation      estimate:2
Build package             estimate:1
Publish release           estimate:0.5
```

Set dependencies so that:

```text
Write documentation
        |
        v
Build package
        |
        v
Publish release
```

Use `E` on each dependent task and enter the dependency UUID or a unique UUID
prefix. The application resolves prefixes against the expanded planning graph
and rejects:

- unknown prefixes;
- ambiguous prefixes;
- self-dependencies;
- dependency changes that introduce a cycle.

## 11. Inspect the dependency graph

Use:

```text
g   dependencies of selected task
G   dependency graph overview
C   critical path
H   Gantt-like planning view
M   milestones
```

External prerequisite tasks can be recursively included according to
`dependency_depth`.

## 12. Configure the working calendar

The default configuration path is:

```text
~/.config/taskwarrior-textual/config.toml
```

or the corresponding path below `$XDG_CONFIG_HOME`. You can also point to a
specific file with `TASKWARRIOR_TEXTUAL_CONFIG`.

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

Meaning:

- `timezone`: timezone used by calendar planning;
- `workdays`: Python weekday numbers, Monday = 0;
- `work_periods`: working intervals in local time;
- `holidays`: excluded ISO dates;
- `dependency_depth`: recursive external dependency expansion; `0` disables
  expansion and `-1` means unlimited;
- `capacity`: maximum number of simultaneously scheduled tasks; omit it for
  unlimited parallel capacity.

Validate the file with:

```sh
.venv/bin/taskwarrior-textual --check-config
```

## 13. Build an absolute plan

Once estimates and dependencies exist:

```text
L   calendar plan
K   scheduling constraints
I   planning health
S   auto-schedule selected project
```

The auto-scheduler:

- starts from the current working instant;
- respects dependency order;
- respects existing later `scheduled` constraints;
- uses the configured calendar and capacity;
- subtracts Timewarrior effort when available;
- includes external dependencies in calculations;
- modifies only eligible tasks belonging to the selected project;
- shows a preview before any Taskwarrior modification is made.

Review the proposal before applying it.

## 14. Use the project cockpit

Select any task in the project and press `O`.

The project dashboard combines:

- project task and effort totals;
- external prerequisites;
- dependency-graph health;
- unresolved edges;
- critical-path duration and path;
- projected calendar finish;
- late-task count;
- actionable task rows.

From the dashboard you can inspect, edit, edit planning metadata, inspect
dependencies, start, stop, complete, or auto-schedule work.

For a compact project summary instead, press `P`.

## 15. Use Timewarrior reports

When Timewarrior data is available:

```text
T   effort report
R   trend report
```

The effort report compares estimates, tracked time, and remaining work.

The trend screen exposes 7-day, 30-day, weekly, and monthly views.

## 16. A recommended first workflow

For a new project:

1. create or import tasks in Taskwarrior;
2. assign a common project;
3. add estimates;
4. add dependencies with `E`;
5. inspect `G` and `C`;
6. check `I` for planning problems;
7. inspect `L` for the projected calendar;
8. preview `S`;
9. apply the proposal only if it matches your intent;
10. execute work with `s`, `x`, and `d`;
11. use `T` and `R` to compare planning with actual effort.

At any point, press `?` for the key reference.
