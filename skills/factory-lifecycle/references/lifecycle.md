# Lifecycle Reference

## Flow

```text
Human conversation
  -> canonical Intake
  -> executable Work Unit
  -> one-time agent-main sufficiency decision
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
Every Work Unit basis is traceable from the ready Intake through its package
root anchor. Specification impact may be recorded as not applicable.

Design Report is not a stored HTML, CSS, or JavaScript artifact. The external
viewer must not create canonical `report/`, `report/index.html`,
`report/styles.css`, or `report/script.js` files.

## Work Unit readiness

Before the launcher starts, `agent-main` checks once that:

- Intake and Work Unit are full-valid;
- no unresolved blocking item exists;
- scope, exclusions, output, test criteria, AI checklist, Human checklist, and
  report evidence requirements are complete;
- repository and Work Unit identity match;
- `executionMode` is explicit.

After launch, the Workflow Agent does not repeat this decision or ask for
approval. It follows recorded canonical decisions until execution completes.

## Background Goal + Exec

`app_server_goal.py` creates and verifies the Goal before `turn/start`. Its
prompt declares: `You are the Workflow Agent. You must execute this Work Unit.`
This Goal preflight uses `thread/goal/set` and `thread/goal/get` before worktree
preparation and fails closed on mismatched protocol evidence.

The launcher accepts initial, rework, and active-resume states. It automatically
continues interrupted turns and reactivates Goals blocked by removed workflow
gates. Recovery is bounded; a real unrecoverable error returns a failed receipt
instead of leaving a waiting process.

## Execution mode

`specification-direct` updates the primary canonical Specification through
`specification.py` and never creates a branch or worktree.

`worktree` creates or reuses the derived branch and canonical linked path.
Sparse checkout excludes all of `.agent-factory`. Canonical manager calls made
from that worktree still resolve to the primary root.

Execution state is revision + attempt + invocation chain + idempotent step
records. It contains no Git subject or head hash.

## Review and completion

Human review has two outcomes:

- `rework`: exact instruction is stored and background Goal + Exec runs again.
- `complete`: `--review-decision complete` is stored.

For `worktree` mode, complete triggers integration automatically. Primary
`.agent-factory/**` dirtiness is ignored during target source-code integration.
Completed worktrees remain until a later batch cleanup. Cleanup refuses dirty
worktrees and never forces removal.

`specification-direct` completion has no merge or cleanup.

Push, deployment, branch deletion, and PR promotion are separate explicit
requests.
