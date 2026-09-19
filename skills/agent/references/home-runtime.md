# Local Agent Runtime

- The runtime manages local projects, sessions, runs and execution results.

<a id="storage-and-identity"></a>

## 1. Storage and identity

- **Runtime home:** host default `~/.agent-factory` or explicit absolute `AGENT_FACTORY_HOME`.
  Codex keeps its own home/credentials.
- **Roots:** canonical worktree `projectRoot` differs from `runtimeRoot`. Create no checkout
  `.agent-factory` marker/runtime/backend/catalog or symlink fallback.
- **Registry:** private/versioned; random stable `project-<32 hex>` per canonical worktree
  path. Copies/worktrees have distinct IDs even with the same remote.
- **Layout:** `projects/<project-id>/agents/<agent-id>/` holds sessions/runs/loops; each run owns its outbox. Locks,
  owner-only permissions and copy-once metadata protect initialization. Unsafe links,
  unsupported versions or ambiguous bindings fail closed.

<a id="installation-and-connection"></a>

## 2. Installation and connection

<a id="initialization"></a>

### 2.1. Initialization

1. Initialize with `exec.py init --project-root PROJECT`; first submit and extension connection use the same
   helper. An installed entry is `python3 /absolute/installed/plugin/skills/agent/scripts/exec.py init --project-root /absolute/code/worktree`.
2. Inspect versioned locations/registrations with `location` and `projects`.
   `list`, capability inspection and status discovery never initialize missing
   storage.
3. Use the returned project identity and runtime location for subsequent commands.

- Marketplace installation runs no arbitrary post-install command; the manifest supplies
  no initialization hook and installation does not trust hooks.
- VS Code uses the workspace extension host's home, including SSH/containers, not the UI
  host's.

<a id="permissions"></a>

### 2.2. Permissions

- **Inheritance:** children inherit the parent's filesystem, network and approval
  policy; no separate child sandbox default. Persist the resolved policy in session, run
  and dispatch identity. Historical run and dispatch policies remain immutable.
- **Next-turn changes:** an idle `send` may explicitly select a complete policy
  file or sandbox/approval pair for its new run; persist that current session policy
  under dispatch/session locks.
  - Omitted inputs keep the current stored policy.
  - Reject active session changes and partial mismatched overrides.
  - Children still match their parent exactly; no automatic widening or fallback.
  - Preflight the selected policy before launch. `capabilities --agent` exposes optional canonical
    `executionMode` for the stored policy.
- **Sources:** managed parent snapshot first, then the exact external Codex `CODEX_THREAD_ID`
  turn context. Without a parent, resolve explicit inputs or the selected Codex's
  effective configuration; fail if authority is unavailable. Never infer permission from
  a project directory.
- **Explicit inputs:** `--execution-policy-file`, or `--sandbox` with `--approval-policy`, `--[no-]network-access` and
  repeated `--writable-root`. Explicit child inputs must match the parent's resolved policy.
- **Run output:** derive exact managed-run write access from the persisted policy; a
  read-only code root stays read-only. Preserve inherited network access.
- **Background approval:** forward the selected approval policy; interactive approval
  requests require Human handling and are never automatically granted.
- **Human approval:** `--human-approval-policy bypass` is Main-only and persists for the session.
  - It authorizes Main to cross the delegation gate from the current Human request for
    work without a separate plan-approval turn; it neither expands request scope nor
    changes the captured execution route.
  - Conversation remains Main's direct responsibility under either policy and starts no
    child graph.
  - Omitted sends preserve the session policy.
- **Linux:** split permissions require bubblewrap; legacy Landlock cannot represent
  them. Denied user-namespace setup fails closed; never substitute a wider policy.
