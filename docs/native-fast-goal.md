# Native Fast and Goal

Agent Factory can use installed Codex's local app-server over stdio inside the
existing managed worker. No separately hosted service is required. Cloud
reporting remains an observer of local execution.

The implementation targets the protocol exposed by **Codex CLI 0.153.4**,
inspected on 2026-09-06. This is an implementation baseline, not a claim that
every older or newer version, model, account, or managed configuration supports
both features. `exec.py capabilities` generates the installed executable's
experimental JSON schema and reports actual protocol fields and methods. Use
`--agent ID` to inspect the executable bound to an existing session. Schema
support does not imply account entitlement: the execution checks `model/list`
and fails with a native diagnostic if the selected model has no advertised
Fast tier or the backend rejects a feature.

```sh
python3 skills/agent/scripts/exec.py capabilities
python3 skills/agent/scripts/exec.py submit --project-root /project \
  --agent main-example --role main --message 'Finish the agreed migration' \
  --model MODEL --reasoning-effort high --fast --goal-mode
python3 skills/agent/scripts/exec.py send --project-root /project \
  --agent main-example --message 'Include the agreed follow-up' \
  --no-fast --no-goal-mode
```

`--fast` selects the selected model's advertised Fast service-tier identifier
through `turn/start.serviceTier` for ordinary turns and freshly loaded
`thread/resume.serviceTier` for Goal execution. `--no-fast` explicitly sets `default`.
Omission inherits the session setting. Model and reasoning overrides are also
accepted on both submit and send. Every send resumes the exact stored Codex
thread ID. There is no `--last` lookup or prompt-based imitation of speed.
Explicit execution options are part of the immutable dispatch tuple; accepted
runs do not allow a second run to take concurrent ownership of the session.
Existing ordinary sessions continue using `codex exec` until native support is
needed. Once a session uses the app-server adapter, it keeps that transport so
explicit off settings clear native state reliably.

`--goal-mode` creates or reopens a native persisted objective. For the first
Goal request, the message becomes the objective if it fits within 4,000
characters. Supply `--goal-objective '...'` for a separate objective or a long
request. On an existing goal, omission of the objective preserves it and its
usage; providing another objective replaces it according to Codex's native
semantics. A send with omitted Goal settings inherits the prior mode and does
not explicitly reopen a paused objective. An explicit `--goal-mode` does reopen
it. `--no-goal-mode` clears the native objective before starting an ordinary
turn. No token budget is inferred or invented.

Goal continuation is **Main-only**. Work and Verification keep bounded turns,
receipt validation, and their existing graph roles; their execution disables
native Goal continuation. The Main role and exact managed request are installed
as thread developer instructions so automatic turns retain the same graph and
authority. Native Goal events never advance `loop.py` or substitute for a
Verification pass or evidenced Human skip. Main must still delegate Work and
Verification through that graph.

Codex schedules automatic continuation. Agent Factory waits for native Goal
state instead of issuing fabricated continuation prompts or treating an
ordinary `turn/completed` as objective completion. An active goal keeps the
managed run open. A native complete goal allows the final managed result to be
processed. Paused, blocked, usage-limited, and budget-limited goals produce a
Human-decision outcome, independently of ordinary turn completion. Native
turn/RPC errors fail the run with a diagnostic. The existing managed turn
timeout and bounded event/stderr limits also bound the entire continuation
sequence.

## Goal controls

```sh
python3 skills/agent/scripts/exec.py goal --project-root /project --agent main-example get
python3 skills/agent/scripts/exec.py goal --project-root /project --agent main-example refresh
python3 skills/agent/scripts/exec.py goal --project-root /project --agent main-example pause
python3 skills/agent/scripts/exec.py goal --project-root /project --agent main-example reopen
python3 skills/agent/scripts/exec.py goal --project-root /project --agent main-example cancel
python3 skills/agent/scripts/exec.py goal --project-root /project --agent main-example disable
```

