# Changelog

All notable changes to this project are documented here.

The project follows semantic versioning once releases are tagged.

## 0.1.0

Initial public release.

### Added

- Textual task browser and editor backed by the public Taskwarrior CLI.
- Pending, waiting, completed, deleted, and scheduled views.
- Local search, project/tag filters, blocked/active filters, and deterministic sorting.
- Task creation, editing, start/stop, completion, deletion, and synchronization.
- Separate planning editor for dependencies, scheduling fields, and estimates.
- Dependency expansion, cycle detection, dependency overview, critical path, and Gantt views.
- Working-calendar scheduling with timezone, work periods, holidays, and capacity.
- Planning-health diagnostics, milestones, calendar plans, and scheduling constraints.
- Preview-before-apply project auto-scheduling.
- Interactive project cockpit with external prerequisite visibility.
- Optional Timewarrior effort and trend reporting.
- Persistent TOML planning configuration with strict validation.
- In-application help with `?`.
- User tutorial, practical use cases, and maintainer documentation.
- Ruff, mypy, 100% branch-aware test coverage, package builds, isolated wheel verification, and CI on supported Python versions.

### Architecture

- Taskwarrior remains the single source of truth.
- No direct access to `taskchampion.sqlite3`.
- Timewarrior remains optional and auxiliary.
- Public releases are published from a private development repository as a clean Git-only mirror.
