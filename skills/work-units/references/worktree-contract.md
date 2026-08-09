# Worktree Contract

This contract applies only to Work Units whose explicit `executionMode` is
`worktree`. `specification-direct` Work Units must not invoke this script.

## Identity

- Repository is the absolute primary Git root.
- Execution base and automatic integration target are local-only `factory`.
- Branch is `work-unit/<work-unit-id>`.
- New linked worktree path is
  `<repository>/.agent-factory/worktree/<work-unit-id>`.
- Repository ignore rules include only the runtime worktree root
  `/.agent-factory/worktree/`; canonical artifacts remain tracked in primary
  Git.

## Factory initialization

`factory-init --repository <absolute-primary-root>` creates the local
`factory` branch at the current `HEAD` only when that local branch is absent.
It does not change the current checkout or any remote. When `factory` already
exists, it reports the resolved existing commit without Git mutation.

## Prepare

Standalone `prepare` full-validates the canonical Work Unit once before its first Git
mutation and resolves the current local `factory` commit. `--base` defaults to
`factory` and refuses every other value for fresh execution. It does not require
an artifact commit, snapshot, hash, or checkpoint.

New worktrees use:

```text
git worktree add --no-checkout --lock ...
git sparse-checkout set --no-cone /* !/.agent-factory/
git checkout <derived-branch>
```

The resulting linked worktree must not contain `.agent-factory`.

Work Package member worktrees instead start from the package's local
`work-package/<package-id>` integration branch so completed prerequisites are
visible. The package target remains local `factory`; member execution cannot
select or promote to another target.

## Inspect and integration

Source status is exact porcelain output from the linked worktree. Target dirty
checks exclude `.agent-factory/**` because canonical package CRUD occurs in the
primary root and must not block source integration. All other target changes
still block integration.

Ancestry determines the strategy:

- `fast-forwardable`: `--ff-only`
- `diverged`: explicit `--strategy no-ff`
- `already-merged`: success without another mutation

No approval argument exists. The main lifecycle invokes integration only after
the Human chooses `complete`. `--target-branch` defaults to `factory` and
refuses every other value. If `factory` is not checked out, integration uses a
temporary detached worktree, advances `refs/heads/factory` with an expected-old
update, and removes only that temporary target worktree.

## Cleanup

Cleanup has no approval argument. Batch cleanup is invoked after completion,
not inline with integration. It refuses dirty worktrees, never forces removal,
and retains the branch. `cleanup-completed` preflights every named Work Unit as
`done` and every registered worktree as clean before it removes any target.
Specification-only and already-cleaned targets are non-mutating results.

## Receipts

Receipts do not contain `humanDecision`. They record repository, Work Unit id,
source/target branches and commits, worktree path, relationship, strategy,
operation result, operations, and final state.
Temporary-target receipts include worktree add, merge, atomic local ref update,
and temporary worktree removal operations.

## Refusal

Refuse invalid paths, repository or branch mismatch, collisions, unresolved
bases or targets, dirty source code, dirty non-canonical target files, invalid
strategy, and Git/I/O failures. A refusal is an explicit terminal result; do
not leave an execution Goal waiting in `blocked`.