- `get` returns the last native observation and its timestamp/error. It does not
  claim to refresh state changed in another Codex interface.
- `refresh` reads native state using the active connection, or a managed control
  run when idle. It does not start a model turn.
- `pause` preserves the objective and usage, sets native paused status, and
  interrupts an active turn. It never reports objective completion.
- `reopen` (alias `resume`) sets the existing objective active, preserving usage,
  and starts a managed Main turn. It requires an idle session and an existing
  objective. It does not manufacture an objective after cancellation.
- `cancel`, `clear`, and `disable` clear the objective and interrupt an active
  turn. Disable/off does not leave a sticky enabled setting. Set a new objective
  to start again after clearing.

Controls accepted during a live run are persisted in its state and handled by
that run's RPC owner. Acceptance is not native application: observe subsequent
Goal events or errors. Idle controls use managed run acceptance, process
containment, and results. Pause/clear/refresh controls return operational
Human-decision results; they do not generate a model response or complete a
goal. The regular run Stop/`cancel` command attempts to **pause** the objective
before terminating containment. It preserves the objective for reopening.

The extension exposes Fast and Goal beside the composer, a bounded objective
field, native status/token/time observations, and refresh, pause, reopen,
cancel, and disable controls. Work/Verification panels cannot enable Goal.
Settings are sent explicitly on both initial and subsequent messages. Native
Goal completion is displayed separately from managed run completion.

## Limits and recovery

An installed schema can advertise a feature that account or administrator
policy later denies; the native error is authoritative. The adapter does not
change credentials, installation, or account policy. Interactive app-server
requests fail with an actionable diagnostic rather than silently granting
approval. Existing runtime permission/sandbox and process-containment contracts
remain in effect.

Pause before forced termination is bounded and best effort. A crash, an
unresponsive RPC, a full event stream, or immediate external termination may
leave the persisted native goal active. The run records an unconfirmed pause
when observed; do not interpret a stale observation as confirmed native state.
Use native refresh before reopening after uncertain termination. No ambiguous
launched run is automatically replayed. Goal status can also be changed outside
Agent Factory; its cached observation is explicitly timestamped.

The changes and authored tests require independent Verification. Suggested
focused commands, from their owning repositories:

```sh
# plugin/
python3 -m unittest discover -s tests -p 'test_native_codex.py'
python3 -m unittest discover -s tests -p 'test_agent_exec.py'
python3 -m unittest discover -s tests -p 'test_agent_loop.py'
python3 -m unittest discover -s tests -p 'test_agent_cloud_reporting.py'
# extension/
npm run typecheck
node --check static/js/chat.js
node --test test/unit/runtime-adapter.test.mjs
```

