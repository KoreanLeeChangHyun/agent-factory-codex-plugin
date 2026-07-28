---
name: work-unit-planner
description: Create and manage executable Agent Factory Work Units from ready Intake packages through the canonical work_unit.py manager.
---

# Work Unit Planner

## Mandatory Manager Script Gate

All canonical Work Unit operations must use
`assets/scripts/work_unit.py` as a hard precondition. If the manager cannot
perform an operation, stop before mutation. Do not fall back to direct JSON
editing and do not create an exception path.

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

## Required output

When creating Work Units, include:

`생성한 Work Unit 이름`

followed by a code block containing only one id per line.
