# Security policy

## Supported versions

Security fixes target the latest released version and current `main`.

## Reporting a vulnerability

Do not open a public issue for a vulnerability that could expose user data,
execute unintended commands, corrupt Taskwarrior state, or bypass a safety
confirmation.

Use GitHub's private vulnerability reporting / security-advisory mechanism for
this repository when available. If that mechanism is unavailable, contact the
maintainer privately through the maintainer's GitHub profile before publishing
technical details.

Include only the minimum information needed to reproduce the problem. Do not
send real Taskwarrior databases, credentials, access tokens, or confidential
task contents.

## Security boundaries

The project deliberately:

- uses the Taskwarrior CLI instead of accessing TaskChampion storage directly;
- invokes Taskwarrior and Timewarrior without `shell=True`;
- validates planning input before mutation;
- confirms destructive task deletion;
- previews project auto-scheduling before applying modifications;
- treats ambiguous Timewarrior-to-task matching as unavailable data rather than
  guessing.

Changes affecting these boundaries require focused tests.