Official references: [Codex App Server](https://learn.chatgpt.com/docs/app-server)
documents persisted `thread/goal/set`, `get`, `clear` and goal notifications,
including the objective limit and same-objective usage preservation.
[Configuration Reference](https://learn.chatgpt.com/docs/config-file/config-reference)
describes `features.goals` and model-catalog tier selection via
`features.fast_mode`. Exact service-tier, Goal-status, and output-schema fields
were inspected in the installed CLI's generated experimental app-server schema,
not inferred from wrapper command help.

## Recovery and Verification contracts

Fast and Goal are negotiated independently. Explicit Fast off overrides
`service_tier` in legacy initial/resumed exec and app-server configuration;
it is never dropped because the optional capability is unavailable. A backend
without Goal APIs can run Fast/default-tier Main turns without invoking Goal
methods. If a previously observed goal exists after capability loss, off disables
local continuation and exposes that native clearing is unconfirmed; restore a
compatible backend and refresh rather than assuming the objective vanished.

Supervisor stop paths attempt bounded pause, including stream failures and log
overflow. Unconfirmed pause is persisted to both run and session and returned
through status/result even when the bounded event log is full. Warnings are
newline-terminated JSONL records. A failed, cancelled, or Human-decision run
always displays authoritative status and diagnostics; retained text is partial.

## Native scheduling and result validation

The adapter first loads with continuation disabled and installs complete Main
instructions. It stages the objective paused and confirms the persisted state.
It then stops its own app-server child and waits for process/reader exit before
starting a replacement child within the same managed containment. The fresh
process resumes the exact thread with continuation enabled, Main instructions,
model/reasoning/tier settings, and the exact final JSON contract. It confirms
objective/status/usage/budget identity before activation. A reload or accounting
mismatch fails before activation.

Native Goal activation starts the first turn and all continuation. No explicit
`turn/start` is submitted for an active Goal. Per-turn transport `outputSchema`
is therefore not used for Goal work: installing it first would begin unaccounted
work or race native scheduling. The exact schema is supplied in developer
instructions; strict runtime terminal JSON keys/status/result-path checks,
managed result-file checks and role receipt validation remain mandatory. This
changes how the result is requested, not what results are accepted. Ordinary
non-Goal turns keep their per-turn output schema.

A resume against an already loaded thread does not reliably apply new config.
The [official app-server documentation](https://learn.chatgpt.com/docs/app-server)
explains that unsubscribe unloads only after a 30-minute inactivity window.
Consequently this adapter uses confirmed owned-process replacement, not an
assumed immediate unsubscribe/reconfiguration. It does not restart unrelated
Codex processes or alter the native thread ID/objective accounting.

## Installed scheduler with a fake model

The former `AF_VERIFY_LIVE_GOAL` paid-model harness has been removed. Independent
evidence showed its 4,000-token Goal setting did not cover its initial model
work. No effective 4,000-token real-model bound is claimed or established here;
no account-model rerun is authorized by this guide.

The replacement test runs the **real installed Codex scheduler, adapter and
transport with a fake local model**. A test-only loopback Responses provider
supplies controlled SSE model messages, advertised native Goal tool calls, and
usage. A temporary isolated CODEX_HOME selects only that provider; credentials
are dummy/local and production authentication is unchanged. It is not a
real-model quality, entitlement or billing test, nor a distributed server.

The provider caps requests at 16, reports 110 controlled tokens per accepted
response (at most 1,760), and the scheduler observation has a shared 90-second
bound. Tests require native automatic turns, nonzero persisted accounting,
exact-session reopening, pause/cancel of native work and strict result rejection.
They fail if the installed host does not expose the necessary native Goal tool
or scheduler behavior; there is no synthetic follow-up turn fallback.

From `plugin/`, independent Verification may run:

```sh
python3 -m unittest discover -s tests -p 'test_native_transport.py'
AF_VERIFY_LOCAL_CODEX=1 AF_VERIFY_EVIDENCE=/absolute/verification-run/native-local.json \
  python3 -m unittest discover -s tests -p 'test_installed_native_scheduler.py'
```

`AF_VERIFY_CODEX` optionally selects the installed executable. Without the
local-fixture opt-in, that installed-host test is explicitly skipped. Retained
RPC/startup/failure/cleanup evidence is labeled as real host with fake model.
Work authors these checks; only independent Verification executes them.

## Final native turn correlation

Goal snapshots can be newer than the event currently being consumed. A terminal
Goal observation therefore triggers an authoritative `thread/read` check; it
does not complete the last answer seen. The adapter waits for the latest native
turn's own message and completion events and for native work to be idle, then
validates that turn's exact result. A later failed/interrupted turn or invalid
answer cannot be replaced by an earlier valid answer. Queue emptiness and fixed
delays are not completion evidence.

The installed-host/local-model suite also invokes production `Bridge.run` after
holding event consumption until native history confirms both turns completed.
It covers valid-earlier/invalid-final, valid-earlier/failed-final-result, and
valid-final success, without explicit follow-up turns or account-provider use.
Its additional evidence is written beside `AF_VERIFY_EVIDENCE` with `-delayed`
added to the filename. Native failed/interrupted event handling also has a
focused protocol regression. Work does not execute these tests.
