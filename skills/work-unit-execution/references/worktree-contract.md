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
| `--path` | all | Absolute linked worktree path. No fallback is generated. |
| `--human-decision approved` | `cleanup` | Explicit Human authorization to clean up the worktree. |

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
- `state` is `prepared`, `reused`, `clean`, `dirty`, `cleaned`, or `refused`.

`prepare` context includes `workUnitId`, `repository`, `baseRef`, `baseCommit`, `branch`,
`worktreePath`, `headCommit`, `locked`, `lockReason`, `dirty`, and `changes`.
`inspect` reports the same current-state fields except `baseRef` and
`baseCommit`. `cleanup` also reports `humanDecision`, `worktreeRemoved`, and
`branchRetained`.

## Refusal Codes

The script performs no requested mutation when preflight validation returns:

- `path_not_absolute`
- `invalid_repository`
- `repository_root_mismatch`
- `invalid_base_ref`
- `invalid_branch`
- `branch_derivation_mismatch`
- `branch_collision`
- `worktree_collision`
- `path_collision`
- `repository_mismatch`
- `worktree_not_registered`
- `branch_mismatch`
- `missing_human_decision`
- `dirty_worktree`

Git or I/O failures use a specific `*_failed` or `unexpected_io_error` code
and preserve the nonzero process exit status.

## Lifecycle States

```text
unresolved
  -> prepare -> prepared and locked
  -> repeated prepare for the same Work Unit -> reused and locked
  -> inspect -> clean or dirty
  -> Human Review decision
  -> cleanup approved and clean -> cleaned, branch retained
```

Do not call `cleanup` automatically. Human approval of Work Unit results,
merge, branch deletion, and PR promotion remain separate decisions.
