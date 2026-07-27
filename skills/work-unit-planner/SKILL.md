---
name: work-unit-planner
description: Use when transforming a validated ready Agent Factory Intake package into executable Work Units for a named /goal work-unit-id. Work Units are self-contained execution and review units with Plan, Work, AI Review, Report, verification, separate AI and Human checklists, and Human approval boundaries. All canonical Work Unit package operations must go through assets/scripts/work_unit.py and fail closed when that script cannot perform the operation.
---

# Work Unit Planner

Transform a validated `ready` Intake package into a self-contained Work Unit.
This skill owns the Work Unit v4 section profile, metadata schema, artifact
adapter, and semantic rules. Lifecycle owns the shared sectioned-document
engine and structural component schemas.
Read `lifecycle/references/lifecycle.md`,
`lifecycle/references/common-document-contract.md`, and
`references/work-unit-structure.md` before creating or reviewing a package.

## Mandatory Manager Script Gate

Treat `assets/scripts/work_unit.py` as a hard precondition for every canonical
Work Unit package operation. Resolve it from this skill directory and invoke it
before creating, showing, mutating, validating, transitioning, admitting,
recording execution or review state, registering or removing blocks, or
recovering a Work Unit package.

- Use the manager command that owns the requested operation. Use `show`,
  `validate`, and `admit` for their authoritative package gates.
- Supply only typed semantic arguments. Let the manager construct, serialize,
  order, version, and transactionally write canonical JSON.
- Never create, update, delete, replace, move, or repair canonical Work Unit
  JSON with `apply_patch`, shell redirection, an ad hoc program, file copy or
  move, temporary JSON files, or any generic filesystem or MCP write tool.
- Never add, invoke, or rely on a hook to enforce this rule. The skill
  instruction and exact manager invocation are the enforcement contract.
- If `assets/scripts/work_unit.py` is unavailable, fails, or cannot express the
  required operation, stop before mutation. Report the exact command, package,
  operation, and failure or capability gap. Do not fall back to direct JSON
  editing and do not create an exception path.

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
- Apply the Mandatory Manager Script Gate without an exception.
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
  chain without creating an attempt. Human-approved `rework-start` requires
  and stores the exact Human Rework instruction, archives the current attempt,
  increments revision, clears attempt identity, and
  invalidates current execution, quality, AI review, report, and Human review
  results in one transaction.
- `admit` is the machine-readable initial execution gate. It full-validates the
  canonical package and ready semantics, verifies the same Work Unit id,
  repository, branch, and worktree path, and treats the recorded `baseRef` as
  the symbolic history owner rather than the requested execution commit.
  The requested base must resolve to the latest package-changing commit
  reachable from that `baseRef`, and the current package must match that exact
  checkpoint. `worktree.py prepare` must obtain this mutation-free result
  before its first Git mutation.
- `execution-progress` durably records pending and completed steps, the last
  verified repository head, and stable idempotency identities.
  `execution-failure` records bounded transient retry state and atomically
  creates an evidence-backed blocker when retry is exhausted or the failure is
  permanent. `blocker-resolve` preserves the active revision and attempt while
  assigning recovery to a new invocation and returning `blocked` to `working`.
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
