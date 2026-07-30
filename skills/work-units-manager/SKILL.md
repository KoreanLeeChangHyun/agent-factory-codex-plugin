---
name: work-units-manager
description: Create and manage executable Agent Factory Work Units from ready Intake packages through the canonical work_unit.py manager.
---

# Work Unit Planner

## Mandatory Manager Script Gate

All canonical Work Unit operations must use
`scripts/work_unit.py` as a hard precondition. If the manager cannot
perform an operation, stop before mutation. Do not fall back to direct JSON
editing and do not create an exception path.

The manager's complete CRUD core is:

```text
python3 scripts/work_unit.py create <package> --id <id> --title <title> --project-id <project> --language <language> --theme <theme>
python3 scripts/work_unit.py show <package> [--section <section-id>]
python3 scripts/work_unit.py delete <package> --confirm-id <id> [--allow-invalid]
python3 scripts/work_unit.py title-set <package> <title>
python3 scripts/work_unit.py metadata-set <package> <field> <typed-data-arguments>
python3 scripts/work_unit.py section-put <package> <typed-data-arguments>
```

Use `--allow-invalid` only as the explicit opt-in for deleting a package that
fails full validation; the manager still requires exact confirmation and
canonical identity.

## Creation

Create a Work Unit only from a full-valid ready Intake basis. It must be
self-contained for a new Workflow Agent session and include:

- goal, scope, exclusions, expected output;
- Plan, acceptance criteria, tests, and quality checks;
- AI checklist and Human review checklist;
- execution context and `executionMode`;
- report and evidence requirements.

The basis reference records the canonical Intake package root and exact section
and item anchor.

`executionMode` is:

- `specification-direct` when the complete scope is canonical Specification
  CRUD. It uses `specification.py` in the primary root and has no worktree.
- `worktree` for every other implementation. It uses the derived branch and
  linked worktree, with `.agent-factory` excluded.

The primary main agent checks sufficiency once before launch. No checkpoint,
artifact commit, hash snapshot, or approval step exists.

## Execution state

Manager-owned execution-state contract v2 records:

- revision and attempt;
- primary invocation id and resume invocation chain;
- ordered attempt history;
- idempotent progress records and bounded retry evidence;
- current recovery owner.

It does not record Git subjects, HEAD commits, immutable snapshots, or
checkpoints. `execution-init` and `attempt-start` therefore do not accept
`--head-commit`. `execution-migrate` upgrades legacy v1 state.

`attempt-resume` binds a new background Goal thread to the current attempt.
`rework-start --instruction <text>` archives the reviewed attempt, increments
the revision, invalidates stale outcome evidence, and prepares the next attempt.

## Review

Execution may transition to `review` only with passing execution, quality,
AI-review, and report evidence bound to the current revision/attempt/invocation.

The Human chooses:

- `rework`, recorded through `rework-start`;
- `complete`, recorded through
  `transition <package> done --review-decision complete`.

This is not an approval gate. Integration receipts contain no
`humanDecision`. Completion of `worktree` mode triggers integration in the
main lifecycle; `specification-direct` has no integration.

Completed outcome records are immutable. Completed clean worktrees are removed
later through batch cleanup.

## Work Packages

Use `scripts/work_package.py` for every canonical
`.agent-factory/work-packages/<package-id>` operation. Never edit Work Package
JSON directly. A package owns its positive `maxParallel`, DAG nodes and
prerequisites, repository and target/integration branches, durable lease and
events, node idempotency keys, package review, member traceability, rework
impact, and single integration receipt.

Run `preflight` before execution. It full-validates every member, repository
identity, readiness, execution mode, graph references and cycles, and
branch/worktree collisions without mutation. `execution-start` converts a
successful preflight into the ACK-bound running state. Use `state-put` for
scheduler state, `review-put` for the package AI/Human review handoff,
`rework-start` for affected nodes and descendants, and `complete` for the one
target integration receipt.

The lifecycle is `draft -> ready -> working <-> recovering -> review -> done`.
After ACK it never uses terminal `blocked` or `failed`.

## Required output

When creating Work Units, include:

`생성한 Work Unit 이름`

followed by a code block containing only one id per line.
