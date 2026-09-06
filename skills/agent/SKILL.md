---
name: agent
description: Run the Agent Factory Main, Work, and Verification graph from a CLI or hosted interface with managed Codex exec sessions for delegated roles.
metadata:
  specification-id: agent
  human-entry: .agent-factory/document/specification/agent/index.html
  ai-root: skills/agent/
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

## Task decomposition and chain orchestration

Before delegation, Main examines the Human request for materially separable
bounded tasks. Main decides dependencies and actual independence by considering
overlapping repository paths and writes plus shared mutable resources such as
the Git index and worktree, Agent, session, loop, and run identities, databases,
ports, and external systems. Uncertainty about independence defaults to
sequencing or obtaining the missing Human decision; Main must not silently
treat uncertain tasks as independent.

When useful, Main may run multiple independent `Work -> Verification` chains
concurrently. Each chain remains internally sequential: its Verification starts
only after its Work result is complete and binds that exact Work run. Dependent
tasks, overlapping writes, and repository-wide integration or publication such
as Git commits are sequenced. Every parallel chain uses distinct Agent IDs,
loop IDs, run IDs, scoped authority and capability bindings, and bounded inputs.
Main continues the Human conversation, tracks every active chain, preserves all
execution and result state, and integrates results in dependency order without
losing or implicitly cancelling work.

Decomposition and safe distribution are Main's orchestration judgment and
responsibility. They are not a claim that the runtime mechanically guarantees
conflict freedom, a new Agent role or graph node, or a requirement to maximize
parallelism.

## Managed sessions

Start delegated Work and Verification through `scripts/exec.py`; Main may
also be exec-hosted. Preserve the exact Codex session identifier so later turns
resume the same role session. Do not use `resume --last` and do not run
concurrent turns in one session.

Store operational state below `<project-root>/.agent-factory/agent/<agent-id>/`. Each request has a separate `runs/<run-id>/` directory containing its request, state, heartbeat, event stream, response schema, result, and role receipt. Keep runtime state separate from Skills and project information.

Pass request bodies and large context through validated files beneath the run directory. Reject traversal, symlinks, and unexpected file types. Publish runtime files atomically.

Submit turns asynchronously. The runtime distinguishes durable acceptance, process start, heartbeat, and terminal completion. Heartbeats are supervisor observations, not semantic progress claims.

On Linux, Worker launch negotiates containment capabilities. When the required
commands and a responsive user manager are available, each run/launch attempt
uses a uniquely bound transient systemd service with the Worker as its main
process, Codex as a child, `Type=exec`, control-group termination, collection,
the submitting process's safely transferable environment, and bounded
TERM-to-KILL escalation. Selection checks the required command features, user
manager, environment-transfer mechanism, and cgroup-v2 population interface.
The runtime records the exact backend and opaque containment identity before or
with launch acknowledgement, queries that binding before reconciliation or
signalling, and confirms from the bound control group's population—not merely
service state or leader PID—that the containment is empty after cancellation.

When user systemd is absent or unusable, the runtime preserves the existing
startup barrier, private session/process groups, and boot-ID/start-ticks PID
identity validation. This fallback fails closed on unverifiable identity and
retains conservative stale-run/non-replay behavior, but its descendant
containment is weaker than a service control group. Systemd is a negotiated
Linux runtime capability, not a universal requirement. The containment
interface is the adapter boundary for a future platform backend; the current
runtime does not claim Windows support. Event and stderr logs remain bounded.

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

## Result integration and commit publication

After independent Verification passes, or after an evidenced Human skip is
applied following Work completion, Main promptly performs an authorized Git
commit itself as narrow result integration/publication. The commit is not Work,
Verification, a new Agent role, or a new graph node, and Main does not delegate
a separate commit Work turn.

Before staging, Main inspects the latest Work result and receipt, the
Verification pass receipt or Human-skip evidence, and the current repository
status and diff. It stages and commits only the exact paths bound to that
verified or skipped result, preserves complete synchronized Specification
pairs, and excludes unrelated dirty, untracked, generated, and runtime changes.
Work and Verification never commit. Ordinary commit authority does not imply
push, amend, force, history rewrite, reset, restore, delete, or any other
repository publication or mutation. If exact safe staging or the ordinary
commit fails, Main reports the obstruction without broadening scope.

