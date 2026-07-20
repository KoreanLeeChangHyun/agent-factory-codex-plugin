# Worktree Command Contract

## Purpose

`scripts/worktree.py` is the deterministic command boundary for Agent Factory
linked worktree mutation and inspection. Each invocation writes exactly one
JSON document to stdout and returns `0` only when `ok` is `true`.

## Input Contract

All commands require explicitly resolved values:

| Argument | Commands | Contract |
| --- | --- | --- |
| `--repository` | all | Absolute canonical Git repository root. |
| `--work-unit-id` | all | Work Unit id used to derive `work-unit/<work-unit-id>`. |
| `--base` | `prepare` | Commit-ish that resolves to one commit. |
| `--branch` | all | Optional resolved branch assertion; when present it must equal the derived branch. |
| `--path` | all | Optional absolute path assertion. Omit it for the canonical `<repository>/.agent-factory/worktree/<work-unit-id>` path. A noncanonical value is accepted only for an already registered legacy worktree. |
| `--target-branch` | `integrate` | Local target branch checked out in exactly one clean registered worktree. |
| `--strategy no-ff` | `integrate` | Required only when source and target are diverged. |
| `--human-decision approved` | `integrate`, `cleanup` | Explicit Human authorization for the requested mutation. |

New worktrees always use the repository-local canonical path. The repository
must ignore `/.agent-factory/worktree/`. Existing registered external
worktrees remain addressable through their explicitly recorded `--path` for
reuse, inspection, and Human-approved cleanup.

## Output Contract

Every response uses schema version `1.0.0` and these top-level fields:

```json
{
  "command": "prepare",
  "context": {},
  "error": null,
  "ok": true,
  "operations": [],
  "schemaVersion": "1.0.0",
  "state": "prepared"
}
```

- `context` contains resolved execution state on success and is `null` on
  refusal.
- `error` contains `code`, `message`, and `details` on refusal and is `null` on
  success.
- `operations` records mutation commands as argument arrays with return code,
  stdout, and stderr. Validation-only commands are not duplicated into the
  mutation ledger.
- `state` is `prepared`, `reused`, `clean`, `dirty`, `integrated`,
  `already-merged`, `cleaned`, or `refused`.

`prepare` context includes `workUnitId`, `repository`, `baseRef`, `baseCommit`, `branch`,
`worktreePath`, `headCommit`, `locked`, `lockReason`, `dirty`, and `changes`.
`inspect` reports the same current-state fields except `baseRef` and
`baseCommit`. `integrate` reports `workUnitId`, `repository`, `sourceBranch`,
`targetBranch`, `worktreePath`, `humanDecision`, `sourceCommit`,
`targetBeforeCommit`, `targetAfterCommit`, `relationship`, `strategy`, and
`operationResult`. `cleanup` also reports `humanDecision`, `worktreeRemoved`,
and `branchRetained`.

`headCommit` is the Git subject input to the Work Unit manager's versioned
execution state. Inspect immediately before `execution-init` and each new
`attempt-start`. A Codex session resume stays in the current attempt and does
not consume a new worktree prepare result; append its session id through
`attempt-resume`. Human-approved rework reuses the registered worktree but
starts a new revision through `rework-start` before its first new attempt.

`integrate` classifies ancestry before mutation. `fast-forwardable` uses
`ff-only`; `diverged` requires explicit `--strategy no-ff`; `already-merged`
returns success without a mutation operation and preserves an explicitly
supplied `no-ff` strategy. This makes rerunning the same approved command after
a merge but before receipt registration recoverable without duplicate merging.

## Refusal Codes

The script performs no requested mutation when preflight validation returns:

- `path_not_absolute`
- `noncanonical_worktree_path`
- `invalid_repository`
- `repository_root_mismatch`
- `invalid_base_ref`
- `invalid_branch`
- `invalid_target_branch`
- `branch_derivation_mismatch`
- `branch_collision`
- `worktree_collision`
- `path_collision`
- `repository_mismatch`
- `worktree_not_registered`
- `branch_mismatch`
- `missing_human_decision`
- `dirty_worktree`
- `dirty_target_worktree`
- `unresolved_target`
- `target_worktree_unresolved`
- `diverged_strategy_required`
- `strategy_mismatch`

Git or I/O failures use a specific `*_failed` or `unexpected_io_error` code
and preserve the nonzero process exit status.
If a `no-ff` merge reports a conflict, `integrate` records the failed merge and
`git merge --abort` operations, returns `integration_failed`, and reports
whether the clean target state was restored.

## Lifecycle States

```text
unresolved
  -> prepare -> prepared and locked
  -> repeated prepare for the same Work Unit -> reused and locked
  -> inspect -> clean or dirty
  -> Human Review decision
  -> integrate approved -> integrated or already-merged, branch and worktree retained
  -> cleanup approved and clean -> cleaned, branch retained
```

Do not call `integrate` or `cleanup` automatically. Human approval of Work Unit
results, integration strategy, cleanup, branch deletion, and PR promotion
remain separate decisions.
