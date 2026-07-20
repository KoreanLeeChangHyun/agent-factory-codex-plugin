---
name: work-unit-planner
description: Use when transforming a validated ready Agent Factory Intake package into executable Work Units for a named /goal work-unit-id. Work Units are self-contained execution and review units with Plan, Work, AI Review, Report, verification, separate AI and Human checklists, and Human approval boundaries.
---

# Work Unit Planner

Transform a validated `ready` Intake package into a self-contained Work Unit.
This skill owns the Work Unit v4 section profile, metadata schema, artifact
adapter, and semantic rules. Lifecycle owns the shared sectioned-document
engine and structural component schemas.
Read `lifecycle/references/lifecycle.md`,
`lifecycle/references/common-document-contract.md`, and
`references/work-unit-structure.md` before creating or reviewing a package.

## Planning Boundary

- Apply the Interview Decision Gate from `fact-only` before asking for a
  decision or declaring planning complete.
- Resolve the source Intake with its manager and run full validation. Do not
  trust status text alone.
- The source Intake must be `ready`, have no blocking open item, and contain the
  selected item in `work-unit-basis`.
- Create an `intake-basis-ref` whose typed source reference points to the Intake
  package root and anchors the selected `{sectionId, itemId}`. The Work Unit
  manager deterministically validates package identity, TOC integrity, anchor
  existence, and Intake readiness.
- Preserve applicable Specification, evidence, requirement, and decision refs
  from Intake. Preserve explicit `not-applicable` results; do not invent design
  coverage.
- Do not create executable Work Units from vague ideas, direct chat context, or
  unvalidated notes. Ask when a fresh execution session would lack a material
  decision.

## Package Rules

- Store each package at
  `<project-root>/.agent-factory/work-units/<work-unit-id>/`; directory and
  metadata ids must match.
- Use only `assets/scripts/work_unit.py` to create and mutate canonical data.
  Run `validate --full` before transition to `ready` or handoff.
- Canonical data is strict JSON. Actual CSS or style data is forbidden.
- Do not manually edit the manager-owned table of contents or block index.
- Use registered `blocks/**` for large logs, screenshots, and other non-JSON
  evidence. Passing review evidence must be non-empty and registered.
- The manager increments `documentVersion` once per mutation and recovers interrupted
  transactions from `.manager/transaction.json`.
- Existing incompatible data need not be rewritten or accepted by v4. Never
  relabel incompatible storage as a conforming package.

## Required Sections

The exact section and required-kind contract is owned by
`assets/profiles/work-unit.profile.json`:

1. `basis`
2. `work-definition`
3. `plan`
4. `execution-context`
5. `acceptance-and-verification`
6. `execution`
7. `ai-review`
8. `human-review`
9. `report`

Title is H1, sections are H2, and optional subsections are H3. Deeper hierarchy
is invalid. TOC array order owns document order.

## Execution Contract

- The Work Unit definition session and execution session are separate. A fresh
  session receiving only `/goal <work-unit-id>` must be able to execute it.
- Record the goal, scope, exclusions, expected output, plan, acceptance
  criteria, Definition of Done, tests, quality checks, AI checklist, Human
  checklist, Human review method, evidence requirements, risks, and unresolved
  items in canonical section items.
- Record execution context with goal id, objective, exec invocation, execution
  agent, repository, base ref, dedicated `work-unit/<work-unit-id>` branch, and
  canonical absolute linked worktree path
  `<repository>/.agent-factory/worktree/<work-unit-id>`.
- Keep the physical package at schema version `4.0.0`. Active execution uses a
  manager-owned `execution-state` item whose independent semantic contract is
  `contractVersion: 1.0.0`. Existing terminal v4 packages without this item
  remain readable; a new active execution must run `execution-init` first.
- `execution-init` binds revision 1 to the inspected Git head. `attempt-start`
  starts attempt 1 or archives the previous attempt before a same-revision
  retry. `attempt-resume` appends a Codex session id to the current invocation
  chain without creating an attempt. Human-approved `rework-start` archives the
  current attempt, increments revision, clears attempt identity, and
  invalidates current execution, quality, AI review, report, and Human review
  results in one transaction.
- `execution-init` and `attempt-start` resolve `git rev-parse HEAD` in the
  recorded prepared worktree and reject a supplied `--head-commit` that does
  not exactly match it. Before Human approval, a failed `review` audit may use
  `attempt-start` for a same-revision retry; Human rework remains the separate
  revision-increment operation.
- Passing execution, quality, AI review, report, and Human approval records for
  an active execution must carry an `executionTarget` matching the current
  contract version, revision, attempt, primary invocation id, and Git head.
  Stale targets cannot enter `review` or validate as `done`.
- `work-unit-execution` owns Git worktree and branch side effects. Planning must
  not create, remove, unlock, merge, or promote them.
- Execute Plan -> Work -> AI Review -> Report. Code Work Units use TDD.
- A transition to `review` requires passing execution verification, quality
  evidence, AI review/checklist, and report verification evidence.
- A transition to `done` requires `--human-review approved`; approval status and
  timestamp are committed atomically with the lifecycle transition.
- Human approval, rework, merge, deployment, and PR promotion remain Human
  decisions. AI completion means review material is ready, not that Human
  approval already occurred.
- Register a successful `work-unit-execution integrate` JSON document with
  `integration-put <package> <receipt> --path blocks/<path>`. The manager
  validates execution-context identity and result consistency, then atomically
  stores the immutable raw receipt block and a normalized `integration-result`
  in `report`. Repeating the same receipt and path is an idempotent no-op;
  reusing the path for different evidence is rejected.
- Integration is orthogonal to the Work Unit lifecycle. `integration-put` may
  append a valid receipt without reopening or changing `working`, `review`, or
  terminal `done`; it never supplies Human approval or performs Git mutation.
- Work Unit outputs are internal. Do not automatically promote them to Customer
  Deliverables.

## Commands

The manager supports schema checks, creation, focused/full display, title and
metadata replacement, single/batch section item updates, optional section
management, block registration/removal, execution initialization, attempt
start/resume, Human-approved rework, integration receipt registration,
validation, and lifecycle transitions. `execution-state` is manager-owned and
cannot be replaced through generic section commands.
Supply only typed semantic data arguments; the shared manager constructs and
serializes JSON. Never compose JSON strings or temporary JSON value files. See
`references/work-unit-structure.md` for exact examples and validation gates.

## Output

- Decompose oversized requests into independently executable and reviewable
  Work Units with explicit dependencies and execution order.
- List created ids in dependency order.
- Include Human checklist and Human review method requirements in Definition of
  Done.
- List unresolved decisions separately.
- When creating Work Units, include this exact label followed by a code block
  containing only one id per line:

`생성한 Work Unit 이름`
