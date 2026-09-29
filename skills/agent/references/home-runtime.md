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

<a id="linux-containment"></a>

## 2. Cancellation and containment

<a id="systemd-backend"></a>

### 2.1. Managed cancellation

- Cancel through `exec.py cancel` with the exact Agent and run identity.
- Check the resulting status; request acceptance alone does not prove process termination.
- Do not signal a reused PID or manipulate runtime containment records directly.

<a id="fallback"></a>

### 2.2. Containment limitations

- `weakerDescendantContainment: true` means detached descendants may escape
  process-group cancellation. Report this limitation when termination is uncertain.
- This flag does not widen filesystem or network permissions.
- Preserve ambiguous runs and reconcile their status before retrying work.

<a id="capability-bindings"></a>

## 3. Capability bindings

<a id="authority-and-configuration"></a>

### 3.1. Authority and configuration

- Bind allowed capabilities and effects to the request and receipt. Capability availability
  grants no additional execution authority; keep credentials outside binding files.
- Individual runs: `exec.py --capability-binding-file`.
- Loops: separate `--work-capability-binding-file` and `--verification-capability-binding-file`; never forward bindings between roles.
- Strict versioned schema: 1–32 unique capability IDs, authority kind/reference,
  invocation route, exact target, allowed effects/scopes, nullable approval reference;
  no credential/token fields. Reject unknown fields and invalid bounds.

<a id="validation"></a>

### 3.2. Validation

- Supply regular, bounded JSON files without symlinks or credentials.
- Use the canonical binding path and hash returned by the runtime.
- Report ordered `capabilityOutcomes`, one per binding, with request hash, run ID,
  capability ID, authority, target and `succeeded`, `failed`, `unknown` or `not-invoked`.
- Do not omit, reorder, widen or substitute bound capabilities.

<a id="legacy-migration"></a>

## 4. Legacy records

- Preserve old runtime and document records; initialization does not authorize migration
  or deletion.
- For an already migrated path, use `exec.py map-path --project-root PROJECT --path OLD_PATH`
  to resolve its archive path and byte digest.
- Keep archives immutable. An archived or malformed record is not proof of completion.
- Resolve projects separately; nested checkouts do not share an identity automatically.
- Report an unavailable mapping or recovery operation instead of editing runtime state.

<a id="progress-projection"></a>

## 5. Progress projection and repair

- Loop `state.json` and validated run receipts retain execution authority. Every saved
  transition increments `stateRevision` and publishes `progress.md`, `progress-state.json`
  and an immutable `progress-history/revision-<N>.json` beneath the same loop directory.
  These files are derived views, not an event-sourced execution log or new task authority.
- `loop.py status` exposes `progressPath`, `stateRevision` and `progressProjection`
  (`current`, `stale` or `missing`). Freshness compares the committed state with the
  generated view and its revision snapshot. It does not assert that a live child has
  finished or that an unprocessed receipt passed.
- Link the returned progress path from the contract's human-maintained summary. Follow
  [Progress writing](../../document/references/progress.md) for that document's ownership.
  Preserve contract versions, task IDs and accepted run bindings in both views.
- Projection failures are logged and do not block committed execution. Repair the
  current view without launching or resuming agents:

  ```sh
  python3 <plugin-root>/scripts/loop.py refresh-progress \
    --project-root PROJECT --work-agent WORK_AGENT --loop-id LOOP_ID
  ```

- Repair holds the loop lock, leaves `state.json` unchanged and returns
  `projection.status` (`current` or `stale`) plus any error. Repeating repair is
  idempotent. Conflicting history is preserved and reported; investigate it rather
  than deleting evidence. An interruption can leave missing intermediate projection
  revisions; repair cannot reconstruct them or authorize replaying completed work.
- Work-only completion, receipt-processed Verification completion, Human skip,
  blocked work and cancellation remain distinct. Later direct work never rewrites
  the cancelled loop's historical outcome.
