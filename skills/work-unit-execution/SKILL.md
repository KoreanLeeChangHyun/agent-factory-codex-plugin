---
name: work-unit-execution
description: Prepare, inspect, Human-approved integrate, and explicitly clean up dedicated Git branches and linked worktrees for Agent Factory named Work Unit Goal execution. Use when an Execution Agent must resolve a Work Unit execution context, create a collision-safe locked worktree, inspect clean or dirty state, produce integration receipts, or perform Human-approved non-force cleanup.
---

# Work Unit Execution

Use this skill as the canonical Git worktree boundary for Agent Factory Work
Unit Execution. Keep Work Unit planning and Git mutation separate.

## Required Inputs

Resolve all values from the Work Unit execution contract or an explicit Human
decision before running a command:

- canonical repository root
- base ref for `prepare`
- Work Unit id; derive the dedicated branch as `work-unit/<work-unit-id>`
- canonical linked worktree path, derived as
  `<repository>/.agent-factory/worktree/<work-unit-id>`
- target branch and explicit Human decision for `integrate`

An execution context may also provide `--branch`; accept it only when it exactly
matches the derived branch. `--path` is an optional assertion for the canonical
path and an explicit compatibility input for an already registered legacy
worktree. Never create a new worktree outside the canonical root. Do not invent
repository roots or base refs. Ask the Human when a required value is absent or
ambiguous.

Read `references/worktree-contract.md` before invoking the script or consuming
its JSON result.

## Execution Workflow

1. Resolve and read the complete named Work Unit package.
2. Confirm that execution is running in either a named Goal session or a fresh
   `codex exec` session, with the Work Unit identity and execution context
   explicitly resolved. Persistent Goal mode is not required for the
   `codex exec` route.
3. Resolve the repository, base ref, and Work Unit id. Derive the branch as
   `work-unit/<work-unit-id>` and the worktree path as
   `<repository>/.agent-factory/worktree/<work-unit-id>`.
4. Run `scripts/worktree.py prepare` before editing when the linked worktree
   does not exist.
5. Perform all scoped edits and verification inside the returned
   `context.worktreePath`.
6. Run `scripts/worktree.py inspect` before reporting or asking for Human
   review.
7. Validate every recorded execution command against the installed CLI parser
   before treating the execution context as ready. Record the exact command
   that passed, not a reconstructed equivalent. For Codex, global options such
   as `--ask-for-approval` precede the `exec` subcommand:
   `codex --ask-for-approval <policy> exec --sandbox <mode> -C <worktree> <prompt>`.
8. Update execution, review, report, and Human-review sections before the final
   inspect capture. Then run `inspect`, register its exact result, and run it
   once more to verify that the reported changed-path set is still current.
   Evidence registration may only change already-reported evidence/index paths;
   record that bounded registration delta explicitly when content hashes cannot
   be a fixed point.
9. Record the exact command and canonical JSON result in the Work Unit
   execution evidence. Treat a nonzero exit code or `ok: false` as refusal, not
   as permission to bypass validation.
10. After a Human merge decision, run `integrate` with the approved target and,
   for diverged branches, the explicit `--strategy no-ff`. Register the raw
   JSON through the Work Unit manager's `integration-put`; rerun `integrate`
   to recover an interrupted registration as `already-merged` without a second
   merge.
11. Run `cleanup` only after an explicit Human cleanup decision. Preserve the
   dedicated branch for Human merge, rework, or later disposal decisions.

## Commands

Use argument arrays when invoking the script. Never interpolate untrusted
values through a shell.

```text
python3 scripts/worktree.py prepare \
  --repository <absolute-repository-root> \
  --work-unit-id <work-unit-id> \
  --base <commit-ish>

python3 scripts/worktree.py inspect \
  --repository <absolute-repository-root> \
  --work-unit-id <work-unit-id>

python3 scripts/worktree.py integrate \
  --repository <absolute-repository-root> \
  --work-unit-id <work-unit-id> \
  --target-branch <target-branch> \
  --human-decision approved \
  [--strategy no-ff]

python3 scripts/worktree.py cleanup \
  --repository <absolute-repository-root> \
  --work-unit-id <work-unit-id> \
  --human-decision approved
```

Pass `--path <recorded-legacy-worktree-path>` only to reuse, inspect, integrate,
or clean up a worktree that Git already registers outside the canonical root.

## Safety Boundary

- Validate the repository root, base commit, branch name, registered
  worktrees, filesystem path, branch ownership, repository ownership, and dirty
  state before the relevant mutation.
- Create with `git worktree add --lock ... -b`; do not reset an existing branch.
- Create new linked worktrees only under the canonical repository-local root.
  The target repository must ignore `/.agent-factory/worktree/` so nested
  worktrees do not dirty the primary worktree.
- Reuse the same registered branch and worktree pair when the same Work Unit is
  executed again or sent to rework. Do not create another pair.
- Preserve explicitly recorded registered legacy worktrees for rework and
  Human-approved cleanup; do not migrate or relocate them implicitly.
- Inspect with stable porcelain and NUL-delimited Git output.
- Refuse collisions, repository or branch mismatch, unresolved targets, dirty
  source or target worktrees, missing Human approval, and invalid strategies
  before integration mutation.
- Classify source and target as `fast-forwardable`, `diverged`, or
  `already-merged`. Use `ff-only` for the first, require explicit `no-ff` for
  the second, and perform no Git mutation for the third.
- Never use forced worktree removal, forced branch deletion, `-B`, or shell
  interpolation.
- Cleanup unlocks and removes only a clean approved linked worktree without
  force. It retains the branch.
- Leave the integration decision and strategy approval, rework, branch
  deletion, Work Unit approval, and PR promotion to the Human. The command only
  executes an explicitly approved integration decision.

## Responsibility Boundary

- `work-unit-planner` defines and validates required execution-context data;
  it does not run Git mutation.
- `lifecycle` routes named Work Unit Goal Execution through
  this skill.
- Execution Agents and Agent extensions call the same script contract and
  record its result instead of implementing separate Git orchestration.

## Reporting

Record the Work Unit id, resolved repository, base commit, source and target
branches, source and target-before/after commits, worktree path, Human decision,
relationship, strategy, operation result, lock state, dirty state, Git mutation
operations, refusal error, and lifecycle state from the JSON result. Do not
translate or rewrite machine-facing values.
