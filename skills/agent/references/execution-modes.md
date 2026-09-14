# Execution modes

## Captured routes

| Mode | Implementation | Completion |
| --- | --- | --- |
| `direct` | Main directly | Appropriate Main checks |
| `work` (new Main default) | Managed Work | Completed Work receipt, appropriate Main checks; separate Verification not requested |
| `work-verification` | Managed Work | Separate Verification pass or evidenced Human skip |
| `plan-work-verification` | Actual Plan then default execution in the same Work thread | Separate Verification pass or evidenced Human skip |

Conversation and Human Interview always remain Main. Selecting a mode does not
satisfy the independent Human approval gate or expand execution permissions.
The selector applies to the next submitted message. Queued messages retain their
submission snapshot; changing the selector cannot redirect accepted/running work.
Main preserves an active task's route when handling conversational steering.

## Runtime interface

- `exec.py submit/send --task-mode MODE` snapshots the route. New Main requests
  without a flag capture `work`; historical runs with no mode retain
  `work-verification`. Explicit flags participate in the immutable dispatch tuple.
- Main performs `direct` work itself; do not create a direct-mode loop.
- `loop.py start --task-mode work --work-agent ID --request-file PATH` needs no
  Verification identity. Its completed Work receipt ends the loop with terminal
  reason `work-completed`. Main then performs appropriate checks and integrates.
- Verification modes additionally require `--verification-agent ID`. Failure
  revises the same Work session, then reuses the same Verification session and
  binds its receipt to the new exact Work run. No planning role or extra Agent exists.
- The low-level loop CLI's omitted flag retains `work-verification` for existing
  callers. Persisted loops without the field retain that same historical route.
  New Main uses its captured mode explicitly when starting a loop.
- `capabilities` version 0.1.0 adds `submit/send.taskModes`. Clients require the
  selected mode in that list before dispatch; absence is unsupported, never an
  invitation to inject prose or silently choose another route. Existing fields
  and receipt schema versions remain compatible.

## Actual Plan transition

Plan support is advertised only when the installed Codex experimental schema
contains `turn/start.collaborationMode`, Plan/default kinds and
`collaborationMode/list`. At execution time the adapter also requires both modes
from the live catalog. Missing support fails closed before a model turn.

A Work run starts/resumes one exact thread with a `plan` collaboration turn and a
planning output schema. It preserves the plan in that run's `plan.json`, checks
cancellation, then issues `turn/start` with `default` collaboration mode and the
original result/receipt schema on that same thread. Model, reasoning, execution
permissions and approval policy are retained. No transition click is required.
A required unresolved Human decision stops at `needs-human-decision`; failure or
interruption cannot start implementation or Verification. Native interactive
requests remain subject to the managed transport's existing input boundary.
Only the implementation result can complete Work and enable Verification.

## Reports and authority

Use `not requested` for separate Verification in direct/work modes, not `pass` or
Human skip. Report Main's own checks separately. Work never self-verifies or
commits. Permission, approval, publication and destructive-action authority remain
independent of mode. Mode selection alone sends no messages to external services.
