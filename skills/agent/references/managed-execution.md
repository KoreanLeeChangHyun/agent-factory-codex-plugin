# Managed Execution

- Prompts, sessions, run files, retries, CLI responses and receipts.

<a id="managed-execution"></a>

<a id="prompts-and-sessions"></a>

## 1. Prompts and sessions

- Managed roles are `main`, `work` and `verification`; follow the role prompt supplied
  for the current run.
- Use `<plugin-root>/scripts/exec.py` for delegated roles; Main may also be exec-hosted.
- Resume exact session IDs; do not use `resume --last` or concurrent turns per session.
- New sessions use App Server when the installed protocol advertises `instructionDelivery`:
  effective developer-configuration reading, developer instructions on start/resume,
  instruction injection and structured turn output. User/project developer instructions
  are composed with the managed fixed rules. Unchanged fixed rules are not appended to
  each user message; changed rules are injected before the next turn and remain available
  for native compaction. Unsupported installations keep CLI delivery. Existing CLI
  sessions keep their transport unless an explicitly requested native feature requires it.
- Extension-managed submission preparation supplies the Agent Skill's source and content
  hash instead of its full body. Reuse it only when that exact content is loaded in the
  current context; read it before dispatch when missing, changed or lost after compaction.
  This instruction hash is not a submission request hash.
- `exec.py reset-conversation --agent <main-agent-id>` starts a fresh provider thread
  for an idle Main Agent while preserving its Agent identity, configuration, and all
  historical run directories. The command records a durable `conversationId` boundary
  under the dispatch/session locks and rejects active runs, unresolved latest decisions,
  linked active child Agents, or an active/uncertain Goal. Child acceptance binds the
  parent Agent/run and refuses a parent conversation boundary that changed in flight.
- Follow [Native Fast and Goal](native-fast-goal.md) for native objective controls and recovery.

<a id="run-files-and-retries"></a>

## 2. Run files and retries

- New runs return `status`, the exact `resultPath`, and a nonempty `resultText` in the
  final structured response.
- The runtime validates the envelope and atomically saves its UTF-8 text as `result.md`
  before terminal publication. Agents do not write or reread their answer file.
- Text is limited to 64 KiB (and 65,536 characters in the output schema), leaving room
  inside the bounded JSONL stream. Keep large artifacts in task-owned files and
  summarize them in the response.
- Work and Verification have separate machine receipts: Work returns its receipt fields in
  the final output and the runtime writes the file; Verification writes its own. Completed
  runs retain all request, role, capability and exact-Work receipt validation.
- Runs with persisted file-based response schemas use their bound completion contract.
  New turns use the structured response schema, including in existing sessions. Preserve
  completed runs and result paths. Native Goal controls use structured response
  persistence.

- `runs/<run-id>/` owns request/state/heartbeat/events/response schema/result/receipt; keep
  operational data separate from Skills/project information.
- Pass large context/requests through validated run files. Reject traversal, symlinks
  and unexpected file types; publish atomically and bound event/stderr logs.
- Submit asynchronously; persist dispatch intent/tuple first. Reconcile ambiguous
  acknowledgement with the same dispatch ID, without replacement dispatch.
- Distinguish accepted, started, active and terminal status; acceptance alone is not completion.
- Pre-start retries are idempotent. After successful launch, missing start events are
  ambiguous; no automatic replay. External/irreversible retries need Human authority.

#### Reported token usage

- `exec.py status --agent <agent-id> --run-id <run-id>` exposes `run.tokenUsage` and
  `run.usageAttempts` for runs observed by this runtime. Historical runs without them
  remain unavailable; they are not backfilled from the latest context size.
- Counters are `inputTokens`, `cachedInputTokens`, `outputTokens` and
  `reasoningOutputTokens`. Cached input is a subset of input; reasoning is a subset of
  output. Do not add subsets again. Missing counters are `null`, never assumed zero.
- `coverage` is `reported` or `unavailable`. `reports` counts accepted usage reports,
  not model/tool calls. CLI reports turn usage; native reports use session-counter
  deltas after the first observed inference, excluding pre-existing session totals.
  Repeated native totals and identified CLI turns are counted once. Counter resets
  increment `counterDiscontinuities` and resume counting from the latest reported inference.
