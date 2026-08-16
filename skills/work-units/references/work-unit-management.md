# Work Unit Planner

## Mandatory Manager Script Gate

All canonical Work Unit operations must use
`scripts/work_unit.py` as a hard precondition. If the manager cannot
perform an operation, stop before mutation. Do not fall back to direct JSON
editing and do not create an exception path.

The manager's canonical package command examples are:

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

Create a Work Unit only when the Human explicitly requests that advanced route.
Do not infer it from task size, repository state, available Intake entries, or
the existence of historical Work Units. It must be
self-contained for a new Workflow Agent session and include:

- goal, scope, exclusions, expected output;
- Plan, acceptance criteria, tests, and quality checks;
- optional Documentation and independent AI-review plans when explicitly selected;
- Human review checklist;
- execution context and `executionMode`;
- report and evidence requirements.

Every test criterion is a conditional plan, not execution authority. When the
Human requests testing, record exact supplied commands unchanged or record the
smallest bounded commands selected from repository evidence. When testing was
not requested, the criterion must say that no tests are authorized and the
report must record that tests were not run. This gate includes smoke checks,
lint, type checks, build verification, and other verification commands.

The `work-basis-ref` records one explicit basis type: the Human request, the
target Project Skill, or a canonical Intake package with exact entry ids. An
Intake is never required merely because a Work Unit was selected. Existing
`intake-basis-ref` items remain valid as the Intake-specific legacy shape.

`executionMode` is selected only inside the explicit Work Unit route:

- `workspace-direct` for ordinary code or project-file work in the opened
  primary Git workspace. It creates no branch or linked worktree.
- `specification-direct` when the complete scope is canonical Specification
  CRUD. It uses `specification.py` in the primary root and has no worktree.
- `worktree` only when the Human also explicitly requested a linked worktree.
  It uses the derived branch and
  linked worktree, with `.agent-factory` excluded. Its execution context records
  local-only `factory` as both `baseRef` and `targetBranch`.

Use `workspace-direct` when the Human requests an ordinary Work Unit without
also selecting worktree or Specification-only execution. Never silently choose
worktree.

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
Independent Review is a separate explicit route. When selected, execution
context contains both `targetReviewRole` and `reviewExecution`; providing only
one field is invalid. Its result must be the independent Review Agent's
structured evidence. Without that selected route, review transition relies on
execution, quality, report, and Human review evidence and does not require an
`ai-review-result`.

The Human chooses:

- `rework`, recorded through `rework-start`;
- `complete`, recorded through
  `transition <package> done --review-decision complete`.

This is not an approval gate. Integration receipts contain no
`humanDecision`. Completion of `worktree` mode triggers integration into local
`factory` in the main lifecycle; `workspace-direct` and
`specification-direct` have no integration.
Pushing `factory`, merging it into `dev`, `main`, `master`, or another real
branch, and creating a PR are separate promotion operations that require an
explicit Human request.

Completed outcome records are immutable. Completed clean worktrees are removed
later through batch cleanup.

## Work Packages

Use `scripts/work_package.py` for every canonical
`.agent-factory/work-packages/<package-id>` operation. Never edit Work Package
JSON directly. A package owns its positive `maxParallel`, DAG nodes and
prerequisites, repository and target/integration branches, durable lease and
events, node idempotency keys, package review, member traceability, rework
impact, and single integration receipt.

Every package has finite recovery limits. `executionPolicy.maxRecoveryAttempts`
and `executionPolicy.maxSupervisorRestarts` may explicitly set positive limits;
when omitted, the executor and supervisor use finite built-in defaults.
Exhaustion returns a terminal error to the Main Agent.

Run `preflight` before execution. It full-validates every member, repository
identity, readiness, execution mode, graph references and cycles, and
branch/worktree collisions without mutation. `execution-start` converts a
successful preflight into the ACK-bound running state. Use `state-put` for
scheduler state, `review-put` for the package AI/Human review handoff,
`rework-start` for affected nodes and descendants, and `complete` for the one
target integration receipt.
`review-put` accepts only explicit `result: pass` and `checklistResult: pass`
evidence derived from every member Work Unit. It never manufactures a passing
review, and a failed member review cannot be marked completed or merged.

The lifecycle is `draft -> ready -> working <-> recovering -> review -> done`.
After ACK it never uses terminal `blocked` or `failed`.

## Required output

When creating Work Units, include:

`생성한 Work Unit 이름`

followed by a code block containing only one id per line.
