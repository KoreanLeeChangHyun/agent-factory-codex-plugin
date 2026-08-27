---
name: agent
description: Run Human-facing Main, bounded Work, independent Review, or resumable Inquiry Agents through the Agent Factory session runtime.
---

# Agent Factory Agent

## Entry contract

Use this skill for Agent Factory role behavior. Read the complete reference for
the active role before acting. Apply the common runtime contract to every Agent
and keep each Agent's unique responsibility in its own reference.

## Common runtime contract

### Topology

Use the Main Agent as the default Human conversation and orchestration agent.
Run it directly in Codex CLI by default or through `codex exec` when a VS Code
extension hosts the conversation.

Start every other Agent through `codex exec`. Preserve its exact Codex session
identifier so the Main Agent or Human-facing extension can resume the same
conversation later. Do not use platform Sub-agents for this route because the
design requires addressable, resumable sessions.

Allow the Human to address an Exec Agent directly through the same session
control surface. Keep the Main Agent responsible for default coordination and
result integration; do not treat it as the exclusive possible sender.

### Session boundary

Store operational Agent sessions below
`<project-root>/.agent-factory/agent/`.

Keep runtime state separate from Skills, project facts, Specifications, and
other canonical artifacts. Use one stable Agent identifier to locate its
session metadata and run state. Do not introduce a central `index.json` unless
a later requirement proves that per-Agent discovery is insufficient.

Use `scripts/agent_exec.py` to own the per-Agent directory schema. It records
the Agent and Codex session identifiers in `session.json` and stores each
request, state, heartbeat, event stream, response schema, and result below a
separate `runs/<run-id>/` directory.

### File handoff

Write request bodies and large context to files under the selected session run.
Pass only a compact control envelope to `codex exec`: Agent identifier, run
identifier, attempt, and validated request and result paths. Return detailed
results through the declared result path rather than embedding them in the
terminal response.

Use paths anchored below the project session root. Reject traversal, symlinks,
and unexpected file types. Publish completed request, state, heartbeat, and
result files atomically.

This reduces Main Agent context duplication and transport tokens, but not the
Exec Agent's token cost when that Agent reads the file.

### Background execution

Submit Exec Agent turns asynchronously. Return a compact acceptance ACK to the
caller without waiting for `codex exec` to finish. Keep the Main Agent available
for Human conversation while separate Exec Agents run concurrently.

Run at most one active turn for a single Codex session. Queue additional Main
or Human messages for that session rather than starting concurrent resume
commands. Permit different Agent sessions to run concurrently.

Do not make the Main Agent follow a blocking event stream. Let the runtime
collect events and expose unread terminal results through a non-blocking inbox
or status query. A VS Code host may subscribe to events independently.

### Acknowledgement and liveness

Separate acceptance, startup, liveness, and completion signals:

- `accepted`: the runtime durably accepted the request;
- `started`: `codex exec` emitted a valid session or turn start;
- `heartbeat`: the supervising process still observes a live run;
- `completed`: the terminal state and result file were published.

Generate periodic heartbeat ACKs in the supervisor or worker process, not as
model-authored messages. A heartbeat proves process liveness only; it does not
prove semantic progress or correctness.

### Timeout and retry

Define distinct acceptance, startup, heartbeat, and total-turn timeouts. Keep
the runtime values configurable through the initial `submit` command. Let the
calling Main Agent or host enforce the acceptance timeout around `submit`; let
the background worker own startup and turn timeouts, and let `reconcile` apply
the recorded heartbeat timeout.

When an ACK expires, inspect the recorded state, process, session, and terminal
result before retrying. Reuse the same run identifier, increment the attempt,
and ensure the prior process cannot still write. Never use `resume --last` for
managed Agents; resume the exact recorded session identifier.

Make retries idempotent. Prevent simultaneous attempts with a per-session lock
and verify the request identity before execution. Do not automatically retry an
irreversible or externally visible action unless a later Human-approved policy
explicitly permits it.

### Runtime commands

Use `scripts/agent_exec.py` for the managed session lifecycle:

- `submit`: create an Agent session and asynchronously submit its first run;
- `send`: asynchronously submit a follow-up run to the same session;
- `status` and `result`: read one run without blocking on execution;
- `inbox`: list unread terminal results for the Main Agent or host;
- `list`: list managed Agent sessions;
- `cancel`: request cancellation of an active run;
- `reconcile`: inspect stale heartbeats and safely resubmit a dead worker.

Pass request content with `--request-file` by default. Use `--actor human` when
the Human addresses an Exec Agent directly. Do not invoke the private `_worker`
command outside the manager.

Use `scripts/agent_loop.py` when the Human requests a durable bounded Work ->
Review -> revision cycle. Its `start`, `status`, `cancel`, and `reconcile`
commands orchestrate exact managed sessions through `agent_exec.py`; they do
not launch Codex directly. Read `references/loop.md` before operating a loop.

## Reference routing

- `references/main.md`: Route Human requests through Work and independent Review Agents or a resumable Inquiry Agent.
- `references/work.md`: Implement one bounded change without running tests or verification.
- `references/review.md`: Review Work Agent changes statically and independently without editing files.
- `references/inquery.md`: Investigate uncertain questions through research, analysis, study, or experiments and return evidence-backed results.
- `references/loop.md`: Operate the finite Work/Review lifecycle and its machine stop conditions.

## Scripts and tests

`scripts/agent_exec.py` owns asynchronous `codex exec` launch, exact session
resume, file handoff, heartbeat, timeout, bounded pre-start retry, cancellation,
result inbox, and stale-worker reconciliation.

Completed Work and Review runs also publish a strictly validated `receipt.json`
beside `result.md`. The per-run state declares its exact path, binding, and
role-specific schema while the compact terminal response remains unchanged.
Callers must pass `--reviewed-work-run-id` for every Review run; orchestration
may also pin the shared original identity with `--receipt-request-hash`.

Work and Review Agents never run tests or verification commands. Testing is
Human-led and remains outside those role contracts.
