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
- Work Unit: `work-units/scripts/work_unit.py`

Never create, update, delete, copy, move, or repair canonical JSON through
`apply_patch`, shell redirection, ad hoc scripts, generic filesystem tools, or a
linked worktree. If the owning manager cannot express an operation, stop and
report that capability gap. Treat each manager as a hard precondition: stop
before mutation, do not create an exception path, and do not fall back to direct
JSON editing.

Conversation is recorded in the active Intake by default. When the Intake is
sufficient or the Human asks for a Work Unit, create the minimum independently
executable Work Unit from a full-valid ready Intake.
The Main Agent may delegate internal, web, document, runtime, or authorized
user research to an Intake Agent through the `intakes`-owned `codex exec`
launcher. The Intake Agent returns a compact result to the Main Agent, uses
`intake.py` for canonical writes, and never owns readiness or Human decisions.
Use `intakes` for every Intake package and every canonical Intake mutation.
Use `intakes` when Intake evidence requires direct observation of users
or operators.

Canonical `intakes`, `specifications`, and `work-units` remain tracked in the
primary repository. CRUD never creates a worktree and always resolves back to
the primary root, even when a manager is invoked from a linked worktree.

## Execution admission

Only an explicit Human request to execute a named Work Unit starts execution.
The primary `agents` makes one sufficiency decision immediately before
launch:

- full-valid Intake and Work Unit;
- no unresolved blocking item;
- complete scope, exclusions, outputs, verification, and execution context;
- matching repository and Work Unit id;
- explicit `executionMode`.

There are no artifact commits, immutable snapshot hashes, checkpoints, or
approval procedures. Do not ask again about decisions recorded in canonical
artifacts.

Verification criteria describe what to run if the Human explicitly requests
it; they do not authorize test execution. Admission records the exact
Human-requested tests, if any. Without such a request, execution runs no tests,
including smoke checks, lint, type checks, or build verification, and reports
that fact for Human review.

After admission, the main agent starts
`work-units/scripts/app_server_goal.py` as a background process. The
launcher establishes the Goal and explicitly tells the started agent that it is
the Workflow Agent and must execute the Work Unit.

This launcher is the Goal preflight. It confirms `thread/goal/set` and
`thread/goal/get` before `turn/start` and fails closed before worktree
preparation when Goal evidence is inconsistent.
After a valid initial `turn/start`, it emits one immediate JSONL ACK and keeps
running until it emits the final execution document. Admission refusal before
the initial turn emits no ACK.

## Execution routes

`executionMode: specification-direct`:

- no Git worktree or execution branch is created;
- the Workflow Agent updates the primary canonical Specification only through
  `specification.py`;
- no merge or worktree cleanup follows.

`executionMode: worktree`:

- base is the current commit of local `factory`;
- branch is `work-unit/<work-unit-id>`;
- path is `<project-root>/.agent-factory/worktree/<work-unit-id>`;
- sparse checkout excludes the entire `.agent-factory`;
- implementation and any Human-explicit non-canonical verification run in that
  worktree;
- canonical manager writes still route to the primary root.
- complete integration target is local `factory`.

Execution runs `Plan -> implementation Work -> optional Test Agent -> mandatory
Documentation Agent -> mandatory independent Review Agent -> Report`. The
Workflow Agent owns only Plan and implementation Work. The launcher skips the
Test Agent and records `tests not run` unless exact Human-authorized commands
exist, always starts the Documentation Agent in a separate background Goal, and
then starts the Review Agent in another Goal. The Review Agent performs static
review only: it modifies no files and runs no verification commands. Each role
has an independent Goal, ACK/result evidence, and terminal failure in the
launcher receipt. Once started, no role repeats admission, requests approval,
or reconstructs a checkpoint.

Execution state records revision, attempt, invocation chain, and idempotent
step records. It does not bind state to Git commits or immutable hashes.

## Human review

After execution, show the result and evidence to the Human. This is a review
decision, not an approval procedure:

- `rework`: record the exact instruction with `rework-start` and run the same
  background Goal + Exec path again.
- `complete`: record `transition ... done --review-decision complete`.

For `worktree` mode, `complete` automatically integrates the source branch into
local `factory`. Target dirtiness ignores primary `.agent-factory/**`
changes. Keep the completed worktree after merge and clean completed clean
worktrees later in a batch. For `specification-direct`, completion has no Git
integration or cleanup.

The Work Unit lifecycle never pushes `factory`. Merging `factory` into `dev`,
`main`, `master`, or another real branch, PR creation, deployment, branch
deletion, and any push occur only on a separate explicit Human promotion
request.

## Skill routing

- `rules` before edits, design, code, review, or workflow claims.
- `intakes` for canonical Intake.
- `intakes/references/analysis.md` for internal evidence collected into Intake.
- `intakes/references/web-search.md` for external published evidence collected
  into Intake.
- `intakes/references/user-research.md` for direct user and operator evidence
  collected into Intake.
- `intakes/references/interview.md` for Human-only decisions recorded in Intake.
- `specifications` for canonical Specification.
- `work-units` for Work Unit creation and state.
- `work-units` for Goal launcher and Git worktree operations.
- `agents` for launched execution.
