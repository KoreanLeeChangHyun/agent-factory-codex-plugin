---
name: work-units
description: Manage and execute optional canonical Agent Factory Work Units and Work Packages in the primary Git workspace when the Human explicitly selects those advanced routes.
---

# Work Units

## Entry contract

Use this skill only after the Human explicitly selects a Work Unit or Work
Package route. Read the complete management or execution reference before
invoking a manager. Canonical package writes must use the scripts in
`scripts/`.

## Reference routing

- `references/work-unit-management.md`: Create, validate, transition, and record canonical Work Units and Work Packages.
- `references/work-unit-structure.md`: Review the canonical Work Unit package structure before authoring or reviewing one.
- `references/work-unit-execution.md`: Launch Goal-bound execution in the primary Git workspace.

## Assets and tools

`scripts/` owns Work Unit, Work Package, Goal launcher, and scheduler managers.
`assets/` owns their profiles and schemas; `tests/` owns regression coverage.
`scripts/requirements.txt` declares manager dependencies.
