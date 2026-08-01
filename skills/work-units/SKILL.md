---
name: work-units
description: Manage and execute canonical Agent Factory Work Units and Work Packages.
---

# Work Units

## Entry contract

Use this skill for every Work Unit or Work Package operation. Read the complete
management or execution reference, plus its linked contract, before invoking a
manager. Canonical package writes must use the scripts in `scripts/`.

## Reference routing

- `references/work-unit-management.md`: Create, validate, transition, and record canonical Work Units and Work Packages.
- `references/work-unit-structure.md`: Review the canonical Work Unit package structure before authoring or reviewing one.
- `references/work-unit-execution.md`: Launch Goal-bound execution and manage code-only linked worktrees.
- `references/worktree-contract.md`: Apply the exact worktree identity, prepare, integration, cleanup, and refusal contract.

## Assets and tools

`scripts/` owns Work Unit, Work Package, Goal launcher, scheduler, and worktree
managers. `assets/` owns their profiles and schemas; `tests/` owns regression
coverage. `scripts/requirements.txt` declares manager dependencies.
