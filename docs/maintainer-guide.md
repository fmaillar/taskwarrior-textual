# Maintainer guide

This guide is for future maintainers of `taskwarrior-textual`.

The most important principle is simple: keep the application a thin, testable
planning/UI layer over public Taskwarrior and Timewarrior interfaces. Do not turn
it into another task database.

## 1. Architectural invariants

These rules should be treated as design constraints.

### Taskwarrior is the source of truth

All task reads and writes go through the Taskwarrior CLI adapter.

Do not:

- read or write `taskchampion.sqlite3` directly;
- maintain a second persistent copy of task state;
- invent synchronization semantics separate from Taskwarrior.

Local application state may cache the current view for interactive filtering and
sorting, but it is disposable.

### Timewarrior is auxiliary

Timewarrior contributes observed effort. It is not required for core task
management or planning.

Failure or absence of Timewarrior must not corrupt Taskwarrior state.

### Planning code should remain deterministic

Graph construction, critical-path calculations, scheduling, and report
formatting should be testable without a running Textual application whenever
possible.

### Mutations should be explicit

Operations that make significant planning changes, especially auto-scheduling,
must remain previewable before application.

### Coverage is a gate, not a metric for display

The repository requires 100% statement and branch coverage. New branches require
new tests. Do not use coverage exclusions merely to keep the number green.

## 2. Repository layout

```text
src/taskwarrior_textual/
    __main__.py       CLI entry point and non-interactive checks
    app.py            Textual application controller and user actions
    ui.py             modal screens and forms
    models.py         Task model and exported-field interpretation
    taskwarrior.py    Taskwarrior / Timewarrior CLI adapter
    planning.py       planning graph and scheduling primitives
    reporting.py      higher-level planning and report generation
    config.py         persistent planning settings and working calendar

tests/
    test_app.py
    test_config.py
    test_main.py
    test_models.py
    test_package.py
    test_planning.py
    test_taskwarrior.py
```

The current large modules are intentionally separated by responsibility.
Splitting a file is useful when responsibilities diverge, not merely because a
line-count threshold has been crossed.

## 3. Data flow

A normal read path is:

```text
Textual action
    |
TaskwarriorApp
    |
TaskwarriorClient.view()
    |
task ... export
    |
Task.from_export()
    |
cached current view
    |
local filtering/sorting
    |
DataTable
```

A planning path is:

```text
current Task objects
    |
optional dependency expansion
    |
planning graph
    |
remaining effort / working calendar
    |
report or schedule proposal
    |
Textual screen
```

A mutation path is:

```text
form / action
    |
validation
    |
TaskwarriorClient
    |
task CLI
    |
refresh current view
```

## 4. Module responsibilities

### `models.py`

Owns the in-memory representation of exported Taskwarrior tasks.

Keep Taskwarrior-export parsing here rather than scattering field conversion
through UI code.

### `taskwarrior.py`

Owns external process interaction.

Responsibilities include:

- locating `task` and optionally `timew`;
- invoking subprocesses;
- converting non-zero exits into `TaskwarriorError`;
- Taskwarrior exports and named views;
- task mutations;
- recursive dependency fetching;
- Timewarrior interval parsing and matching.

No Textual widget logic belongs here.

### `planning.py`

Owns planning primitives.

Examples:

- dependency graph construction;
- cycle information;
- remaining effort;
- relative scheduling;
- absolute/calendar scheduling;
- capacity constraints.

Prefer pure functions and immutable result structures.

### `reporting.py`

Builds higher-level human-readable analyses from models and planning primitives.

It currently contains dependency, critical-path, Gantt, calendar, health,
Timewarrior, project, and scheduling-proposal reporting.

If this module is split in the future, split by cohesive report families and
keep deterministic calculations outside Textual widgets.

### `ui.py`

Owns modal forms and screens.

A screen should generally:

- receive already prepared data;
- render it;
- collect user input;
- dismiss with a small typed result.

Do not put Taskwarrior subprocess access into screens.

### `app.py`

Coordinates the application.

It owns:

- bindings;
- loaded view state;
- local search/filter/sort state;
- screen opening;
- calls into the client;
- refresh after mutations;
- routing between UI and planning/reporting.

