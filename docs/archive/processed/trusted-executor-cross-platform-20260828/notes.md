# Trusted executor and reproducibility exploration

## Information stage, question, and boundary

This document is **processed Explorer information**, not accepted or refined
project truth. It investigates an implementable trusted-execution design for
Agent Factory. It does not choose acceptance, release priority, supported-OS
policy, key custody, or residual-risk tolerance for the Human.

The delegated scope covers signed executor evidence, a hermetic execution
manifest, content-addressed artifacts, Linux cgroup v2 plus pidfd, Windows Job
Objects, macOS containment, chaos tests, and repeat-build CI. Repository tests
were inspected but not run. The request authorized read-only capability probes
and bounded experiments only in this Explorer workspace; canonical project files
were not edited by this exploration.

Retrieval context: repository and local runtime inspected on 2026-08-28 KST;
web sources retrieved on 2026-08-28. Direct links below are primary or official
project documentation where available.

## Executive conclusion

The design is implementable if it treats four guarantees as separate and
independently verifiable:

1. **Input closure**: a canonical manifest identifies every permitted build
   influence, rejects undeclared inputs, and binds source, dependencies,
   toolchain, image, environment, command, and nondeterminism policies.
2. **Execution containment**: an OS backend owns a race-free process-tree
   lifetime and resource limits. Containment is not by itself hermeticity.
3. **Artifact integrity**: a deterministic, path-aware artifact index is sealed
   by digest after the process tree is empty; verification re-hashes bytes.
4. **Evidence authenticity**: a trusted control plane, inaccessible to the
   workload, signs an in-toto/SLSA-shaped statement binding manifest,
   execution, and artifact digests.

Linux can provide the strongest local backend by combining a delegated cgroup
v2 subtree with pidfds and a filesystem/network isolation mechanism. Windows
Job Objects give robust process-tree and resource containment when the target is
created suspended and assigned before resume. macOS has no direct Job Object or
cgroup equivalent exposed to an ordinary CLI: a process-group backend is useful
for best-effort cleanup, while a stronger product requires a signed App Sandbox
and preferably an XPC service. Therefore the backend must publish an explicit
`capabilityGrade`; it must never claim equivalent hermeticity across platforms.

Cryptographic signing proves who made a claim and whether it changed. It does
not prove the claim was accurate. SLSA requires stronger levels to generate
provenance in a trusted control plane and keep signing material out of tenant
build steps. The executor architecture must enforce that split rather than
letting the executed command write or sign its own evidence.

## Observed repository and runtime facts

### Repository observations

- The inspected revision was `e57f78691c01c9f4dcccb4678f0036b310fe8124`,
  but the working tree was already materially dirty and contained untracked
  Agent Factory work. This is important: a commit ID alone does not identify the
  code currently being inspected or executed.
- The public runtime is currently concentrated in
  `skills/agent/scripts/agent_exec.py`; no trusted-executor package or execution
  manifest schema exists.
- The current Linux-first implementation starts a bootstrap with
  `start_new_session=True`, checks that leader PID equals process-group ID,
  records `{pid, bootId, startTicks}` from `/proc`, and signals a verified
  process group TERM then KILL. It fails closed on unverifiable identity.
- Current run state hashes the request, limits `events.jsonl` and `stderr.log`,
  atomically clears the active Codex identity on terminal transition, and
  refuses replay after an ambiguous or observed launch. Those are useful
  foundations for a trusted executor journal, but they do not seal inputs,
  outputs, or signed provenance.
- Current process containment is Linux `/proc` plus process groups. There is no
  cgroup, pidfd, Windows Job Object, or macOS-specific backend.
- `tests/test_agent_exec.py` contains 26 test methods. Relevant current coverage
  includes exact `/proc` identity and PID-reuse detection, nested process-group
  termination, leader-exit cleanup, bootstrap-barrier failures, log caps,
  atomic terminal identity clearing, and cancellation refusal on identity
  mismatch. These are unit/integration-shaped tests, not signed evidence,
  hermeticity, artifact sealing, or repeated-source reproducibility tests.
- No `.github` workflow was present in the inspected file inventory.
- No tracked submodule gitlinks or `.gitmodules` were observed.
- No tracked package-manager lockfile or requirements file was observed. The
  runtime imports only the Python standard library, but the Python interpreter,
  Codex executable, OS, and runner utilities remain undeclared toolchain inputs.
- `.gitignore` exists. `git ls-files --others --ignored --exclude-standard`
  showed extensive ignored runtime material. A manifest that silently hashes
  the working directory would therefore be neither small nor policy-stable.

### Authorized runtime probes and bounded experiment

Observed environment:

- Linux `7.0.0-29-generic`, x86-64, Python `3.12.3`.
- `/sys/fs/cgroup` reported `cgroup2fs`; `/proc/self/cgroup` reported
  `0::/user.slice/user-1000.slice/session-1674.scope`.
- Root cgroup controllers visible to the session were `cpuset cpu io memory
  hugetlb pids rdma misc dmem`, but `/sys/fs/cgroup` was not writable by this
  user. This means a backend cannot assume direct root-level delegation merely
  because cgroup v2 is mounted. It must detect a writable delegated subtree or
  obtain one from a service manager/privileged helper.
