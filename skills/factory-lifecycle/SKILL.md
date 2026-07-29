---
name: factory-lifecycle
description: Route Agent Factory work through canonical Intake, Work Unit planning, background Goal execution, Human review, integration or rework, and later batch cleanup.
---

# Agent Factory Lifecycle

Use the opened primary workspace as `<project-root>`. Canonical lifecycle data
lives only under `<project-root>/.agent-factory/`.
Always start with `intakes`; there is no separate initialization phase.

```text
Conversation -> Intake -> Work Unit -> background Goal + Exec
             -> Human review (rework | complete)
             -> complete integration -> later batch cleanup
```

## Mandatory Manager Script Gate

Every canonical operation uses its owning manager:

- Intake: `intakes/scripts/intake.py`
- Specification: `specifications/scripts/specification.py`
- Work Unit: `work-unit-manager/assets/scripts/work_unit.py`

Never create, update, delete, copy, move, or repair canonical JSON through
`apply_patch`, shell redirection, ad hoc scripts, generic filesystem tools, or a
linked worktree. If the owning manager cannot express an operation, stop and
report that capability gap. Treat each manager as a hard precondition: stop
before mutation, do not create an exception path, and do not fall back to direct
JSON editing.

Conversation is recorded in the active Intake by default. When the Intake is
sufficient or the Human asks for a Work Unit, create the minimum independently
executable Work Unit from a full-valid ready Intake.
Use `intakes` for every Intake package and every canonical Intake mutation.
Use `intake-research` when Intake evidence requires direct observation of users
or operators.

Canonical `intakes`, `specifications`, and `work-units` remain tracked in the
primary repository. CRUD never creates a worktree and always resolves back to
the primary root, even when a manager is invoked from a linked worktree.

## Execution admission

Only an explicit Human request to execute a named Work Unit starts execution.
The primary `agent-main` makes one sufficiency decision immediately before
launch:

- full-valid Intake and Work Unit;
- no unresolved blocking item;
- complete scope, exclusions, outputs, verification, and execution context;
- matching repository and Work Unit id;
- explicit `executionMode`.

There are no artifact commits, immutable snapshot hashes, checkpoints, or
approval procedures. Do not ask again about decisions recorded in canonical
artifacts.

After admission, the main agent starts
`work-unit-execution/scripts/app_server_goal.py` as a background process. The
launcher establishes the Goal and explicitly tells the started agent that it is
the Workflow Agent and must execute the Work Unit.

This launcher is the Goal preflight. It confirms `thread/goal/set` and
`thread/goal/get` before `turn/start` and fails closed before worktree
preparation when Goal evidence is inconsistent.

## Execution routes

`executionMode: specification-direct`:

- no Git worktree or execution branch is created;
- the Workflow Agent updates the primary canonical Specification only through
  `specification.py`;
- no merge or worktree cleanup follows.

`executionMode: worktree` (or omitted legacy mode):

- branch is `work-unit/<work-unit-id>`;
- path is `<project-root>/.agent-factory/worktree/<work-unit-id>`;
- sparse checkout excludes the entire `.agent-factory`;
- implementation and non-canonical verification run in that worktree;
- canonical manager writes still route to the primary root.

Execution runs `Plan -> Work -> AI Review -> Report`. Once started, the
Workflow Agent does not repeat admission, request approval, or reconstruct a
checkpoint. The launcher automatically continues interrupted turns and
reactivates Goals blocked by removed workflow gates. A genuine unrecoverable
error becomes an explicit failed receipt, never an indefinitely waiting blocked
process.

Execution state records revision, attempt, invocation chain, and idempotent
step records. It does not bind state to Git commits or immutable hashes.

## Human review

After execution, show the result and evidence to the Human. This is a review
decision, not an approval procedure:

- `rework`: record the exact instruction with `rework-start` and run the same
  background Goal + Exec path again.
- `complete`: record `transition ... done --review-decision complete`.

For `worktree` mode, `complete` automatically integrates the source branch into
the recorded target. Target dirtiness ignores primary `.agent-factory/**`
changes. Keep the completed worktree after merge and clean completed clean
worktrees later in a batch. For `specification-direct`, completion has no Git
integration or cleanup.

Push, deployment, branch deletion, and PR promotion occur only on a separate
explicit Human request.

## Skill routing

- `factory-rule` before edits, design, code, review, or workflow claims.
- `intakes` for canonical Intake.
- `intake-analysis`, `intake-web-search`, and `intake-research` for evidence collected into
  Intake.
- `specifications` for canonical Specification.
- `work-unit-manager` for Work Unit creation and state.
- `work-unit-execution` for Goal launcher and Git worktree operations.
- `agent-workflow` for launched execution.
