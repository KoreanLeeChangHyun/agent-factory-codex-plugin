# Lifecycle Reference

## Flow

```text
Human conversation
  -> canonical Intake
  -> executable Work Unit
  -> one-time agents sufficiency decision
  -> background Goal + Exec
  -> Plan -> Work -> AI Review -> Report
  -> Human review: rework | complete
  -> complete integration
  -> later batch cleanup
```

Conversation and feedback are appended to Intake through `intake.py`. Intake,
Specification, and Work Unit CRUD always uses the primary root and never creates
a worktree. Canonical packages remain tracked in primary Git, but execution does
not create artifact commits, immutable snapshots, hashes, or checkpoints.
The Main Agent may delegate research to an Intake Agent through the
`intakes`-owned `codex exec` launcher. A new or explicitly selected resume
session is isolated behind a compact ACK and terminal result; the Main Agent
retains Human decisions and readiness, while `intake.py` remains the only
canonical writer.
Every Work Unit basis is traceable from the ready Intake through its package
root anchor. Specification impact may be recorded as not applicable.

Design Report is not a stored HTML, CSS, or JavaScript artifact. The external
viewer must not create canonical `report/`, `report/index.html`,
`report/styles.css`, or `report/script.js` files.

## Work Unit readiness

Before the launcher starts, `agents` checks once that:

- Intake and Work Unit are full-valid;
- no unresolved blocking item exists;
- scope, exclusions, output, test criteria, AI checklist, Human checklist, and
  report evidence requirements are complete;
- repository and Work Unit identity match;
- `executionMode` is explicit.

After launch, the Workflow Agent does not repeat this decision or ask for
approval. It follows recorded canonical decisions until execution completes.
Test criteria remain conditional plans: only tests explicitly requested by the
Human may run. Smoke checks, lint, type checks, build verification, and other
verification commands are included in this gate. If no test was explicitly
requested, the Workflow Agent runs none and records `tests not run` in the
result evidence.

## Background Goal + Exec

`app_server_goal.py` creates and verifies the Goal before `turn/start`. Its
prompt declares: `You are the Workflow Agent. You must execute this Work Unit.`
This Goal preflight uses `thread/goal/set` and `thread/goal/get` before worktree
preparation and fails closed on mismatched protocol evidence.
After the verified initial `turn/start`, the launcher emits one immediate JSONL
ACK and later emits its final execution document. A refusal before the initial
turn emits no ACK.

The launcher accepts initial, rework, and active-resume states. It automatically
continues interrupted turns and reactivates Goals blocked by removed workflow
gates. Recovery is bounded; a real unrecoverable error returns a failed receipt
instead of leaving a waiting process.

## Execution mode

`specification-direct` updates the primary canonical Specification through
`specification.py` and never creates a branch or worktree.

`worktree` creates or reuses the derived branch and canonical linked path. It
resolves the current local `factory` commit as its base and records local
`factory` as its complete integration target. Sparse checkout excludes all of
`.agent-factory`. Canonical manager calls made from that worktree still resolve
to the primary root.

Execution state is revision + attempt + invocation chain + idempotent step
records. It contains no Git subject or head hash.

## Review and completion

Human review has two outcomes:

- `rework`: exact instruction is stored and background Goal + Exec runs again.
- `complete`: `--review-decision complete` is stored.

For `worktree` mode, complete triggers integration into local `factory`
automatically. Primary
`.agent-factory/**` dirtiness is ignored during target source-code integration.
Completed worktrees remain until a later batch cleanup. Cleanup refuses dirty
worktrees and never forces removal.

`specification-direct` completion has no merge or cleanup.

The Work Unit lifecycle never pushes `factory`. Promotion from `factory` into
`dev`, `main`, `master`, or another real branch, PR creation, deployment,
branch deletion, and any push are separate explicit requests.