- `bwrap` and `unshare` were installed; `cosign` was not found; `gh` was found.

Bounded pidfd experiment:

```text
method: spawn a Python child sleeping for 30 seconds; os.pidfd_open(child_pid);
        signal.pidfd_send_signal(pidfd, SIGTERM); wait up to 3 seconds
observation: pidfd_open succeeded; Python exposed pidfd_send_signal;
             child return code was -15
limitation: proves only host API availability for one child, not cgroup
            delegation, descendant containment, privilege isolation, or CI hosts
```

No repository test suite, build, server, or canonical-file mutation was run.

## Primary-source constraints

### Provenance and signatures

- SLSA defines provenance as verifiable information about where, when, and how
  an artifact was produced, and recommends cryptographic digests for subjects:
  <https://slsa.dev/spec/v1.2/provenance> and
  <https://slsa.dev/spec/v1.2/build-requirements>.
- SLSA Build L2 authenticity requires signature verification and a recognizable
  builder. L3 requires provenance fields to be generated or verified by the
  trusted control plane, with signing secrets inaccessible to user-defined build
  steps. SLSA also explicitly distinguishes isolation from hermetic/no-network
  execution; the latter is not implied by Build L3:
  <https://slsa.dev/spec/v1.2/build-requirements>.
- SLSA verification checks the envelope signature, artifact/subject digest,
  builder identity, `buildType`, and recognized `externalParameters`; unknown
  external parameters should fail verification:
  <https://slsa.dev/spec/v1.2/verifying-artifacts>.
- The in-toto Statement v1 binds a typed predicate to immutable subjects by
  digest: <https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md>.
  Its envelope specification recommends DSSE and authenticates `payloadType`
  with the payload:
  <https://github.com/in-toto/attestation/blob/main/spec/v1/envelope.md>.
- Sigstore Cosign can sign and verify arbitrary blobs. Its recommended bundle
  carries signature, certificate, and transparency-log proof for the public
  Sigstore service: <https://docs.sigstore.dev/cosign/signing/signing_with_blobs/>
  and <https://docs.sigstore.dev/cosign/verifying/verify/>.
- GitHub artifact attestations produce signed provenance and can be verified by
  `gh attestation verify`:
  <https://docs.github.com/en/actions/concepts/security/artifact-attestations>
  and
  <https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations>.
  GitHub documents that its Sigstore instance differs from the public-good
  instance and has no transparency log, so the trust profile must identify
  which service produced a bundle.

**Inference:** use an in-toto Statement/SLSA provenance predicate as the
interoperable outer evidence, but retain an Agent Factory predicate for exact
containment observations and manifest bindings that generic SLSA fields do not
model. Signing must occur after execution in the executor control plane.

### Linux cgroup v2 and pidfd

- cgroup v2 organizes processes hierarchically and distributes resources.
  Processes written to `cgroup.procs` bring their threads; children are born in
  the parent's current cgroup. Delegation restricts movement across the
  delegated boundary:
  <https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html>.
- A delegated subtree requires explicit write permissions or cgroup namespace
  delegation. Controllers are top-down, and domain controllers are constrained
  by the no-internal-process rule. A nonprivileged executor must detect and
  report delegation instead of trying unsafe fallbacks.
- `cgroup.kill` sends SIGKILL to the complete subtree, handles concurrent forks,
  and is protected against migrations. `pids.max`, `memory.max`, and `cpu.max`
  provide hard process, memory, and CPU-bandwidth limits where delegated and
  enabled. `cgroup.events`/`populated` is the right emptiness observation:
  <https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html>.
- A pidfd is a stable reference to a specific process and avoids the recycled-
  PID race of `kill(2)`. It can be polled for process exit and targeted with
  `pidfd_send_signal(2)`:
  <https://man7.org/linux/man-pages/man2/pidfd_open.2.html> and
  <https://man7.org/linux/man-pages/man2/pidfd_send_signal.2.html>.
- `clone3(CLONE_PIDFD|CLONE_INTO_CGROUP)` can create the child with both a pidfd
  and initial cgroup placement, eliminating the fork-before-migration window:
  <https://man7.org/linux/man-pages/man2/clone.2.html>.

**Inference:** use cgroup membership as the process-tree ownership primitive and
pidfd as the leader identity/liveness primitive. A pidfd alone does not refer to
all descendants, and a process group can be escaped with a new session; neither
substitutes for `cgroup.kill`.

### Windows Job Objects

- A Job Object groups processes, applies resource limits, supports nested jobs
  on Windows 8/Server 2012 and later, and can terminate the tree with
  `TerminateJobObject`. `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` terminates all
  associated processes when the last job handle closes:
  <https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects> and
  <https://learn.microsoft.com/en-us/windows/win32/procthread/nested-jobs>.
- `AssignProcessToJobObject` applies job limits. Creating the child with
  `CREATE_SUSPENDED`, assigning it, then resuming avoids user code running before
  association:
  <https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject>.
- Extended/basic limits cover job memory, per-process memory, active process
  count, CPU time, and related controls:
  <https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information>.