- Attempt snapshots replace previous snapshots for that attempt. Run totals sum distinct
  attempts; an unavailable counter in any attempt makes that aggregate counter unknown.
  Reported usage survives later execution failure. Provider omissions, interrupted streams,
  or notifications arriving after completion can leave consumption unreported.
- These are backend-reported counters, not a billing estimate, subscription allowance,
  context occupancy, or proof of a token-saving percentage. Compare equivalent tasks,
  models and routes, including quality and retries. Prompt byte sizes measure transport
  size only; loading a referenced Skill still consumes input tokens when needed.

<a id="cli-and-receipts"></a>

## 3. CLI and receipts

- Public exec/loop JSON responses include additive `operation` metadata:
  `{ "schemaVersion": 1, "provider": "agent-factory", "script": "exec.py", "action": "submit" }`.
  Renderers may use it for activity labels without parsing shell wrappers. Command
  completion does not mean run completion; use the matching run's status. Older or
  mixed output remains available as raw evidence, without inventing identities.
- Standalone submit/send generates and returns `dispatchId` when omitted. A new
  invocation without an explicit key is a new request, not a retry. For uncertain
  acceptance, inspect the Agent's existing runs; recover using the original key
  and immutable inputs. Loops manage this binding automatically.

- Subcommands and arguments of `exec.py` and `loop.py`: [exec.py usage](../../tool/references/usage/exec.md), [loop.py usage](../../tool/references/usage/loop.md).
- `submit` and `send` accept either the existing text inputs or `--input-file`.
  - The latter is a versioned `agent-input` JSON document containing `message` and up to
    eight sibling PNG, JPEG, GIF or WebP filenames.
  - The runtime rejects traversal, symlinks, non-regular files, MIME/extension
    mismatches, images over 10 MiB, and combined image content over 20 MiB, then
    captures accepted bytes into the run before asynchronous acknowledgement.
  - Codex exec receives those files through `--image`; app-server turns receive
    `localImage` inputs.
  - Native Goal activation has no image field in the installed app-server schema;
    requests combining images with enabled Goal mode fail before run creation instead of
    silently discarding image content.
  - For direct Main, disable Goal for that turn. Work requires Goal and reports this
    unsupported image/Goal combination instead of silently dropping the image or Goal.
- The `capabilities` response advertises `images: true` independently for `submit` and
  `send`. Clients must require that flag before using `agent-input`; a missing or
  false flag identifies a runtime that cannot guarantee image delivery and must not be
  downgraded to attachment-reference text.
