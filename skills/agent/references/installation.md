# Runtime Installation and Connection

- Initialization, permissions, host readiness and relocation of the local runtime.

<a id="installation-and-connection"></a>

<a id="initialization"></a>

## 1. Initialization

1. Initialize with `exec.py init --project-root PROJECT`; first submit and extension connection use the same
   helper. An installed entry is `python3 /absolute/installed/plugin/scripts/exec.py init --project-root /absolute/code/worktree`.
2. Inspect versioned locations/registrations with `location` and `projects`.
   `list`, capability inspection and status discovery never initialize missing
   storage.
3. Use the returned project identity and runtime location for subsequent commands.

- Marketplace installation runs no arbitrary post-install command; the manifest supplies
  no initialization hook and installation does not trust hooks.
- VS Code uses the workspace extension host's home, including SSH/containers, not the UI
  host's.

<a id="permissions"></a>

## 2. Permissions

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

## 3. Host readiness and diagnostics

- Run `python3 <plugin-root>/scripts/exec.py doctor` when first choosing a managed host,
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
| Native Windows (for example Git Bash) | Requires native Python 3.10+ (not MSYS2/Cygwin), kernel process identity and Job Objects | Inspect `doctor`; call `python` or `py -3` where `python3` is absent; validate the selected native Codex sandbox on the actual host. |
| Other operating systems | Unsupported | Use a supported host. |

- macOS `doctor --probe` reports the Linux bubblewrap probe as `not-applicable`; it reads native
  identity availability and leaves sandbox readiness unknown.
  - For custom `AGENT_FACTORY_HOME`, use an absolute path with no symlink ancestors (for example,
    `/private/tmp/...` rather than the macOS `/tmp` alias).
  - The runtime does not weaken its path checks to accommodate aliases.
- Windows identifies a process by PID plus kernel creation time and contains it in a private
  kill-on-close Job Object owned by the bootstrap root.
  - Background workers and loop drivers break away from the caller's job so they outlive it;
    if an outer job forbids breakaway they stay nested and end with their caller.
  - Stops terminate immediately; there is no POSIX `SIGTERM` grace period.
  - POSIX owner/mode checks do not apply; runtime files rely on the per-user profile ACL.
  - npm `codex.cmd` shims resolve to the vendored native `codex.exe` when present.
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

## 4. Relocation

1. Use `exec.py rebind --runtime-home HOME --project-id ID --from-root OLD --project-root NEW`.
2. Require matching old binding, an existing unregistered destination and no active
   runs.
3. Restart clients. Existing clients stay pinned and must fail on registry change.

- Rebinding preserves identity; it neither merges projects nor resolves conflicting
  histories.