- **References:** [sandbox backend](https://github.com/openai/codex/blob/main/codex-rs/linux-sandbox/README.md), [configuration](https://learn.chatgpt.com/docs/config-file/config-reference).

<a id="host-readiness-and-diagnostics"></a>

### 2.3. Host readiness and diagnostics

- Run `python3 <installed-agent-skill>/scripts/exec.py doctor` when first choosing a managed host,
  when that host changes, or when diagnosing a relevant failure. Reuse the observation
  for unchanged hosts; it is not a per-submission ceremony or a substitute for launch preflight.
- Add `--probe` to exercise the system bubblewrap helper on Linux with a five-second
  timeout, read-only filesystem and isolated network.
- Neither command initializes the runtime registry or changes host policy.
- `--codex PATH` selects the executable to locate; this inventory does not prove its
  version or complete sandbox works.

| Host | Managed execution | Required action |
| --- | --- | --- |
| Linux, including Ubuntu | Requires `/proc` identity and usable containment/sandbox facilities | Inspect `doctor`; use `--probe` for system bubblewrap evidence. |
| macOS | Requires kernel boot/process identity and private process groups | Use Python 3.10+ and inspect `doctor`; validate the selected native Codex sandbox on the actual Mac. |
| Native Windows | Unsupported by this managed runtime | Use a separately checked Linux host or WSL environment. |
| Other operating systems | Unsupported | Use a supported host. |

- macOS `doctor --probe` reports the Linux bubblewrap probe as `not-applicable`; it reads native
  identity availability and leaves sandbox readiness unknown.
  - For custom `AGENT_FACTORY_HOME`, use an absolute path with no symlink ancestors (for example,
    `/private/tmp/...` rather than the macOS `/tmp` alias).
  - The runtime does not weaken its path checks to accommodate aliases.
- Native API references: [process info](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/proc_info.h), [boot session UUID](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_sysctl.c).
- Unsupported hosts return `managed_platform_unsupported`; use a supported host without
  broadening permissions.
- `sandboxReadiness: unknown` is intentional: locating a binary, an enabled AppArmor setting, or a
  successful system helper probe is not a Codex sandbox pass. Codex may use a bundled
  helper, so missing system bubblewrap is not conclusive.
- Every managed attempt preflights the **selected Codex executable and policy** before
  launching the Agent: read the request and write inside the exact run directory.
  - Record evidence as `executionPreflight`; failure ends the run before launch.
  - Do not retry with broader permissions or substitute a host helper probe.
- An observed filesystem-helper initialization failure is reported as `sandbox_unavailable`,
  including nonzero exec exits and app-server error events.
  - Unrelated command failures retain their original classification.
  - For legacy runs, a structured failed file change for the exact managed result path
    followed by a missing file reports `result_file_write_failed`; it does not infer a sandbox cause
    from Agent prose.
- On Linux, inspect security audit logs and container/namespace restrictions. AppArmor
  is one possible cause, not a universal Linux diagnosis. Host policy changes belong to
  the host administrator and are never applied automatically.
- Exit codes: `0` means inventory completed (or the requested helper probe
  passed), `1` means a required inspected prerequisite is absent or the probe
  failed/could not run, and `2` means the managed platform is unsupported. None
  certifies successful managed execution on the selected host.

<a id="relocation"></a>

### 2.4. Relocation

1. Use `exec.py rebind --runtime-home HOME --project-id ID --from-root OLD --project-root NEW`.
2. Require matching old binding, an existing unregistered destination and no active
   runs.
3. Restart clients. Existing clients stay pinned and must fail on registry change.

- Rebinding preserves identity; it neither merges projects nor resolves conflicting
  histories.

<a id="managed-execution"></a>

## 3. Managed execution

<a id="prompts-and-sessions"></a>

### 3.1. Prompts and sessions

- Managed roles are `main`, `work` and `verification`; follow the role prompt supplied
  for the current run.
- Use `scripts/exec.py` for delegated roles; Main may also be exec-hosted.
- Resume exact session IDs; do not use `resume --last` or concurrent turns per session.
- `exec.py reset-conversation --agent <main-agent-id>` starts a fresh provider thread
  for an idle Main Agent while preserving its Agent identity, configuration, and all
  historical run directories. The command records a durable `conversationId` boundary
  under the dispatch/session locks and rejects active runs, unresolved latest decisions,
  linked active child Agents, or an active/uncertain Goal. Child acceptance binds the
  parent Agent/run and refuses a parent conversation boundary that changed in flight.
- Follow [Native Fast and Goal](native-fast-goal.md) for native objective controls and recovery.

<a id="run-files-and-retries"></a>

### 3.2. Run files and retries

- New runs return `status`, the exact `resultPath`, and a nonempty `resultText` in the
  final structured response.
- The runtime validates the envelope and atomically saves its UTF-8 text as `result.md`
  before terminal publication. Agents do not write or reread their answer file.
- Text is limited to 64 KiB (and 65,536 characters in the output schema), leaving room
  inside the bounded JSONL stream. Keep large artifacts in task-owned files and
  summarize them in the response.
- Work and Verification write separate machine receipts. Completed runs retain all
  request, role, capability and exact-Work receipt validation.
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

<a id="cli-and-receipts"></a>

### 3.3. CLI and receipts

- Public exec/loop JSON responses include additive `operation` metadata:
  `{ "schemaVersion": 1, "provider": "agent-factory", "script": "exec.py", "action": "submit" }`.
  Renderers may use it for activity labels without parsing shell wrappers. Command
  completion does not mean run completion; use the matching run's status. Older or
  mixed output remains available as raw evidence, without inventing identities.
- Standalone submit/send generates and returns `dispatchId` when omitted. A new
  invocation without an explicit key is a new request, not a retry. For uncertain
  acceptance, inspect the Agent's existing runs; recover using the original key
  and immutable inputs. Loops manage this binding automatically.

- `scripts/exec.py`: `submit`, `send`, `status`, `result`, `inbox`,
  `list`, `cancel`, `reconcile`.
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
  - Disable Goal for that turn.
- The `capabilities` response advertises `images: true` independently for `submit` and
  `send`. Clients must require that flag before using `agent-input`; a missing or
  false flag identifies a runtime that cannot guarantee image delivery and must not be
  downgraded to attachment-reference text.
- `scripts/loop.py`: `start`, `status`, `reconcile` (one transition), `recover-receipt`,
  `skip --actor human --authorization-reference REF --decision-evidence TEXT`. Missing skip evidence or non-Human actors fail closed. Timing and END
  follow [the Agent graph](../SKILL.md#roles-and-graph).
- Completed runs publish validated `receipt.json` beside `result.md`.
- Work receipts identify the request, project-root-relative changed paths and addressed
  finding IDs for revisions.
- Runtime-only artifacts remain in the detailed result; `changedPaths` is empty when the
  project was untouched.
- Write `outcome: completed` in receipts, including for read-only Work. Receipt version 0.1.0
  also accepts `implemented` for compatibility.
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
    the loop with `work-completed`; Main then performs appropriate own checks and integrates,
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

<a id="linux-containment"></a>

## 4. Cancellation and containment

<a id="systemd-backend"></a>

### 4.1. Managed cancellation

- Cancel through `exec.py cancel` with the exact Agent and run identity.
- Check the resulting status; request acceptance alone does not prove process termination.
- Do not signal a reused PID or manipulate runtime containment records directly.

<a id="fallback"></a>

### 4.2. Containment limitations

- `weakerDescendantContainment: true` means detached descendants may escape
  process-group cancellation. Report this limitation when termination is uncertain.
- This flag does not widen filesystem or network permissions.
- Preserve ambiguous runs and reconcile their status before retrying work.

<a id="capability-bindings"></a>

## 5. Capability bindings

<a id="authority-and-configuration"></a>

### 5.1. Authority and configuration

- Bind allowed capabilities and effects to the request and receipt. Capability availability
  grants no additional execution authority; keep credentials outside binding files.
- Individual runs: `exec.py --capability-binding-file`.
- Loops: separate `--work-capability-binding-file` and `--verification-capability-binding-file`; never forward bindings between roles.
- Strict versioned schema: 1–32 unique capability IDs, authority kind/reference,
  invocation route, exact target, allowed effects/scopes, nullable approval reference;
  no credential/token fields. Reject unknown fields and invalid bounds.

<a id="validation"></a>

### 5.2. Validation

- Supply regular, bounded JSON files without symlinks or credentials.
- Use the canonical binding path and hash returned by the runtime.
- Report ordered `capabilityOutcomes`, one per binding, with request hash, run ID,
  capability ID, authority, target and `succeeded`, `failed`, `unknown` or `not-invoked`.
- Do not omit, reorder, widen or substitute bound capabilities.

<a id="legacy-migration"></a>

## 6. Legacy records

- Preserve old runtime and document records; initialization does not authorize migration
  or deletion.
- For an already migrated path, use `exec.py map-path --project-root PROJECT --path OLD_PATH`
  to resolve its archive path and byte digest.
- Keep archives immutable. An archived or malformed record is not proof of completion.
- Resolve projects separately; nested checkouts do not share an identity automatically.
- Report an unavailable mapping or recovery operation instead of editing runtime state.