Avoid growing it back into a monolith. New calculations normally belong in
`planning.py` or `reporting.py`, and new standalone interfaces belong in
`ui.py`.

### `config.py`

Owns configuration parsing, validation, and the working calendar.

Unknown planning keys are rejected intentionally. Configuration mistakes should
fail visibly instead of being silently ignored.

## 5. Taskwarrior boundary

Use the public Taskwarrior CLI. The adapter should remain the only layer that
knows command-line syntax.

When adding a new Taskwarrior operation:

1. add a narrowly scoped method to `TaskwarriorClient`;
2. pass explicit arguments, never shell-constructed command strings;
3. raise `TaskwarriorError` for execution failures;
4. add unit tests for success and failure;
5. expose it through an application action only after the adapter is tested.

The application uses `subprocess.run(..., shell=False)`. Preserve this property.

## 6. Timewarrior matching

Timewarrior intervals do not inherently carry a Taskwarrior UUID in the current
integration. The adapter matches intervals using a signature constructed from:

- task description;
- Taskwarrior tags;
- project, when present.

Only unambiguous signatures are accepted.

When modifying this mechanism, avoid silently attributing one interval to the
wrong task. Ambiguity should reduce available tracking information rather than
create false precision.

## 7. Local state versus authoritative state

`TaskwarriorApp.view_tasks` is the current Taskwarrior result.

Search, project filter, tag filter, blocked-only, active-only, and sort order are
local transformations over that list.

They should not call Taskwarrior again.

Operations that change the authoritative view, such as switching from pending to
waiting or explicitly refreshing, do call Taskwarrior.

This distinction is both a performance property and a testable behavioral
contract.

## 8. Dependencies

The planning editor accepts UUIDs or unique UUID prefixes.

Before a modification is sent to Taskwarrior, the application checks:

- the prefix exists;
- it is unambiguous;
- it does not refer to the task itself;
- the resulting graph does not introduce a cycle through the edited task.

Do not move these protections into presentation-only code.

## 9. Scheduling

Scheduling depends on:

- dependency order;
- estimates;
- already tracked effort;
- current time;
- configured working calendar;
- explicit `scheduled` constraints;
- due dates;
- optional capacity.

Important distinction:

- external dependencies may influence calculations;
- auto-scheduling only proposes modifications for eligible tasks in the selected
  project.

Preserve this ownership boundary.

## 10. Adding a new key binding

A typical new application command requires:

1. add the binding to `TaskwarriorApp.BINDINGS`;
2. add an `action_...` method;
3. keep substantial calculation outside the action;
4. add interaction tests using Textual's test pilot;
5. update the in-application help if the command is user-facing;
6. update the README/tutorial where appropriate.

The help screen is part of the product contract. A new user-facing binding is
not complete until it is discoverable.

## 11. Adding a new modal screen

Prefer a small screen in `ui.py`.

The pattern is:

1. constructor receives the minimum data needed;
2. `compose()` renders widgets;
3. key/button handlers dismiss the screen with a compact value;
4. `TaskwarriorApp` handles the returned value and performs mutations.

For read-only analysis screens, pass a prepared report body rather than making
the screen calculate it.

## 12. Adding a new report

Prefer this dependency direction:

```text
models/config
      |
      v
planning primitives
      |
      v
reporting
      |
      v
app
      |
      v
ui
```

A report should be callable directly from tests without constructing the Textual
application when practical.

## 13. Tests

The test suite is not secondary documentation; it defines expected behavior.

Useful boundaries are:

- model parsing in `test_models.py`;
- CLI adapter behavior in `test_taskwarrior.py`;
- scheduling mathematics in `test_planning.py`;
- config/calendar behavior in `test_config.py`;
- Textual interactions and actions in `test_app.py`;
- CLI flags in `test_main.py`;
- packaging/import assumptions in `test_package.py`.

For a bug fix, first reproduce the bug in a focused test whenever possible.

For a new branch in production code, add tests for both outcomes. The coverage
gate is branch-aware.

## 14. Quality gate

The authoritative local gate is:

```sh
make check
```

It runs:

1. Ruff over `src` and `tests`;
2. mypy over the package;
3. pytest in parallel;
4. statement and branch coverage with a required 100%;
5. wheel and source-distribution builds;
6. package-content checks;
7. installation of the built wheel in a clean virtual environment and a CLI
   version check.

