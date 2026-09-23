# Contributing

## Repository model

The public `fmaillar/taskwarrior-textual` repository is a publication mirror.
Development, CI review, and release preparation happen in a separate private
development repository.

This separation keeps development-only metadata such as internal branches,
reviews, automation comments, and pull-request history out of the public
release repository.

## Reporting bugs and proposing changes

For bugs or feature proposals, open a GitHub issue on the public repository with:

- the Taskwarrior version;
- the Python version;
- the `taskwarrior-textual` version or commit;
- the relevant configuration;
- concise reproduction steps;
- expected and observed behavior.

Do not include private Taskwarrior data, credentials, tokens, or confidential
task descriptions.

## Pull requests

Please do not open pull requests against the public mirror unless a maintainer
explicitly asks for one. Changes are integrated in the development repository
and then published to the public mirror.

For a substantial contribution, discuss the change in an issue first so the
maintainer can arrange the appropriate integration path.

## Development checks

The authoritative local gate is:

```sh
make check
```

It runs Ruff, mypy, the branch-aware 100% coverage test suite, builds wheel and
sdist artifacts, checks package contents, and installs the built wheel in a
clean virtual environment.

Useful focused commands are:

```sh
make lint
make typecheck
make test
make test-compat
make test-serial
make package
make verify-package
```

New production branches require tests for all outcomes. Do not weaken the
coverage gate or add exclusions solely to preserve the percentage.

## Design constraints

Contributions must preserve these invariants:

- Taskwarrior is the source of truth.
- Taskwarrior and Timewarrior are accessed through their public CLIs.
- `taskchampion.sqlite3` is never read or modified directly.
- Timewarrior remains optional.
- destructive or bulk planning mutations remain explicit and reviewable.
- subprocess calls use argument sequences rather than `shell=True`.
