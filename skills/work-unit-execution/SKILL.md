---
name: work-unit-execution
description: Launch Goal-bound background Work Unit execution, manage code-only linked worktrees, integrate completed code work, and batch-clean completed worktrees.
---

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
- automatically continues a turn that ends as `interrupted`;
- reactivates a Goal that was blocked by a removed checkpoint or approval
  procedure;
- returns an explicit error after bounded recovery instead of leaving a live
  process waiting forever.

This is the Goal preflight: `thread/goal/set` and `thread/goal/get` must agree
before `turn/start`. On mismatch, fail closed before worktree preparation.

Once launched, do not repeat readiness, checkpoint, or approval decisions.

## Execution modes

`specification-direct`:

- never creates or prepares a worktree;
- updates the primary root `.agent-factory/specifications` package only through
  `specification.py`;
- has no Git integration or worktree cleanup.

`worktree` (and omitted legacy mode):

- derives branch `work-unit/<work-unit-id>`;
- derives path `<repository>/.agent-factory/worktree/<work-unit-id>`;
- creates it with no checkout, configures sparse checkout to exclude the entire
  `.agent-factory`, and then checks out source files;
- keeps canonical Intake, Specification, and Work Unit CRUD in the primary root.

## Worktree commands

```text
python3 scripts/worktree.py prepare \
  --repository <absolute-primary-root> \
  --work-unit-id <id> \
  --base <commit-ish>

python3 scripts/worktree.py inspect \
  --repository <absolute-primary-root> \
  --work-unit-id <id>

python3 scripts/worktree.py integrate \
  --repository <absolute-primary-root> \
  --work-unit-id <id> \
  --target-branch <branch> \
  [--strategy no-ff]

python3 scripts/worktree.py cleanup \
  --repository <absolute-primary-root> \
  --work-unit-id <id>

python3 scripts/worktree.py cleanup-completed \
  --repository <absolute-primary-root> \
  --work-unit-id <done-id> \
  [--work-unit-id <done-id> ...]
```

`prepare` uses the requested code base commit directly; it does not inspect or
create artifact checkpoints. `integrate` ignores primary
`.agent-factory/**` changes when checking target dirtiness, so canonical CRUD
does not block source integration. It still refuses dirty source code, dirty
non-canonical target files, repository/branch mismatches, and unresolved merge
strategies.

After the Human chooses `complete`, integrate `worktree` mode automatically and
register the receipt through `integration-put`. Do not clean the worktree
immediately. Batch cleanup later removes only clean completed worktrees without
force and retains branches. Push, deployment, branch deletion, and PR promotion
require separate explicit requests.

## Execution state

Execution state uses Work Unit revision, attempt, invocation chain, and
idempotent step records. It does not bind artifact state to Git hashes,
immutable snapshots, or checkpoints. `attempt-resume` appends the new Goal
thread id to the current attempt.