- Completion-port notifications provide lifecycle and limit events, but most
  are notifications rather than guaranteed delivery. PID-bearing messages are
  vulnerable to PID reuse unless the executor retains an open process handle:
  <https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_associate_completion_port>.

**Inference:** the durable identity is the process handle plus Job handle, not a
PID. Set limits and completion port while the Job is inactive; create suspended,
assign, record handles, and only then resume. Do not enable breakaway flags.

### macOS

- Foundation `Process` inherits environment from its launcher and can monitor a
  subprocess. Apple's docs say sandboxed child processes inherit the parent's
  sandbox and recommend XPC services for different entitlements:
  <https://developer.apple.com/documentation/foundation/process>.
- App Sandbox inheritance requires code signing and exact entitlements;
  inherited static rights do not include dynamically granted rights. Apple says
  XPC is preferred for privilege separation:
  <https://developer.apple.com/library/archive/documentation/Miscellaneous/Reference/EntitlementKeyReference/Chapters/EnablingAppSandbox.html>.
- XPC services are launchd-managed, tied to a client lifetime, and support
  privilege isolation:
  <https://developer.apple.com/documentation/xpc>.
- macOS process groups distribute signals, but Apple's published interface does
  not make them a non-escapable resource container:
  <https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/getpgrp.2.html>.
- Apple warns that inherited file descriptors and environment variables,
  including dynamic-loader variables, can become attack inputs:
  <https://developer.apple.com/library/archive/documentation/Security/Conceptual/SecureCodingGuide/Articles/AccessControl.html>.

**Inference:** an ordinary Python CLI can implement `setsid`/process-group
cleanup plus `setrlimit` as a compatibility backend, but must label it
`containmentGrade: best-effort-tree`; descendants can detach. Strong macOS
isolation requires a separately signed helper/XPC product and cannot be inferred
from the present plugin's Python script.

### Source closure, runner images, and reproducibility

- `git ls-files` can enumerate tracked files and separately enumerate untracked
  and ignored files. `--exclude-standard` includes repository, info, and global
  excludes; global ignores are host-specific and therefore must not silently
  define a portable source closure: <https://git-scm.com/docs/git-ls-files>.
- `.gitmodules` defines submodule paths/URLs and ignore behavior can hide dirty
  state, so the trusted manifest must inspect gitlinks and exact submodule HEADs
  rather than trusting default status output: <https://git-scm.com/docs/gitmodules>.
- GitHub says hosted runner software is updated weekly and runner image labels
  can migrate. Exact build logs expose image versions and Ubuntu/Windows/macOS
  image releases provide SBOMs:
  <https://docs.github.com/en/actions/concepts/runners/github-hosted-runners>,
  <https://docs.github.com/en/actions/reference/security/secure-use>, and
  <https://github.com/actions/runner-images>.
- GitHub recommends full-length commit SHAs because that is the immutable way to
  pin Actions: <https://docs.github.com/en/actions/reference/security/secure-use>.
- `SOURCE_DATE_EPOCH` gives build systems a stable source timestamp, but it does
  not virtualize all clocks:
  <https://reproducible-builds.org/docs/source-date-epoch/>.

**Inference:** `ubuntu-latest`, `windows-latest`, and `macos-latest` are invalid
hermetic image identities. Even versioned hosted labels are mutable. A run must
record the exact observed runner image release/SBOM digest, while high-assurance
Linux uses an OCI image pinned by digest. Equivalent Windows/macOS guarantees
need immutable self-hosted VM image digests or must report weaker capability.

## Proposed architecture

Keep `agent_exec.py` as the managed-session front door, but move trusted
execution into a testable package instead of further growing the monolith:

```text
skills/agent/scripts/
├── agent_exec.py                    # existing session/run orchestration
└── trusted_executor/
    ├── __init__.py
    ├── cli.py                       # prepare/run/seal/attest/verify/probe
    ├── schema.py                    # strict schema + semantic validation
    ├── source.py                    # Git snapshot and ignored-input policy
    ├── manifest.py                  # canonical bytes and executionHash
    ├── journal.py                   # crash-safe phase transitions
    ├── artifacts.py                 # descriptor-safe traversal and CAS
    ├── provenance.py                # in-toto/SLSA + AF predicate
    ├── signing.py                   # provider interface, never workload-loaded
    └── backends/
        ├── base.py
        ├── linux_cgroup_pidfd.py
        ├── windows_job.py
        └── macos_process.py
```

Suggested run files, all below the existing per-run directory:

```text
execution.manifest.json    # immutable canonical input contract
execution.state.json       # journal, not signed until terminal
artifact.index.json        # deterministic path/type/mode/size/digest list
provenance.statement.json  # in-toto Statement payload
provenance.bundle.json     # DSSE/Sigstore or configured signature bundle
verification.json          # verifier result and policy identity
```

The runtime should bind their absolute paths and SHA-256 values in `state.json`.
Atomic publication should reuse the current safe-file patterns, upgraded to
directory-fd/openat-style traversal where artifact races matter.

### Control-plane sequence

1. `prepare`: validate strict schema with unknown keys rejected; resolve source
   into a new immutable snapshot/CAS; verify every declared digest; create an
   isolated empty output directory; compute `executionHash` over canonical
   manifest bytes.