- `loop.py reconcile` performs one transition. `loop.py skip` requires a Human actor,
  authorization reference and decision evidence; missing evidence fails closed. Timing and END
  follow [the Agent graph](../SKILL.md#roles-and-graph).
- Completed runs publish validated `receipt.json` beside `result.md`.
- Unsaved error captures never fail a run: its status reports them as `pendingLessons` and a
  later writable run records them ([runtime capture](../../document/references/lessons-learned.md#runtime-capture)).
- Work receipts identify the request, project-root-relative changed paths and addressed
  finding IDs for revisions.
- Each Work run captures its response contract at creation (`responseContract` in its status;
  `capabilities` advertises the newest as `responseContract`):
  - `2`: the final output also carries `outcome`, `changedPaths`, `tests` (`run`, `reason`) and
    `addressedFindingIds`. On `completed` the runtime adds `schemaVersion`, `kind`, `runId` and
    `requestHash`, validates the whole receipt and writes `receipt.json`. It never fills a
    judgment value: omitted fields fail as `receipt_missing` and nothing is written.
  - `1` (runs without the field): Work writes `receipt.json` itself. It remains for
    capability-bound runs, plan-only Work (host-recorded) and loops started before contract 2,
    whose later runs are dispatched with `--response-contract 1`. A run always finishes under
    the contract it captured.
  - A Codex native Goal turn takes no per-turn `outputSchema`. When its completed final
    message lacks valid receipt fields, the adapter asks once more in a schema-constrained turn.
  - A well-formed receipt is not proof of its values; independent Verification judges them.
- Runtime-only artifacts remain in the detailed result; `changedPaths` is empty when the
  project was untouched.
- Receipts use `outcome: completed`, including for read-only Work. Receipt version 0.1.0
  file receipts also accept `implemented` for compatibility.
- A loop started with `--receipt-recovery auto` (the default) gives Work one repair turn
  for the allowlisted receipt failures below instead of stopping: the driver dispatches the
  same recovery request once per task and records `receiptRecovery.automatic`. A second
  receipt failure, any other failure, `--receipt-recovery manual` and loops persisted before
  the setting stop as before.
- A stopped loop reports `failureClass` beside `controlPlaneError`; `capabilities` advertises
  `failureClass`. The runtime never re-dispatches Work; Main acts on the class:
  - `contract`: the Agent's output broke its contract. Automatic receipt recovery handles it;
    report a run that still ends failed.
  - `transient`: control plane. Run `loop.py reconcile`, read the status once more, then decide.
  - `provider`: model backend. Report its message; dispatch again only when the Human asks.
  - `environment`: the host or policy must change first. Stop and report the cause.
  - `human`: pass the decision to the Human. Anything else is `unknown`.
  - The one `workLight` or `scribe` to `work` retry applies only to `contract` or no class;
    a failed `explore` run is reported, not retried with write access.
- `task_repository_invalid` and `parent_session_invalid` are environment/binding failures,
  not Work failures. Preserve the accepted loop, results and parent identity. Do not
  switch `--project-root`, strip the managed parent environment or repeatedly assign a
  stronger worker. A different project requires its own correctly bound Main request.
- Work sub-agents are limited per provider; see
  [enforcement](execution-modes.md#captured-routes).
- Status reads retry a transient control-plane failure three times with backoff. A dispatch
  is never replayed; its durable intent is completed by `reconcile`.
- The driver periodically runs exec `reconcile` for a running child, so a run whose worker
  died becomes a recorded failure instead of an endless `running`.
- A worker that cannot start fails its run (`worker_start_failed`). A stale run that never
  launched a worker is resubmitted by exec `reconcile`, or cancelled when cancellation was
  requested; `cancel` ends such a run immediately.
- A loop whose first dispatch fails stops as `runtime-error`, keeping its dispatch intent for
  `reconcile`. Commands that leave a loop `active` launch a driver only when none runs; a
  repeated `start` returns the accepted loop unchanged.
- `recover-receipt` is an explicit, allowlisted recovery for a loop stopped on a deterministic
  Work receipt missing, format or changed-path-contract failure:
  - Test-proof, core/capability-binding, and unsafe path failures are not recoverable.
  - Preserve the failed run and loop.
  - Resume the exact Work session in a fresh run through durable dispatch.
  - Retain original request, captured task mode, findings, capability and
    execution-policy bindings.
  - The recovery request forbids repeating completed effects; active, ambiguous, unsafe
    and non-receipt failures fail closed.
  - Reconcile only after the recovered Work actually completes. In `work` mode, end
    the loop with `work-completed`; Main acknowledges and reports Work results and own checks,
    with separate Verification `not requested`.
  - In verification modes, start independent Verification with the preserved failed-run
    evidence unless an evidenced Human skip applies. Follow [execution modes](execution-modes.md) for completion
    and skip rules.
- Work-bound Verification uses `--verified-work-run-id`; its receipt binds the exact Work run and original
  request. `pass` has no findings; `fail` has actionable findings.
- Standalone Verification uses `--task-mode verification` without Work/hash overrides. Its
  `standalone-verification-receipt` binds its own `runId` and target `requestHash` with
  decision/findings; it cannot substitute for a Work-bound receipt.
- Plan-only Work uses `--task-mode plan`: actual Plan mode returns a plan and the host
  records read-only completion without a default execution turn.
- Exec owns process/session/run facts and genuine same-session Plan/default turns. Loop
  owns delegated transitions and END; Main owns completion of direct tasks and its own
  checks in direct/work/plan-work modes. See [execution modes](execution-modes.md).
