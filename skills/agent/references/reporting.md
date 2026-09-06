# Local execution and cloud reporting

## Ownership and configuration

`exec.py` owns local process/session/run facts and `loop.py` owns the graph. Cloud `reporting_read`, `reporting_write` and `reporting_search` own shared report persistence and discovery, not execution. Read the advertised `agent-factory://reporting/cloud-guide` and schemas. The development handoff is `/tmp/af-cloud-migration-20260906/local-reporting-handoff.md`; it is a development evidence locator, never an installed dependency.

Reporting is explicit opt-in through `exec.py --reporting-config`; absence keeps execution local. For `loop.py start`, use separate `--work-reporting-config` and `--verification-reporting-config` options for the corresponding roles; do not implicitly forward one role's reporting configuration to the other. Resolve the actual endpoint, recipient/project/organization/Workspace/reporting-user/cloud-Agent identities and owning credential reference from existing authority. Never silently pick a tenant, create a cloud Agent or raise scopes. Keep the endpoint exact, authenticated and bound to its recipient. Configuration and run state contain no credentials; secrets remain outside repository/runtime data in their owning store. Use the installed runtime's current configuration contract rather than copying evolving transport internals into callers. Do not invent configured accounts or claim live delivery from configuration.

## Durable association and delivery

Register each run as a new cloud task only after the real Codex session ID is durable. Preserve exact project, local Agent, actual session, run and optional loop identity in an immutable runtime binding. A resumed session with a new run gets a new task UUID; reconnect/retry keeps the original task, binding, target and reporting user.

Before network dispatch, atomically persist the validated command, durable key, expected revision and credential-free target/binding in the local outbox. Persist the acknowledgement before marking delivery done. Lost acknowledgement means unknown delivery: replay the identical command/key under current authorization, including after credential rotation. Never rewrite a pending command or bypass revision/identity conflicts with a new key. Read current cloud state and reconcile a genuinely new intended event separately. Preserve original commands and safe receipts for recovery.

Use the existing explicit command `exec.py reporting-deliver --project-root PROJECT --agent AGENT --run-id RUN` to reconcile/deliver that run's pending reports. It starts no AI turn and must not invoke submit or legacy `agent_run_submit`. Network delivery stays outside process supervision/termination and cannot block or replace local graph authority. Failure, denial, timeout, unknown acknowledgement or changed recipient remains pending with credential-free diagnostics. Local exec/loop paths and extension command/layout compatibility remain intact; no background daemon or new local provider service is required.

## Observation is not semantic completion

Heartbeats report only actually observed `process_alive`, `process_exited` or `unreachable` facts, with durable increasing sequence, nonregressing observed time and exact binding. Receipt time is delivery freshness, not observation freshness. Missing/stale observation, process exit, return code or disconnection never invent progress, failure, cancellation, semantic result or graph END. Do not fabricate timestamps to bypass clock skew.

Semantic reporting requires validated explicit terminal result evidence and applicable role receipts. Preserve durable semantic intent and retry evidence capture/delivery without rerunning execution. Bind exact result and validated receipt hashes; changed/replaced evidence fails pending. Upload required Document evidence only with its own authority. Freeform requests, paths, environments, secrets and arbitrary result/receipt bodies are not reporting metadata. Human-decision results remain input-required; runtime-only failure is a control-plane fact, not a fabricated semantic result.

Read cloud task status and separate semantic freshness, observation freshness and delivery freshness. Search returns bounded literal discovery excerpts; it is not a verdict and does not fetch linked content. Cloud report completion does not prove local Verification pass; local validated receipts and loop state retain that authority. Planning tools describe development tasks and remain separate from background-job execution and this runtime report stream.

## Deployment boundary

The retained adapter is a minimum local runtime dependency, not a cloud domain backend. Contract/source availability does not establish server registration, migrations, production credentials, transport/RLS verification, deployment or complete migration steps 1–13. Keep pending delivery and recovery evidence visible. Source/data retirement waits for backup and independent verified import plus exact deletion authority where needed.