## Cloud reporting and search

The selected authenticated cloud MCP application owns shared reporting persistence and search. Read `agent-factory://reporting/cloud-guide` and the current `reporting_read`, `reporting_write` and `reporting_search` schemas before use. Use Document tools for Document persistence/search and upload required durable evidence. The local catalog executable and schema are retired; legacy `.agent-factory/db.sqlite` is preserved and is not a route for new domain work. Preserve old data until backed up and independently verified imported; no code retirement implies data deletion.

Local `exec.py` remains authoritative for process/session/run state; `loop.py` alone owns transitions, fail-return, Human skip and END. Cloud task/report status is an observation and semantic-report projection, never a command to launch, resume, cancel or finish local execution. Never use legacy `agent_run_submit` as reporting transport. A Work task completion or Verification execution completion does not imply Verification pass or graph END. Planning task state and background jobs remain separate.

For explicit runtime reporting configuration and delivery, read `references/reporting.md`. Missing connection, capability or recipient binding is reported honestly; do not infer a configured account, select a tenant/credential authority or create a local MCP/provider service. Existing local shell/file tools supply bounded Git/tool inspection. Keep local run, outbox, acknowledgement and recovery data local, and credentials with their owning authority. Reporting failure must not replay or take over local execution.

## Receipts

Completed Work and Verification runs publish a validated `receipt.json` beside `result.md`.

- Work receipts bind the request and changed paths. A revision also lists the Verification finding identifiers it addressed.
- Verification receipts bind the exact Work run and original request, declare `pass` or `fail`, and carry actionable correction findings. `fail` requires at least one finding; `pass` requires none.

Persist every child dispatch intent and exact dispatch tuple before calling the
managed runtime. Reconcile an interrupted dispatch through the same dispatch ID;
never create a replacement intent for an ambiguous acknowledgement.

Every Verification dispatch supplies `--verified-work-run-id`. Failed findings return to the same Work session, and the next check uses the same Verification session.

## Tool boundary

Tool owns logical discovery and lifecycle control for external tools and
connectors, but readiness does not authorize their use. Agent owns binding a
specific capability to a Work or Verification request, the authority for that
execution, and the resulting execution receipt. Preserve the authoritative
host, plugin, MCP server, or project manifest selected through Tool; do not
copy its registry or credentials into Agent runtime state.

Main may bind capabilities to an individual managed Work or Verification run
with `exec.py --capability-binding-file`. `loop.py start` keeps least privilege
with separate `--work-capability-binding-file` and
`--verification-capability-binding-file` inputs; a binding for one role is not
forwarded to the other. The strict versioned document contains one to 32
unique bindings, each with capability ID, authority kind/reference, invocation
route, exact target, allowed effects, allowed scopes, and a nullable approval
reference. The runtime validates unknown fields and bounds, canonicalizes the
document, copies it into the managed run, hashes it into the immutable dispatch
tuple, and exposes its canonical path/hash in run status. It stores no
credential or token field.

The caller-supplied binding file is opened without resolving or following any
file or parent-directory symlink. Unsupported safe traversal, traversal
components, non-regular files, unsafe parents, replacement races, and oversized
content fail closed before dispatch. The final component is opened nonblocking
before its descriptor is checked as a regular file, so a caller-controlled FIFO,
socket, or device cannot block the runtime. The bounded bytes read from the
same opened regular-file descriptor are the bytes canonicalized for the managed
run.

When a run has bindings, its role receipt must carry one ordered
`capabilityOutcomes` entry per binding. Each entry repeats the original request
hash, exact run ID, capability ID, authority, and target and records only
`succeeded`, `failed`, `unknown`, or `not-invoked`. Receipt validation re-reads
and hashes the canonical binding and rejects omitted, reordered, widened, or
substituted outcomes. Tool readiness still grants no execution authority.
