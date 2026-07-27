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
2. Run the Goal preflight before worktree preparation or any other execution
   work. Inspect the current Goal and require its unfinished objective to target
   the same Work Unit. If no Goal exists, create one from the explicit Human
   Work Unit execution request. If Goal inspection or creation is unavailable
   or fails, or another unfinished Goal conflicts, fail closed. A fresh
   `codex exec` process or prompt is only a bootstrap and is not proof of an
   active Goal.
   Programmatic callers and the primary `main-agent` use
   `scripts/app_server_goal.py`. It performs the
   app-server `initialize` handshake, starts a thread, sets and reads back the
   matching Goal through `thread/goal/set` and `thread/goal/get`, requires the
   matching `thread/goal/updated` notification, and sends `turn/start` only
   after all three Goal results agree on thread, objective, and active status.
   The started turn explicitly invokes `$workflow-agent`.
   Do not substitute a model-authored receipt or private Codex SQLite state for
   this protocol evidence.
3. Resolve the repository, base ref, and Work Unit id. Derive the branch as
   `work-unit/<work-unit-id>` and the worktree path as
   `<repository>/.agent-factory/worktree/<work-unit-id>`.
4. Reconstruct the second lifecycle checkpoint with
   `lifecycle/assets/scripts/artifact_handoff.py inspect` and use its exact
   Work Unit checkpoint commit as `--base`. Keep the execution context's
   symbolic `baseRef` unchanged; admission uses it to find the latest reachable
   package checkpoint and compares that commit to the requested exact base.
5. Run `scripts/worktree.py prepare` before editing when the linked worktree
   does not exist.
   `prepare` invokes the Work Unit manager's full-ready admission contract for
   the same id, repository, base, branch, and path before any branch or
   worktree mutation; direct invocation cannot bypass admission.
6. Perform all scoped edits and verification inside the returned
   `context.worktreePath`.
7. Before the first active attempt, pass the inspected `headCommit` to the Work
   Unit manager's `execution-init`, then start the attempt with a unique Codex
   execution invocation id and the same inspected head. A same-revision retry
   uses a new `attempt-start`; `codex exec resume` uses `attempt-resume` and
   does not prepare another worktree or increment the attempt.
   The Work Unit manager independently resolves the prepared worktree `HEAD`
   and refuses a mismatched recorded digest.
8. During the active attempt, use the Work Unit manager's durable progress,
   bounded failure, and blocker-resolution commands. Resume preserves the same
   revision and attempt and must not replay a completed non-idempotent step.
9. Run `scripts/worktree.py inspect` before reporting or asking for Human
   review.
10. Validate every recorded execution command against the installed CLI parser
   before treating the execution context as ready. Record the exact command
   that passed, not a reconstructed equivalent. For Codex, global options such
   as `--ask-for-approval` precede the `exec` subcommand:
   `codex --ask-for-approval <policy> exec --sandbox <mode> -C <worktree> <prompt>`.
11. Update execution, review, report, and Human-review sections before the final
   inspect capture. Then run `inspect`, register its exact result, and run it
   once more to verify that the reported changed-path set is still current.
   Evidence registration may only change already-reported evidence/index paths;
   record that bounded registration delta explicitly when content hashes cannot
   be a fixed point.
12. Record the exact command and canonical JSON result in the Work Unit
   execution evidence. Treat a nonzero exit code or `ok: false` as refusal, not
   as permission to bypass validation.
13. After a Human merge decision, run `integrate` with the approved target and,
   for diverged branches, the explicit `--strategy no-ff`. Register the raw
   JSON through the Work Unit manager's `integration-put`; rerun `integrate`
   to recover an interrupted registration as `already-merged` without a second
   merge.
14. Run `cleanup` only after an explicit Human cleanup decision. Preserve the
   dedicated branch for Human merge, rework, or later disposal decisions.

## Commands

Use argument arrays when invoking the script. Never interpolate untrusted
values through a shell.

```text
python3 scripts/app_server_goal.py \
  --repository <absolute-repository-root> \
  --work-unit-id <work-unit-id> \
  [--timeout-seconds <positive-seconds>]

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
- The app-server launcher performs only read-only Work Unit validation before
  Goal confirmation. It admits a fully valid `ready` initial execution or the
  manager-owned `working` + `planned` state produced by Human-approved Rework.
  Planned Rework must carry the exact manager-owned Human instruction, which
  the launcher includes in the workflow-agent turn. It refuses other lifecycle
  or attempt states, missing Rework instructions, RPC errors, a missing or
  mismatched Goal, invalid JSON, EOF, timeout, and non-completed execution turns,
  and always closes the child process and its pipes.
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
- Programmatic callers and Agent extensions use `app_server_goal.py` for Goal
  admission and execution startup. The primary `main-agent` delegates through
  that launcher, and the launched `workflow-agent` uses `worktree.py` for Git
  orchestration after its Goal preflight. Callers record both script results
  instead of implementing either boundary again.

## Reporting

Record the Work Unit id, resolved repository, base commit, source and target
branches, source and target-before/after commits, worktree path, Human decision,
relationship, strategy, operation result, lock state, dirty state, Git mutation
operations, refusal error, and lifecycle state from the JSON result. Do not
translate or rewrite machine-facing values.

For programmatic launch, also record the app-server thread id, Goal objective
and terminal status, turn ids, ordered protocol operations, child-process
result, refusal error, and launcher state from its JSON result.
