# Work Unit Execution

Read `references/worktree-contract.md` before Git worktree operations.

## Launch

The primary agent performs one full-valid sufficiency decision immediately
before execution. Then run:

```text
python3 scripts/app_server_goal.py \
  --repository <absolute-primary-root> \
  --work-unit-id <work-unit-id>
```

The launcher:

- validates the canonical primary-root Work Unit;
- accepts `ready` initial execution, planned rework, or a manager-owned active
  attempt that must be resumed;
- creates and verifies the matching active Goal;
- starts a background turn whose prompt begins by declaring the Workflow Agent
  role and requiring execution;
- emits one immediate JSONL ACK after the verified initial `turn/start`;
- automatically continues a turn that ends as `interrupted`;
- reactivates a Goal that was blocked by a removed checkpoint or approval
  procedure;
- returns an explicit error after bounded recovery instead of leaving a live
  process waiting forever.

This is the Goal preflight: `thread/goal/set` and `thread/goal/get` must agree
before `turn/start`. On mismatch, fail closed before worktree preparation.
Admission refusal before a valid initial turn emits no ACK. After ACK, the
launcher keeps running and emits its existing final success or failure JSON
document when execution terminates.

Once launched, do not repeat readiness, checkpoint, or approval decisions.
For `worktree` execution, prepare or reuse the canonical linked worktree before
`execution-init` or `attempt-start`. A manager-owned active working or blocked
attempt may use recovery admission to prepare a missing worktree without
reopening the one-time readiness decision.

## Execution modes

`specification-direct`:

- never creates or prepares a worktree;
- updates the primary root `.agent-factory/specifications` package only through
  `specification.py`;
- has no Git integration or worktree cleanup.

`worktree` (and omitted legacy mode):

- resolves the current local `factory` commit as the execution base;
- derives branch `work-unit/<work-unit-id>`;
- derives path `<repository>/.agent-factory/worktree/<work-unit-id>`;
- creates it with no checkout, configures sparse checkout to exclude the entire
  `.agent-factory`, and then checks out source files;
- keeps canonical Intake, Specification, and Work Unit CRUD in the primary root.

## Worktree commands

```text
python3 scripts/worktree.py prepare \
  --repository <absolute-primary-root> \
  --work-unit-id <id>

python3 scripts/worktree.py inspect \
  --repository <absolute-primary-root> \
  --work-unit-id <id>

python3 scripts/worktree.py integrate \
  --repository <absolute-primary-root> \
  --work-unit-id <id> \
  [--strategy no-ff]

python3 scripts/worktree.py cleanup \
  --repository <absolute-primary-root> \
  --work-unit-id <id>

python3 scripts/worktree.py cleanup-completed \
  --repository <absolute-primary-root> \
  --work-unit-id <done-id> \
  [--work-unit-id <done-id> ...]
```

`prepare` resolves local `factory` at invocation time; explicit `--base` accepts
only `factory` for fresh execution. It does not inspect or create artifact
checkpoints. `integrate` targets only local `factory`; explicit
`--target-branch` accepts only `factory`. When `factory` is not checked out,
integration uses a temporary detached worktree and atomically advances the
local ref without displacing the Human's current checkout. `integrate` ignores primary
`.agent-factory/**` changes when checking target dirtiness, so canonical CRUD
does not block source integration. It still refuses dirty source code, dirty
non-canonical target files, repository/branch mismatches, and unresolved merge
strategies.

After the Human chooses `complete`, integrate `worktree` mode automatically into
local `factory` and register the receipt through `integration-put`. Do not clean
the Work Unit worktree immediately. Batch cleanup later removes only clean
completed worktrees without force and retains branches. The Work Unit lifecycle
never pushes `factory`; promotion from `factory` into `dev`, `main`, `master`,
or another real branch, PR creation, deployment, and branch deletion require a
separate explicit request.

## Execution state

Execution state uses Work Unit revision, attempt, invocation chain, and
idempotent step records. It does not bind artifact state to Git hashes,
immutable snapshots, or checkpoints. `attempt-resume` appends the new Goal
thread id to the current attempt.

## Work Package execution

Run a ready package through:

```text
python3 scripts/work_package_supervisor.py \
  --repository <absolute-primary-root> \
  --package-id <package-id>
```

The supervisor requires the executor's first JSONL event to be ACK, forwards
heartbeat and state events, and reinvokes the same package after ACK-bound
process death or heartbeat timeout. Admission refusal before ACK is
non-mutating and is not retried.

`work_package_exec.py` uses manager preflight, stable topological/id ready
selection, `maxParallel`, a sparse package integration worktree, stable merge
order, dependent-node bases from the integrated prerequisite result,
specification-direct serialization and full validation, durable leases and
idempotency keys, and `app_server_resolution_goal.py` recovery. It reaches one
package review only after every node, verification, and AI review pass.

After the Human chooses complete, run:

```text
python3 scripts/work_package_integrate.py \
  --repository <absolute-primary-root> \
  --package-id <package-id> \
  --review-decision complete
```

This integrates the package branch into the recorded target once and registers
the manager-owned receipt. Do not integrate before the Human decision.
