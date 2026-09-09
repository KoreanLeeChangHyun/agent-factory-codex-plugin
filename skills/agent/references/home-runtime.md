# Local Agent Runtime

## Storage and identity

- **Resolver:** `runtime/paths.py`; host default `~/.agent-factory` or explicit
  absolute `AGENT_FACTORY_HOME`. Codex keeps its own home/credentials.
- **Roots:** canonical worktree `projectRoot` differs from `runtimeRoot`.
  Create no checkout `.agent-factory` marker/runtime/backend/catalog or symlink fallback.
- **Registry:** private/versioned; random stable `project-<32 hex>` per canonical
  worktree path. Copies/worktrees have distinct IDs even with the same remote.
- **Layout:** `projects/<project-id>/agents/<agent-id>/` holds sessions/runs/loops;
  each run owns its outbox. Locks, owner-only permissions and copy-once metadata
  protect initialization. Unsafe links, unsupported versions or ambiguous bindings fail closed.

## Installation and connection

### Initialization

1. Initialize with `exec.py init --project-root PROJECT`; first submit and
   extension connection use the same helper. An installed entry is
   `python3 /absolute/installed/plugin/skills/agent/scripts/exec.py init --project-root /absolute/code/worktree`.
2. Inspect versioned locations/registrations with `location` and `projects`.
   `list`, capability inspection and status discovery never initialize missing storage.
3. Preserve the resolved binding across supervisor, Worker, loop children, native
   bridge and reporting sender.

- Marketplace installation runs no arbitrary post-install command; the manifest
  supplies no initialization hook and installation does not trust hooks.
- Initialization requires no cachebuster, reinstall or credential change.
- VS Code uses the workspace extension host's home, including SSH/containers,
  not the UI host's. Connections cache validated binding/filesystem event signature;
  failed initialization clears it.

### Permissions

- **Inheritance:** children inherit the parent's filesystem, network and approval
  policy; no separate child sandbox default. Persist the resolved policy in session,
  run and dispatch identity. Historical run and dispatch policies remain immutable.
- **Next-turn changes:** an idle `send` may explicitly select a complete policy file
  or sandbox/approval pair for its new run; persist that current session policy under
  dispatch/session locks. Omitted inputs keep the current stored policy. Reject active
  session changes and partial mismatched overrides. Children still match their parent
  exactly; no automatic widening or fallback. Preflight the selected policy before launch.
  `capabilities --agent` exposes optional canonical `executionMode` for the stored policy.
- **Sources:** managed parent snapshot first, then the exact external Codex
  `CODEX_THREAD_ID` turn context. Without a parent, resolve explicit inputs or the
  selected Codex's effective configuration; fail if authority is unavailable.
  Never infer permission from a project directory.
- **Explicit inputs:** `--execution-policy-file`, or `--sandbox` with
  `--approval-policy`, `--[no-]network-access` and repeated `--writable-root`.
  Explicit child inputs must match the parent's resolved policy.
- **Run output:** derive exact managed-run write access from the persisted policy;
  a read-only code root stays read-only. Preserve inherited network access.
- **Background approval:** forward the selected approval policy; interactive
  approval requests require Human handling and are never automatically granted.
- **Linux:** split permissions require bubblewrap; legacy Landlock cannot represent
  them. Denied user-namespace setup fails closed; never substitute a wider policy.
