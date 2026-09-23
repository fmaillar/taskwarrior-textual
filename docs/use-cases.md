# Use cases

This document describes practical workflows rather than individual features.

## 1. Daily task triage

Goal: quickly reduce a large pending list to the tasks relevant right now.

Workflow:

1. press `1` for pending tasks;
2. use `/` to search by text;
3. use `p` to restrict to one project;
4. use `f` to restrict to one tag;
5. use `b` when you specifically want blocked/dependent work;
6. use `v` to see only currently active work;
7. press `t` to cycle through urgency, date, project, and priority ordering;
8. press `c` to reset the local working set.

Why this is useful: these are local operations over the cached Taskwarrior view.
They are fast and do not repeatedly query Taskwarrior.

## 2. Focus on today's execution

Goal: inspect a task, start it, track work, and complete it without leaving the
terminal.

Workflow:

1. select the task;
2. press `Enter` to inspect the canonical Taskwarrior details;
3. press `s` to start;
4. work;
5. press `x` to stop if the work is interrupted;
6. press `s` again when resuming;
7. press `d` when complete.

When the Taskwarrior/Timewarrior hook is installed, tracked work becomes
available to the effort and trend reports.

## 3. Plan a project with prerequisites

Goal: express execution order and identify what controls the project duration.

Workflow:

1. assign tasks to the same Taskwarrior project;
2. add estimates with `E`;
3. add dependencies using full UUIDs or unique UUID prefixes;
4. press `g` on individual tasks to inspect their neighborhood;
5. press `G` for the whole dependency overview;
6. press `C` for the critical path;
7. press `H` for a Gantt-like representation.

The planning editor rejects dependency cycles before writing the change.

Use this workflow before auto-scheduling. An automatic schedule can only be as
meaningful as the graph and estimates it receives.

## 4. Plan across project boundaries

Goal: account for prerequisites that belong to another project.

A project task may depend on a task outside its own project. The application can
recursively fetch those prerequisites according to `dependency_depth`.

Example:

```text
infra.Rotate certificates
        |
        v
release.Deploy service
        |
        v
release.Announce release
```

The external `infra` task participates in project calculations. It can appear
in the cockpit as an actionable prerequisite, but the project's auto-scheduler
does not rewrite unrelated external tasks.

This distinction is intentional: external work can constrain a project without
becoming owned by that project.

## 5. Check whether a plan is internally consistent

Goal: find planning defects before relying on dates.

Press `I` for planning health.

Typical problems reported include:

- dependency cycles;
- tasks blocked by cycles;
- unresolved dependencies;
- missing estimates;
- malformed or unusable `scheduled` values;
- malformed or unusable `due` values;
- projected lateness;
- tracked effort exceeding estimates.

Use this report after a substantial planning edit and before accepting an
auto-schedule.

## 6. Turn relative effort into calendar dates

Goal: answer "when does this project finish under my actual working calendar?"

Configure:

- timezone;
- working days;
- working periods;
- holidays;
- optional parallel capacity.

Then press `L` for the calendar plan.

This view combines dependencies, remaining effort, explicit scheduling
constraints, and the working calendar into absolute start and finish times.

Press `K` when you need to understand which explicit scheduling constraints
are influencing the result.

## 7. Auto-schedule a project without blindly rewriting it

Goal: generate a feasible proposed schedule while retaining human control.

Workflow:

1. select a task in the target project;
2. press `I` and resolve planning-health problems;
3. optionally inspect `C` and `L`;
4. press `S`;
5. review the proposed modifications;
6. apply only if the result is appropriate.

The preview/apply split is a safety property. The scheduler does not silently
rewrite the project as soon as the key is pressed.

## 8. Use the project cockpit as the main project view

Goal: manage a project from one terminal surface.

Press `O` on a task belonging to the project.

The cockpit brings together:

- project scope;
- external prerequisites;
- estimates;
- tracked/remaining effort;
- graph health;
- critical path;
- projected finish;
- actionable task rows.

Inside the dashboard:

```text
Enter   inspect
e       edit normal task fields
E       edit planning
g       dependencies
s       start
x       stop
d       complete
S       auto-schedule
```

This is the most suitable workflow when the project, rather than the global task
list, is the unit of work.

## 9. Compare estimates with actual effort

Goal: improve future planning from observed work.

Requirements:

- estimates on tasks;
- Timewarrior intervals that can be matched unambiguously to those tasks.

Use:

```text
T   current effort / remaining-work report
R   historical trend views
```

A useful review loop is:

1. inspect estimated versus tracked effort;
2. identify systematic under- or over-estimation;
3. adjust future estimates, not historical data;
4. compare the next project.

## 10. Use milestones

Goal: represent meaningful events that consume no working time.

Set:

```text
estimate:0
```

Press `M` to inspect milestones explicitly.

Examples:

- release approved;
- procurement decision;
- external handoff;
- deployment complete.

A milestone participates in dependencies while contributing zero duration.

## 11. Work with waiting and scheduled tasks

Goal: inspect tasks that are deliberately unavailable until later.

Use:

```text
2   waiting
5   scheduled
```

The table's "When" column adapts to the current view. Waiting tasks show their
wait time; scheduled tasks show their scheduled time.

Use the dedicated planning editor `E` when modifying these values.

## 12. Synchronize explicitly

Goal: keep Taskwarrior synchronization an explicit user action.

Press `y` to invoke `task sync`.

The TUI does not replace Taskwarrior's synchronization model. It calls the
public Taskwarrior CLI and then refreshes the current view.

## 13. Work without Timewarrior

Timewarrior is optional.

Without it:

- task browsing and editing still work;
- dependencies and project planning still work;
- calendar planning still works from estimates;
- tracked effort is unavailable;
- Timewarrior reports contain no tracking data;
- remaining work is based solely on estimates.

This is a valid configuration.

## 14. Recover from a confusing view

If the displayed set no longer matches your mental model:

1. press `c` to clear local filters and sorting;
2. press the desired view key `1`–`5`;
3. press `r` to reload from Taskwarrior;
4. press `?` if a binding is unclear.

Because Taskwarrior remains the source of truth, the CLI can always be used to
inspect the underlying task state independently.