2. `contain`: acquire OS container, configure limits, attach monitoring, and
   publish journal state `contained` before workload release.
3. `launch`: start at a barrier (Linux clone-into-cgroup or bootstrap attached
   before exec; Windows suspended and assigned to Job; macOS process group),
   persist stable OS handles/identity, then release.
4. `observe`: keep signing provider absent from child environment and handles;
   collect exit/resource/container events into a bounded log whose digest is
   later attested.
5. `quiesce`: wait for leader and full container emptiness. On timeout/cancel,
   terminate the complete container, wait boundedly, and fail if emptiness
   cannot be proven.
6. `seal`: revoke output writes by unmount/read-only transition where available;
   traverse without following symlinks; hash entries; atomically publish index
   and CAS blobs. Any mutation during sealing fails the run.
7. `attest`: trusted control plane constructs statement from its observations,
   not workload-provided JSON, then invokes isolated KMS/Sigstore/GitHub OIDC
   signing. Atomically publish bundle last.
8. `verify`: independently validate schema, signature/trust identity, manifest
   digest, artifact index root, every artifact byte, and expected builder/
   policy. Never trust `status: completed` without these checks.

### Capability contract

Every backend returns machine-readable capabilities rather than a Boolean:

```json
{
  "processTree": "kernel-enforced|best-effort",
  "stableLeaderIdentity": "pidfd|handle|pid-start-time",
  "resourceLimits": ["cpu", "memory", "pids"],
  "filesystemIsolation": "mount-namespace|app-sandbox|none",
  "networkIsolation": "namespace-firewall|app-sandbox|none",
  "clockControl": "namespace-shim|env-only|none",
  "randomnessControl": "injected-api|none",
  "grade": "hermetic|contained|best-effort-tree"
}
```

Manifest requirements are matched against observed capabilities before launch.
Unsupported required controls fail `capability_unsatisfied`; they never degrade
silently.

## Hermetic execution manifest v1