- **References:** [sandbox backend](https://github.com/openai/codex/blob/main/codex-rs/linux-sandbox/README.md),
  [configuration](https://learn.chatgpt.com/docs/config-file/config-reference).

### Host readiness and diagnostics

Run `python3 skills/agent/scripts/exec.py doctor` before choosing a managed host.
Add `--probe` to exercise the system bubblewrap helper on Linux with a five-second
timeout, read-only filesystem and isolated network. Neither command initializes
the runtime registry or changes host policy. `--codex PATH` selects the executable
to locate; this inventory does not prove its version or complete sandbox works.

| Host | Managed execution | Required action |
| --- | --- | --- |
| Linux, including Ubuntu | Requires `/proc` identity and usable containment/sandbox facilities | Inspect `doctor`; use `--probe` for system bubblewrap evidence. |
| macOS | Unsupported by this managed runtime | Use a supported Linux host; native Codex support is separate. |
| Native Windows | Unsupported by this managed runtime | Use a separately checked Linux host or WSL environment. |
| Other operating systems | Unsupported | Add and verify a process-identity/containment backend before claiming support. |

- Unsupported hosts return `managed_platform_unsupported` before runtime storage
  access or POSIX-only runtime imports. No backend or permission fallback is selected.
- `sandboxReadiness: unknown` is intentional: locating a binary, an enabled
  AppArmor setting, or a successful system helper probe is not a Codex sandbox pass.
  Codex may use a bundled helper, so missing system bubblewrap is not conclusive.
- Every managed attempt preflights the **selected Codex executable and policy**
  before launching the Agent: read the request and write inside the exact run
  directory. Record evidence as `executionPreflight`; failure ends the run before
  launch. Do not retry with broader permissions or substitute a host helper probe.
- An observed filesystem-helper initialization failure is reported as
  `sandbox_unavailable`, including nonzero exec exits and app-server error events.
  Unrelated command failures retain their original classification. A structured failed
  file change for the exact managed result path followed by a missing file reports
  `result_file_write_failed`; it does not infer a sandbox cause from Agent prose.
- On Linux, inspect security audit logs and container/namespace restrictions.
  AppArmor is one possible cause, not a universal Linux diagnosis. Host policy
  changes belong to the host administrator and are never applied automatically.
- Exit codes: `0` means inventory completed (or the requested helper probe passed),
  `1` means a required inspected prerequisite is absent or the probe failed/could
  not run, and `2` means the managed platform is unsupported. None certifies native
  execution on macOS/Windows; simulated platform tests establish diagnostics only.

### Relocation

1. Use `exec.py rebind --runtime-home HOME --project-id ID --from-root OLD --project-root NEW`.
2. Require matching old binding, an existing unregistered destination and no active runs.
3. Restart clients. Existing clients stay pinned and must fail on registry change.

- Rebinding preserves identity; it neither merges projects nor resolves conflicting histories.

## Managed execution

### Prompts and sessions

- Only `main`, `work`, `verification` roles exist; sources are `prompt/main.md`,
  `prompt/work.md`, `prompt/verification.md` relative to the Skill root.
- Every initial/resumed exec turn validates and injects the complete selected
  prompt as a tagged `codex exec` stdin block, not a platform system message.
- Use `scripts/exec.py` for delegated roles; Main may also be exec-hosted.
  Resume exact session IDs; no `resume --last` or concurrent turns per session.

### Run files and retries

- `runs/<run-id>/` owns request/state/heartbeat/events/response schema/result/receipt;
  keep operational data separate from Skills/project information.
- Pass large context/requests through validated run files. Reject traversal,
  symlinks and unexpected file types; publish atomically and bound event/stderr logs.
- Submit asynchronously; persist dispatch intent/tuple first. Reconcile ambiguous
  acknowledgement with the same dispatch ID, without replacement dispatch.
  Separate acceptance, startup, heartbeat and turn timeouts;
  distinguish durable acceptance, start, observed heartbeat and terminal completion.
- Pre-start retries are idempotent. After successful launch, missing start events
  are ambiguous; no automatic replay. External/irreversible retries need Human authority.

### CLI and receipts

- `scripts/exec.py`: `submit`, `send`, `status`, `result`, `inbox`, `list`,
  `cancel`, `reconcile`.
- `scripts/loop.py`: `start`, `status`, `reconcile` (one transition),
  `skip --actor human --authorization-reference REF --decision-evidence TEXT`.
  Missing skip evidence or non-Human actors fail closed. Timing and END follow
  [the Agent graph](../SKILL.md#roles-and-graph).
- Completed runs publish validated `receipt.json` beside `result.md`.
- Work receipts identify the request, changed paths and addressed finding IDs
  for revisions.
- Verification uses `--verified-work-run-id`; its receipt binds the exact Work
  run and original request. `pass` has no findings; `fail` has actionable findings.
- Exec owns process/session/run facts; loop alone owns transitions and END.

### Linux containment

#### Systemd backend

1. Check command features, responsive user manager, safe environment transfer and
   cgroup-v2 population access.
2. Use a unique transient service per run/attempt: Worker main process, Codex child,
   `Type=exec`, group termination, collection, safely transferable submitter environment,
   bounded TERM-to-KILL escalation.
3. Record backend/opaque containment identity by launch acknowledgement; query
   that binding before reconciliation/signalling.
4. Confirm cancellation from empty bound cgroup population, not service state or leader PID.

#### Fallback

- Without usable user systemd, retain startup barrier, private sessions/process
  groups and boot-ID/start-ticks checks. Fail closed on unverifiable identity;
  preserve conservative stale-run/non-replay behavior.
- Descendant containment is weaker. Systemd is optional; the adapter allows future
  backends but claims no Windows support.

## Capability bindings

### Authority and configuration

- MCP Tool owns discovery/lifecycle; readiness grants no execution authority.
  Agent binds authority/capabilities to requests/receipts. Preserve selected
  host/plugin/MCP/manifest authority; copy neither registry nor credentials.
- Individual runs: `exec.py --capability-binding-file`.
- Loops: separate `--work-capability-binding-file` and
  `--verification-capability-binding-file`; never forward bindings between roles.
- Strict versioned schema: 1–32 unique capability IDs, authority kind/reference,
  invocation route, exact target, allowed effects/scopes, nullable approval reference;
  no credential/token fields. Reject unknown fields and invalid bounds.

### Validation

1. Open without resolving/following file or parent symlinks. Unsupported traversal,
   unsafe parents, replacement races, non-regular files and oversized content fail closed.
2. Open final component nonblocking; verify a regular descriptor, then read bounded
   bytes from that same descriptor. FIFOs/sockets/devices cannot block dispatch.
3. Canonicalize/copy into the run; hash into the immutable dispatch tuple and expose
   canonical path/hash in status.
4. Require ordered `capabilityOutcomes`, one per binding: request hash, run ID,
   capability ID, authority, target and `succeeded`, `failed`, `unknown` or `not-invoked`.
5. Re-read/hash canonical bindings; reject omitted, reordered, widened or substituted outcomes.

## Legacy migration

### 1. Inventory and plan

- `runtime/migration.py` provides `inventory`, `plan`, `copy-request`, `copy`,
  `verify-eligible`, `activate`, `retire`.
- Pass each parent/plugin/extension/MCP project as a separate `--project-root`;
  nesting does not merge identities.
- Bind complete file/directory inventory, sizes/SHA-256, registry bindings and exact
  operational locator mapping. Mark malformed inactive records archive-only.
- `copy-request` binds independent backup and deterministic source/projection hashes
  before Work copies. Plans are data, not executable model output.

### 2. Copy and map

- Preserve legacy bytes, including requests/results/receipts/events, in the home
  archive and independent backup outside home/source projects. Only Agent runtime
  records receive operational projections.
- Documents/SQLite remain archived, never local domain backends. Human Specifications
  and historical Documents belong to MCP or selected archival authority, not this plugin.
  Never add raw Documents, untracked runtime, secrets or credential caches to Git.
- Refuse changed sources, unsafe traversal/links/special files, active/unverifiable
  boot-ID/start-ticks identities, populated containment, writer locks or conflicts.
- Journal copy intent; identical retries are supported. Check complete allowlisted
  archive/backup/projection/activation trees, including empty directories; reject
  foreign files and replacement inodes.
- Resolve only known JSON filesystem locator fields, including absent optional
  outputs, by longest root-bound prefix. Preserve historical request identity,
  receipt hashes, session/run/loop IDs, recipients, payload strings and outbox commands.
- `exec.py map-path --project-root PROJECT --path OLD_PATH` uses the cross-project
  manifest to return archive path/byte digest. Prompts describe this route;
  archives remain immutable and invalid records gain no fabricated completion.

### 3. Verify and activate

- `verify-eligible` proves byte eligibility only. Independent Verification reviews
  copied state, valid/invalid receipts, cross-project mapping, exact-session continuation,
  graph pass/fail/skip and reporting recovery.
- Activation requires a version-2 envelope naming actual completed managed Work and
  Verification states. Revalidate ownership, exact request/result/response/receipt
  schemas/hashes, terminal events, distinct sessions, strict pass receipt and exact
  plan/home/backup/source/projection binding. Unbound fields/filenames are insufficient.
- Publish operational projection with a recoverable journal; partial activation
  blocks use until recovery.

### 4. Retire

- Require exact already-authorized retirement reference and unchanged source/archive/
  backup/projection evidence. Recheck writer exclusion/allowlists on every retry;
  persist one inode-bound unlink/rmdir intent and reject foreign/replaced source/tombstones.
- Existing authorization needs actual verification evidence, not another permission request.
- Keep pinned bootstrap runtime/active records until Main transfers control and
  independent validation permits retirement.

### Authority

- Preserve [the Agent role boundaries](../SKILL.md#roles-and-graph) and
  [Convention domain authority](../../convention/references/agent-factory-core.md).
- Code changes/copies prove no physical migration, acceptance, cloud import,
  installation or deployment.

## Optional cloud reporting

- Follow [reporting.md](reporting.md) for role-specific configuration, outbox
  delivery, recovery and cloud reporting evidence.
