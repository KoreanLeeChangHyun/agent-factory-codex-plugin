---
name: agent
description: Run the Agent Factory Main, Work, and Verification graph from a CLI or hosted interface with managed Codex exec sessions for delegated roles.
---

# Agent Factory Agent

## Graph

Agent Factory has exactly three Agent roles and one execution graph:

```text
Main -> Work -> Verification
          ^          |
          +-- fail --+
                     +-- pass -> END
                     +-- Human skip -> END
```

- Main is the Human-facing orchestration and result-integration role.
- Work performs the bounded task.
- Verification independently verifies the latest Work result.
- A failed Verification returns its feedback to the same Work Agent. Repeat Work and Verification until Verification passes.
- The Human may record skip intent at any time before the next Verification
  starts. That control-plane intent takes effect only after the current initial
  or revision Work turn completes; the graph then starts no next or additional
  Verification run and reaches `END`.

Do not add another Agent role, node, or route. Main does not perform Work or Verification itself. Work does not verify its own work. Verification does not repair the work.

## Role prompts

The Agent Factory role system-prompt sources are `prompt/main.md`,
`prompt/work.md`, and `prompt/verification.md`. For an exec-hosted role, the
runtime validates and reads the selected file, then injects its complete text as
a tagged role-instruction block in the `codex exec` stdin request on every
initial and resumed turn. This is Agent Factory's prompt transport contract; it
does not claim a separate platform system-channel message. Only `main`, `work`,
and `verification` are valid role identifiers.

Main is the same graph node whether the Human reaches it through Codex CLI, an
exec-hosted session, or a VS Code extension. These are entry interfaces and
hosts, not additional Agent roles. Codex CLI is the default entry interface.
Main continues Human conversation while child work runs, preserves exact active
session/run state, and connects new input to the existing task. New input does
not implicitly cancel or abandon prior work. An explicit Human redirect
preserves existing execution/result state and is recorded as a control-plane
transition within the same graph.

## Managed sessions

Start delegated Work and Verification through `scripts/exec.py`; Main may
also be exec-hosted. Preserve the exact Codex session identifier so later turns
resume the same role session. Do not use `resume --last` and do not run
concurrent turns in one session.

Store operational state below `<project-root>/.agent-factory/agent/<agent-id>/`. Each request has a separate `runs/<run-id>/` directory containing its request, state, heartbeat, event stream, response schema, result, and role receipt. Keep runtime state separate from Skills and project information.

Pass request bodies and large context through validated files beneath the run directory. Reject traversal, symlinks, and unexpected file types. Publish runtime files atomically.

Submit turns asynchronously. The runtime distinguishes durable acceptance, process start, heartbeat, and terminal completion. Heartbeats are supervisor observations, not semantic progress claims.

On Linux, each attempt uses a private process group and records the boot ID and process start ticks with its PID. Cancellation and timeout signal only a verified managed process group. Unverifiable identity fails closed. Event and stderr logs remain bounded.

Acceptance, startup, heartbeat, and turn timeouts are distinct. Pre-start retry must be idempotent. Once process launch succeeds, an absent start event is ambiguous and must not be replayed automatically. Never retry an irreversible or externally visible action without Human authority.

## Runtime commands

Use `scripts/exec.py` for individual managed sessions: `submit`, `send`, `status`, `result`, `inbox`, `list`, `cancel`, and `reconcile`.

Use `scripts/loop.py` for the Work/Verification cycle:

- `start`: submit the initial Work turn;
- `reconcile`: advance one `Work -> Verification`, `fail -> Work`, or `pass -> END` transition;
- `status`: inspect loop state;
- `skip --actor human --authorization-reference REF --decision-evidence TEXT`:
  before the next Verification starts, record the explicit Human intent to skip
  it.

Missing evidence and non-Human skip attempts fail closed. `skip` starts no next
or additional Verification run only after the current Work turn completes; the
record itself is not a graph transition or completion. A managed child failure,
cancellation, or Human-decision request is a control-plane error and is not
graph completion. Only Verification `pass` or an evidenced Human skip applied
after Work completion reaches `END`.

## Receipts

Completed Work and Verification runs publish a validated `receipt.json` beside `result.md`.

- Work receipts bind the request and changed paths. A revision also lists the Verification finding identifiers it addressed.
- Verification receipts bind the exact Work run and original request, declare `pass` or `fail`, and carry actionable correction findings. `fail` requires at least one finding; `pass` requires none.

Persist every child dispatch intent and exact dispatch tuple before calling the
managed runtime. Reconcile an interrupted dispatch through the same dispatch ID;
never create a replacement intent for an ambiguous acknowledgement.

Every Verification dispatch supplies `--verified-work-run-id`. Failed findings return to the same Work session, and the next check uses the same Verification session.