Use UTF-8 JSON with an exact schema and no floats. Compute
`executionHash = sha256(canonicalManifestBytes)`. RFC 8785 JCS is an available
canonicalization profile (<https://www.rfc-editor.org/rfc/rfc8785.html>), but
DSSE should sign the exact serialized statement bytes so signature security does
not depend on consumers independently recreating JSON formatting.

Proposed semantic shape (illustrative, not accepted schema):

```json
{
  "schemaVersion": "1.0.0",
  "kind": "agent-factory-execution",
  "source": {
    "repository": "https://example.invalid/org/repo",
    "commit": "40-hex-object-id",
    "tree": "git-object-id",
    "snapshot": {"algorithm": "sha256", "digest": "..."},
    "worktreePolicy": "committed-only",
    "untrackedPolicy": "reject",
    "ignoredPolicy": "exclude-and-unmount",
    "submodules": []
  },
  "dependencies": {
    "lockfiles": [],
    "install": {"argv": [], "network": "deny"}
  },
  "toolchain": {
    "executables": [{"name": "python", "version": "3.12.3", "sha256": "..."}],
    "runnerImage": {"kind": "oci", "digest": "sha256:...", "sbomDigest": "sha256:..."}
  },
  "environment": {
    "clear": true,
    "allow": {"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC", "SOURCE_DATE_EPOCH": "..."},
    "forbidPrefixes": ["LD_", "DYLD_", "PYTHON", "NODE_OPTIONS"]
  },
  "command": {
    "argv": ["python", "-m", "..."],
    "cwd": ".",
    "stdin": {"mode": "closed"},
    "umask": "0022"
  },
  "policy": {
    "network": {"mode": "deny"},
    "time": {"mode": "fixed", "unixSeconds": 0},
    "randomness": {"mode": "deterministic", "seedDigest": "sha256:..."},
    "filesystem": {"source": "read-only", "output": "write-only-output"},
    "limits": {"wallSeconds": 300, "cpuMicrosPerPeriod": "100000/100000", "memoryBytes": 1073741824, "pids": 128}
  },
  "outputs": {"root": "out", "symlinks": "reject", "specialFiles": "reject"},
  "builder": {"id": "https://agent-factory.example/trusted-executor/v1", "backendRequired": "hermetic"}
}
```

Semantic rules:

- **Source**: default to committed-only. Materialize from Git objects, not the
  mutable working tree. A `tracked-worktree` option may exist only when every
  path and byte is snapshotted and its snapshot digest becomes the source
  identity. Never mix commit identity with undeclared dirty bytes.
- **Ignored inputs**: portable options are `reject`, `exclude-and-unmount`, or
  `include-by-digest`. Do not let global Git ignore configuration silently
  choose inputs. Record repository ignore-file digests separately as policy
  material. `exclude-and-unmount` is the hermetic default.
- **Submodules**: enumerate gitlinks recursively with path, canonical URL,
  recorded commit, resolved tree/snapshot digest, and dirty/untracked policy.
  Fail if missing, detached at a different commit, URL-rewritten without policy,
  or recursively undeclared.
- **Lockfiles**: list exact path, ecosystem, SHA-256, and required frozen/offline
  installer mode. Fail if a declared ecosystem has no accepted lockfile. An
  empty list is valid only for a declared no-external-dependency build.
- **Toolchain**: digest executables and configuration, record semantic versions,
  and bind an immutable runner image digest and SBOM digest. A tag or `-latest`
  label cannot satisfy `backendRequired: hermetic`.
- **Environment**: start empty and set exact allowlisted values. Locale, timezone,
  path, home/temp directories, language runtime variables, dynamic loader
  variables, and certificate stores are inputs. Secrets are prohibited from a
  reproducible job; a separate nonreproducible profile may bind secret identity
  (never plaintext) and must report the limitation.
- **Command**: argv array, no implicit shell; exact cwd; closed or digest-bound
  stdin; fixed umask. Resolve executable within the sealed toolchain, not host
  `PATH` lookup.
- **Network**: deny by default at the backend. An allowlist must record protocol,
  endpoint identity, DNS policy, and fetched content digest; otherwise the run
  cannot claim hermetic/reproducible status.
- **Time**: fixed `SOURCE_DATE_EPOCH`, UTC, normalized output mtimes. Environment
  variables do not stop direct wall-clock syscalls; a strong claim requires
  time namespace, virtualization, or a declared deterministic shim.
- **Randomness**: a seed variable does not control `/dev/urandom`, hardware RNG,
  or library behavior. A strong claim requires a controlled entropy interface
  or isolation layer. Seed material should be secret only if unpredictability,
  rather than reproducibility, is required; those goals conflict.

## Artifact sealing and verification

Define `artifact.index.json` with sorted normalized relative paths. Each entry
contains type (`file` or permitted `symlink`), path as UTF-8/NFC, executable bit
or normalized mode, byte size, and SHA-256. Reject absolute paths, `..`, control
characters, duplicate case-folded names for cross-platform sets, devices,
FIFOs, sockets, hard links unless explicitly modeled, and symlinks by default.

Compute leaf bytes with unambiguous length-prefixing, for example:

```text
leaf = SHA256("AF-ARTIFACT-v1\0" || len(path) || path || type || mode || size || contentSha256)
root = SHA256("AF-ARTIFACT-SET-v1\0" || leaf_1 || ... || leaf_n)
```

The index itself is canonicalized and hashed. Store blobs at
`cas/sha256/<first-two>/<digest>` with create-exclusive/no-follow semantics,
verify after copy, then rename atomically. A CAS path is an optimization, not a
trust signal; verification always hashes bytes.

Seal only after the OS container is proven empty. Open the output root once,
walk relative to a directory handle, do not follow links, compare pre/post
metadata around each read, and fail on replacement or mutation. Where the
platform supports it, move output to a read-only mount before traversal. Never
sign a pathname before hashing its opened file.

Verification order:

1. parse strict schemas and enforce size/count/path bounds;
2. validate trust root, certificate identity/issuer, signature, and freshness or
   transparency proof according to the signing profile;
3. ensure statement subject contains the artifact-set root and predicate binds
   exact `executionHash`, builder ID, backend capability digest, and journal log
   digest;
4. recompute manifest digest from exact bytes;
5. recompute every artifact digest and set root;
6. evaluate expected source, builder, command/policy, and allowed external
   parameters; reject unknown parameters;
7. report policy verification separately from cryptographic validity.

## Evidence and signing profile

Use an in-toto Statement v1 whose subjects include both the artifact set and,
optionally, individually distributed artifacts. Predicate type should be a
versioned Agent Factory URI. The predicate can embed or reference a SLSA
Provenance v1 mapping:

- `buildDefinition.buildType`: stable Agent Factory executor v1 URI;
- `externalParameters`: source identity plus human-selected manifest reference;
- `internalParameters`: control-plane-only run ID, backend selection, policy;
- `resolvedDependencies`: source snapshot, submodules, lockfiles, toolchain,
  image/SBOM;
- `runDetails.builder.id`: exact trusted executor identity;
- `runDetails.metadata`: invocation/start/finish and completeness flags;
- Agent Factory extension: `executionHash`, capability digest, terminal journal
  digest, exit status, termination cause, artifact index digest/root.

Signing provider interface:

- `sigstore-keyless`: ephemeral key via workload-identity/OIDC, Fulcio cert and
  Rekor proof; verifier pins issuer and certificate identity.
- `github-attestation`: GitHub OIDC/attestation action; verifier pins repository,
  workflow reference, and owner. Pin every action by full commit SHA.
- `kms-key`: asymmetric KMS signing; evidence includes key resource/version and
  algorithm. Rotation and revocation policy are external trust configuration.
- `development-key`: local file key, always marks `trustProfile: development`
  and cannot satisfy release policy.

The private key or OIDC token must never enter the child environment, filesystem,
inherited handles/file descriptors, or logs. Separate builder identity from the
Human/Agent request identity. Multiple signatures may be useful for independent
builder and release approval, but the executor must not infer that signature as
Human acceptance.

## OS backend designs

### Linux: cgroup v2 + pidfd

Required preflight: Linux, unified cgroup v2, writable delegated subtree,
required controllers enabled by ancestors, `cgroup.kill` availability, pidfd
syscalls, and filesystem/network isolation provider. Record kernel release,
cgroup mount identity, delegated path, controller set, and isolation provider.

Launch design:

1. create per-attempt domain cgroup below the delegated executor subtree;
2. configure `pids.max`, `memory.max`, `memory.oom.group=1`, and `cpu.max`; record
   values read back from kernel;
3. prefer a small native launcher using `clone3(CLONE_PIDFD|CLONE_INTO_CGROUP)`;
   otherwise use a stop/barrier bootstrap, attach its PID to `cgroup.procs`,
   verify `/proc/<pid>/cgroup`, obtain pidfd, then release before exec;
4. poll pidfd for leader exit and `cgroup.events` for subtree population;
5. TERM the pidfd leader for graceful shutdown where appropriate, then write
   `1` to `cgroup.kill` for complete forced cleanup; wait for `populated 0`;
6. collect `cpu.stat`, `memory.events`, `memory.peak`, `pids.events`, exit status,
   and OOM evidence before removing the empty cgroup.

Keep boot ID/start ticks as diagnostic compatibility fields, but use pidfd for
live identity. Persisting a numeric pidfd across a supervisor crash is not
enough because file descriptors are process-local. Crash recovery should use
the cgroup path plus a privileged long-lived broker or fail closed and kill the
known cgroup; it must not reconstruct identity from PID alone.

cgroup is resource/process containment, not filesystem or network isolation.
For `hermetic`, pair it with a mount/user/network namespace provider (for
example a carefully configured bubblewrap/container) using read-only source and
toolchain, tmpfs scratch, dedicated output, no host network, and closed inherited
FDs. Record the provider binary/image digest and actual namespace/cgroup IDs.

### Windows: Job Object

Use a native helper because Python's standard library does not expose the full
Job API. Hold Job and process handles in a supervisor/broker with restricted
ACLs. Create an unnamed Job, set completion port while inactive, enable
`KILL_ON_JOB_CLOSE`, active-process/memory/CPU limits, and explicitly prohibit
breakaway. Create target with `CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT`
and an explicit handle list; assign to Job; persist control-plane journal; then
resume the primary thread.

Wait on the process handle and query Job accounting. Treat completion messages
as observations, not the sole truth; query active process count and retain
handles because message PIDs can be reused. Cancellation uses
`TerminateJobObject`; successful quiescence requires active process count zero.
Nested-host constraints must be probed. If assignment fails because the runner's
parent Job topology is incompatible, report `job_assignment_unsupported`; do
not fall back silently.

Job Objects do not provide filesystem/network hermeticity. Strong Windows runs
need an ephemeral immutable VM/container plus firewall/network policy, read-only
source ACLs, dedicated output ACLs, explicit environment/handle inheritance,
and image identity. Publish `contained` rather than `hermetic` when those are
absent.

### macOS: compatibility and strong profiles

Compatibility backend: spawn with a new process group/session, explicit empty
environment, closed FDs, `setrlimit`, and a startup barrier. Store PID plus
start-time/audit observations where available. Signal the group and enumerate
descendants for diagnostics, but publish `best-effort-tree`; child code may
detach into another session and resource limits do not form a non-escapable
tree container.

Strong profile (separate product work): a code-signed, sandboxed executor/XPC
service with minimal entitlements, client code-signing requirements, explicit
file extensions/access, no network entitlement for network-denied jobs, and
launchd-managed lifetime. Even then, validate whether the desired arbitrary
tool execution model is compatible with App Sandbox and code-signing rules.
This cannot be promised by merely adding Python branches.

For CI, an ephemeral macOS VM runner with image identity and external supervisor
can improve environment freshness, but it does not convert process groups into
kernel Job Objects. State that limitation in evidence.

## CLI proposal

Extend the managed runtime without changing its asynchronous envelope:

```text
agent_exec.py probe-executor --backend auto
agent_exec.py prepare-execution --manifest FILE
agent_exec.py execute --manifest FILE --signing-profile PROFILE
agent_exec.py seal --run-id RUN_ID                 # recovery/admin, only if quiescent
agent_exec.py verify-execution --bundle FILE --artifact-root DIR --policy FILE
```

`execute` should normally own prepare through attest atomically. Split commands
exist for diagnostics/recovery and enforce journal preconditions. Stable errors:

```text
manifest_invalid, undeclared_input, dirty_source, submodule_mismatch,
lockfile_missing, toolchain_mismatch, image_identity_unpinned,
capability_unsatisfied, containment_start_failed, containment_escape_detected,
process_identity_lost, resource_limit_exceeded, network_policy_violation,
output_not_quiescent, artifact_mutated, artifact_path_invalid,
artifact_digest_mismatch, signing_identity_unavailable, signing_failed,
signature_invalid, provenance_policy_mismatch, reproducibility_mismatch
```

`agent_exec submit/send` can accept `--execution-manifest` and
`--signing-profile`; existing sandbox choice remains distinct and must not be
renamed as hermeticity. Terminal state adds evidence paths/digests only after
verification succeeds. A run can complete execution but fail attestation; its
overall trusted-execution status is failed, while raw observations remain for
diagnosis.

## Chaos and adversarial test plan

All destructive signals and mutations target only temporary per-test fixtures.
Each test asserts both stable error and absence of collateral signaling/writes.

| ID | Fault | Method | Required invariant |
| --- | --- | --- | --- |
| CR-01 | supervisor crash before launch | kill after `prepared` journal | exact run is safely resumable because no workload launch occurred |
| CR-02 | crash after launch before start event | kill at launch boundary | run is ambiguous/non-replayable; container is reconciled or failed closed |
| CR-03 | crash during sealing | kill after first CAS blob | no signature exists; restart re-hashes from quiescent output or fails |
| CR-04 | crash after signature temp write | kill before atomic rename | verifier sees no terminal bundle; temp file is ignored |
| PID-01 | PID reuse | inject stale PID/start identity; create unrelated process | no signal reaches unrelated process |
| PID-02 | Linux leader exits, grandchild lives | double-fork/setsid child | cgroup remains populated and `cgroup.kill` removes only run subtree |
| WIN-01 | child rapidly forks/exits | completion-port stress | Job active-count/handles establish truth despite missed notifications |
| MAC-01 | child calls `setsid` | compatibility backend | test exposes limitation and grade never claims kernel tree containment |
| ART-01 | mutate file while sealing | synchronized writer changes bytes/rename | seal fails `artifact_mutated`; no attestation |
| ART-02 | replace path with symlink | rename race to outside fixture | no outside read; `artifact_path_invalid`/mutation failure |
| ART-03 | mutate after sealing | flip one byte in distributed copy | independent verify fails digest/root |
| SIG-01 | forge signature | alter DSSE signature | cryptographic verification fails |
| SIG-02 | valid signature, wrong identity | sign with untrusted test key/OIDC subject | policy verification fails |
| SIG-03 | splice artifact/statement | pair valid bundle with other artifact | subject digest mismatch |
| ENV-01 | undeclared env mutation | vary `HOME`, locale, TZ, loader/runtime vars | child sees only allowlist; executionHash unchanged or launch rejected |
| ENV-02 | time mutation | vary host time/timezone | normalized artifact repeats or capability reports insufficient clock control |
| ENV-03 | randomness mutation | read uncontrolled entropy | hermetic profile blocks/fails; no false reproducibility claim |
| NET-01 | denied egress | attempt DNS/TCP/loopback according to policy | connection fails and observed policy is attested |
| CG-01 | cgroup delegation missing | read-only cgroup fixture/host | preflight fails without process-group downgrade |
| LIM-01 | fork bomb bounded | tiny `pids.max` fixture | fork fails, host remains healthy, `pids.events` records hit |
| LIM-02 | memory limit | bounded allocator in disposable fixture | Job/cgroup reports limit cause; full tree becomes empty |

Signature tests use ephemeral test keys only. A chaos suite must never receive
production KMS permissions. Artifact races should coordinate with barriers, not
timing sleeps, to make failure deterministic.

## CI and repeated identical-source verification

Proposed workflows, all third-party/GitHub actions pinned to full commit SHAs:

1. **Static/unit matrix** on `ubuntu-24.04`, `windows-2025`, and `macos-15`
   (plus supported Python versions): schema validation, canonicalization golden
   vectors, artifact path/digest tests, evidence verification, journal state
   machine, and mocked backend failure classification.
2. **Native containment integration** per OS: Linux delegated cgroup runner,
   Windows Job tests, macOS limitation/cleanup tests. Hosted runners may lack
   cgroup delegation, so Linux strong tests should use an ephemeral self-hosted
   runner or VM explicitly configured with a delegated subtree.
3. **Chaos** in disposable VMs only, with strict wall/resource caps. Run fork,
   crash, PID-reuse, mutation, and signature suites. Preserve bounded diagnostic
   logs and unsigned failure evidence.
4. **Reproducibility**: materialize the exact same committed source snapshot
   twice into independent clean workspaces with caches disabled; use the same
   manifest, toolchain/image digest, fixed time/entropy policy, and command;
   compare `executionHash`, artifact index, set root, and every artifact digest.
   Repeat with cache enabled as an additional check; SLSA says cache must not
   affect isolated build output.
5. **Cross-runner repetition**: two independent runners of the same immutable
   image digest compare outputs. This detects host leakage better than two
   directories on one host.
6. **Cross-platform comparison**: compare only artifacts declared
   platform-independent. Platform-specific outputs use per-platform expected
   roots. A single mismatch uploads both indexes, manifests, image identities,
   and a path-level digest diff; it never overwrites the golden value.
7. **Attestation job**: signing runs only after all required comparisons pass,
   in a separate job/environment with minimal OIDC/KMS permission. GitHub
   artifact attestation can supplement, not replace, the executor's own
   manifest/artifact binding.

Runner labels are scheduling hints, not image digests. Each job captures exact
runner image version and SBOM digest from the setup metadata/release. High-
assurance release policy should use immutable, ephemeral self-hosted VM images
or Linux OCI images pinned by digest; hosted runner repetition can be valuable
evidence while still reporting the weaker image guarantee.

Suggested reproducibility outcome schema:

```json
{
  "sourceSnapshot": "sha256:...",
  "executionHash": "sha256:...",
  "runs": [{"runId": "...", "imageDigest": "...", "artifactRoot": "sha256:..."}],
  "comparison": "identical|different|not-comparable",
  "differences": [{"path": "...", "left": "sha256:...", "right": "sha256:..."}]
}
```

## Test-retirement criteria

Tests should be retired only when all of the following are recorded in the
replacement change:

- the tested threat or contract is removed by an explicit Human-owned decision,
  or an equal/stronger test covers the same invariant on every supported backend;
- the replacement is linked by stable test/threat ID and demonstrates fault
  injection, not only the success path;
- platform coverage and capability-grade assertions are not reduced silently;
- at least one release cycle/defined observation window shows the replacement is
  stable (duration is Human-owned and currently unspecified);
- removal does not eliminate independent artifact re-hashing, signature identity
  checks, ambiguous-launch fail-closed behavior, or collateral-damage checks.

Current `/proc` boot-ID/start-ticks tests may become diagnostic compatibility
tests after pidfd adoption, but should not be removed until all Linux signalling
uses pidfd/cgroup identity and crash reconciliation no longer relies on PID.
Current process-group descendant tests remain useful for the macOS compatibility
backend and Linux fallback refusal tests; they are not evidence that cgroup
tests are unnecessary.

## Contradictions and tensions

1. **Cross-platform containment is not symmetric.** Linux cgroups and Windows
   Jobs own process trees; ordinary macOS process groups do not. A single
   `trusted: true` flag would be misleading.
2. **Containment is not hermeticity.** cgroup/Job/process groups do not alone
   constrain source visibility, filesystem, network, clock, randomness, or
   environment. The manifest needs enforcement providers for each dimension.
3. **Reproducibility and secret/unpredictable inputs conflict.** Jobs that need
   live secrets, unpinned network responses, current time, or nondeterministic
   entropy cannot simultaneously claim identical-source reproducibility unless
   those influences are removed from outputs or captured/replayed under an
   explicitly weaker profile.
4. **Dirty working tree versus commit identity.** The current repository is
   dirty. Building the current filesystem while claiming only the inspected
   commit would be false. Snapshot dirty content explicitly or use the committed
   tree.
5. **Hosted convenience versus immutable image identity.** GitHub-hosted images
   are ephemeral but updated. Version capture improves provenance after the
   fact; it is not the same as selecting a preverified immutable image digest.
6. **Signature validity versus evidence accuracy.** A compromised or tenant-
   controlled signer can make valid false statements. Key isolation and
   control-plane measurement are mandatory to raise confidence.
7. **Current Linux fail-closed portability versus requested cross-platform
   support.** The present runtime deliberately reports `/proc` identity as
   unsupported elsewhere. Adding OS backends must preserve fail-closed semantics
   rather than relaxing identity globally.

## Security assumptions

- The verifier's trust roots/policy are authenticated and maintained outside the
  artifact bundle.
- The control plane, backend helper, kernel/hypervisor, image provisioning, and
  signing service are within the trusted computing base for their claimed grade.
- Executed code is adversarial and can fork, detach, race output paths, flood
  logs, alter environment-dependent behavior, and attempt credential discovery.
- Signing credentials and OIDC tokens are unavailable to executed code and are
  issued only after policy gates where applicable.
- SHA-256 collision/second-preimage resistance and signature algorithm security
  hold; algorithm identifiers are explicit and downgrade is rejected.
- A verified artifact proves bytes and provenance policy, not semantic safety,
  absence of vulnerabilities, or Human acceptance.
- Local administrator/root or kernel compromise is out of scope for an
  in-process local backend; stronger adversaries require separate VM/hardware
  trust boundaries.

## Residual limitations and unresolved Human decisions

- Select supported OS versions and whether macOS `best-effort-tree` is an
  acceptable product mode or only a diagnostic mode.
- Select the signing trust model (public Sigstore, GitHub attestation, KMS,
  multiple signers), identity policy, rotation, revocation, offline verification,
  and transparency requirements.
- Decide whether release-grade hermetic execution requires self-hosted immutable
  VMs/containers and who owns those images and SBOM policy.
- Define accepted lockfile ecosystems, allowed network exceptions, time/random
  virtualization strength, artifact mode/symlink rules, and cross-platform path
  normalization policy.
- Define resource-limit defaults and acceptable containment failure behavior for
  each runner environment.
- Define acceptance thresholds and the observation period for test retirement.
- Validate Apple App Sandbox/XPC feasibility with a signed prototype on real
  macOS; this Linux exploration cannot prove entitlement or arbitrary-tool
  compatibility.
- Validate Windows nested Job behavior and immutable-image strategy on real
  Windows; no Windows runtime experiment was possible here.
- Validate cgroup delegation and `clone3(CLONE_INTO_CGROUP)` in the intended
  Linux service-manager/runner topology; this host exposed cgroup v2 but did not
  delegate a writable root to the current process.

## Smallest useful follow-up

Implement a non-signing vertical prototype in a separate authorized Work task:
strict manifest validation, committed-source snapshot digest, deterministic
artifact index/root, independent verification, and a backend capability probe.
Exercise it in disposable Linux/Windows/macOS CI without claiming acceptance.
Then add Linux delegated-cgroup/pidfd containment and chaos tests before
introducing production signing; otherwise signatures may prematurely
authenticate inaccurate executor claims.