GitHub Actions uses one full gate on Python 3.13 and a lighter compatibility
test run on Python 3.11. This avoids duplicating lint, typing, coverage, and
package-build work while still exercising the supported minimum Python version.

CI runs for pull requests targeting `main` and for pushes to `main` in the
private development repository. Stale runs for the same branch/PR are cancelled
automatically. The public mirror keeps the workflow file for reproducibility,
but its jobs are skipped.

If CI is green on the exact commit under review, there is normally no reason to
rerun the same gate manually merely for confirmation.

Useful focused commands while developing are:

```sh
make lint
make typecheck
make test
make test-serial
make package
make verify-package
make test-compat
```

`make test-serial` is useful when debugging ordering, asynchronous, or
Textual-test failures.

## 15. Reports

`make report` writes reviewable machine/human outputs below `reports/`,
including Ruff, mypy, pytest/JUnit, and coverage data.

`make push-reports` exists for workflows where those generated reports are
intentionally committed. It is not required to establish correctness when the
CI quality gate already passed.

## 16. Configuration compatibility

When adding a configuration key:

1. add it to the settings model;
2. define a conservative default;
3. validate its type and semantic range;
4. update `config.example.toml`;
5. update user documentation;
6. add tests for valid, invalid, omitted, and unknown-key behavior as relevant.

Avoid silently accepting misspelled keys.

## 17. Error handling

External command failures should become `TaskwarriorError`.

Configuration failures should become `ConfigError`.

The Textual application should present recoverable runtime errors in the UI
rather than crashing when possible.

Do not catch broad exceptions unless the layer can actually recover or add
useful context.

## 18. Release and publication workflow

The development repository is private. The public
`fmaillar/taskwarrior-textual` repository is a publication mirror containing
validated Git history, tags, and release material only. Pull requests, review
automation, and development-only branches stay private.

The expected local remotes are:

```text
origin  -> private development repository
public  -> public publication mirror
```

For a tagged release:

1. ensure private `main` is green;
2. review user-visible documentation and `?` help;
3. confirm the version in `pyproject.toml` and `taskwarrior_textual.__version__`;
4. confirm `CHANGELOG.md`;
5. build and verify the package through the CI quality gate;
6. tag the exact validated `main` commit;
7. push the tag to `origin`;
8. run `make publish` from a clean local `main`.

`make publish` intentionally does not rerun the quality gate. It requires
`main`, a clean worktree, and `HEAD == origin/main`, then pushes only
`main` and tags to the configured public remote.

Do not tag or publish a commit whose private CI has not passed.

## 19. Refactoring policy

Refactor when there is a concrete maintenance benefit:

- responsibilities are mixed;
- a unit cannot be tested independently;
- duplication is creating divergent behavior;
- additions repeatedly require unrelated changes;
- cognitive complexity is becoming a practical problem.

Do not split modules purely to reduce line counts. A cohesive 500–1000 line
module can be easier to maintain than a fragmented package with circular
dependencies.

Current likely future split points, if growth justifies them, are:

```text
ui/
    forms.py
    reports.py
    project.py
    help.py

reports/
    dependencies.py
    schedule.py
    timewarrior.py
    project.py
```

These are options, not current requirements.

## 20. Security and data integrity

The application controls shell-adjacent tools and task metadata, so maintainers
should preserve the following:

- never use `shell=True` for Taskwarrior/Timewarrior calls;
- pass subprocess arguments as sequences;
- never evaluate task text as code;
- do not directly manipulate TaskChampion storage;
- validate user-entered planning values before mutation;
- retain confirmation for destructive actions;
- retain preview-before-apply for bulk scheduling changes.

## 21. Before merging a change

A maintainer should be able to answer yes to all relevant questions:

- Is Taskwarrior still the single source of truth?
- Is the new logic in the correct architectural layer?
- Does the change avoid unnecessary Taskwarrior refetches?
- Are failure paths tested?
- Are new branches covered?
- Is a new user-facing binding documented in `?`?
- Does configuration documentation match validation?
- Does the exact commit pass CI on Python 3.11 and 3.13?
- Does packaging still build?

If so, the change fits the current maintenance model.
