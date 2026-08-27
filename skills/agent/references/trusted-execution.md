# Trusted execution

## Boundary

Trusted execution is opt-in and does not change the asynchronous managed-Agent
envelope, dispatch identity, receipt binding, retry rules, or Work/Review test
prohibition. It produces executor observations, not Human acceptance and not a
claim that an artifact is semantically safe.

The private signing key is an external control-plane input. It must not be
placed below `.agent-factory/`, inherited by the payload, copied into logs or
artifacts, or embedded in evidence. Verification requires an independently
provisioned public key. Generating a key and treating it as trusted in the same
verification path is not a trust decision.

## CLI

`scripts/agent_exec.py` exposes:

- `execute-execution --project-root DIR --run-directory DIR --run-id ID
  --manifest FILE --private-key FILE --public-key FILE --policy FILE` is the
  normal lifecycle entry point. It completes only when an executor integration
  supplies a payload-inaccessible control plane and reparse/no-follow artifact
  publication; the bundled same-identity CLI backends currently return the
  machine-readable `capability_unsatisfied` refusal before launch;
- `probe-executor [--backend auto|linux|windows|macos]` reports observed
  capabilities without promoting them to requested policy;
- `prepare-execution --project-root DIR --manifest FILE --run-directory DIR`
  is a diagnostic preparation surface. A read-only mode bit under the payload
  owner's identity is not an immutable snapshot or trust boundary;
- `seal-execution --run-directory DIR --manifest FILE` is a diagnostic recovery
  operation that requires journal-proven quiescence and derives the output root
  from the manifest;
- `attest-execution --run-directory DIR --run-id ID --manifest FILE --index
  FILE --private-key FILE --public-key FILE` requires journal phase `sealed`,
  derives result and capabilities from executor observations, signs DSSE PAE
  bytes, and publishes the statement and envelope;
- `verify-execution --run-directory DIR --run-id ID --manifest FILE --index
  FILE --bundle FILE --public-key FILE --policy FILE` checks the trust key and
  strict external verifier policy, exact signature bytes, recursive schemas,
  builder/run/manifest/capability binding, artifact subjects, CAS contents, and
  set root;
- `compare-executions` compares canonical manifest identities and every sealed
  artifact digest, failing with `reproducibility_mismatch` on divergence.

OpenSSL is the explicit system cryptography provider for RSA/SHA-256 signing
and verification. Its absence is the stable `signing_identity_unavailable`
capability failure. The executor passes DSSE PAE bytes to OpenSSL and verifies
the exact decoded payload; it does not parse and reserialize before checking a
signature.

## Manifest v1

The manifest is UTF-8 JSON, version `1.0.0`, canonicalized with RFC 8785 JSON
Canonicalization Scheme rules over the supported float-free I-JSON domain.
Property names sort by UTF-16 code units; lone surrogates and integers outside
the exactly representable range `[-(2^53-1), 2^53-1]` fail closed. Unknown or
missing fields and floating-point numbers also fail closed. Its identity excludes
timestamps, nonces, signatures, runtime PIDs, and other observations.

The complete top-level fields are `schemaVersion`, `kind`, `source`,
`dependencies`, `toolchain`, `environment`, `platform`, `command`, `policy`,
`outputs`, and `builder`. They bind:

- source input digests, ignored-input policy and ignore-file digests,
  submodules, and snapshot digest;
- lockfiles or an explicit declaration of no external dependencies;
- executable/interpreter and immutable runner-image identity;
- an empty base environment and exact allowlisted values;
- platform, argv, bounded cwd, stdin policy, and umask;
- requested network, time, randomness, filesystem, and resource policy;
- output rules, builder identity, backend, and required capability grade.

The manifest records requested controls. The signed predicate separately
records observed backend capabilities. `hermetic` is valid only when every
required influence is enforced; process containment alone is insufficient.
Preparation rehashes each source, ignore-policy file, lockfile, interpreter,
and tool executable and checks actual platform plus separately supplied runner
metadata. GitHub runner labels and `ImageVersion` values are observations, not
immutable image digests. The payload gets
only the exact allowlisted environment and runs with the declared executable,
argv, cwd, closed stdin, and umask. Any requested control that the backend does
not report as enforced fails before launch.

## Artifact seal

Only regular files beneath the resolved managed run and selected artifact root
are accepted. Traversal, absolute paths, symlink directories/files, devices,
FIFOs, sockets, hard links, oversized files, mutation during reads, and
case-folded duplicate subjects fail closed. Reads use no-follow descriptors and
compare identity and metadata around hashing. CAS blobs and indexes publish by
atomic rename with read-only permissions.

Each index entry binds normalized path, regular-file type, normalized mode,
size, and SHA-256. The set root hashes sorted, domain-separated entry leaves.
Verification reopens and rehashes every blob; a digest-shaped pathname is never
trusted by itself.

Traversal, CAS creation, publication, and verification are anchored to opened
trusted-directory descriptors. Components open relative with no-follow
semantics, CAS blobs publish create-exclusive, and directory identities are
rechecked against their still-named locations. Sealing is permitted only at
journal phase `quiescent` and advances atomically to `sealed`.

## Evidence

`provenance.bundle.json` is a strict DSSE-compatible envelope containing one
base64 in-toto Statement v1 payload and one signature. The statement predicate
binds the exact run ID, canonical manifest SHA-256, result status, command,
requested policy, observed backend capabilities, artifact-index digest, set
root, and every artifact subject. Unknown fields, wrong public keys, invalid
signatures, payload splicing, manifest changes, and artifact changes fail
closed.

The canonical manifest and artifact identities are reproducible. Evidence
signatures and any future event timestamps are deliberately excluded from the
reproducibility comparison because randomized signature encodings and runtime
observations are evidence about a run, not source inputs.

The signed predicate also binds the executor terminal-observation digest. Every
post-prepare operation reopens only the fixed `execution.manifest.json`, checks
its digest against the journal, and rejects a caller-selected substitute.

The adjacent-only journal phases are `prepared`, `contained`, `launching`, `launched`,
`observed`, `quiescent`, `sealed`, `attested`, and `verified`. Diagnostic split
commands cannot skip a phase, invent a result/capability observation, seal a
live tree, or attest unsealed output. Private keys resolving within either the
repository or managed state fail with `signing_identity_unavailable`.
Run-local journal and manifest files remain payload-writable under an ordinary
same-identity process. Consequently the bundled backends report
`controlPlaneIsolation: none` and refuse attestation; mode `0400`, a process
group, cgroup, or Job Object does not change that ownership fact.

## Backend contract

- Linux strict process containment requires an explicitly delegated cgroup v2
  path with `cgroup.kill` and pidfd.
  A startup barrier keeps the target from executing before cgroup attachment;
  pidfd owns exact leader identity and `cgroup.kill` owns subtree termination.
  The existing process-group route remains clearly reported as weaker
  compatibility behavior.
- Windows native Job containment remains independently usable and tested. It
  uses import-safe, pointer-width ctypes declarations, creates the target suspended,
  assigns it to a Job Object configured with
  `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, and only then resumes it. Termination and
  waiting use Job/process handles, never PID identity alone. The current Job
  backend advertises CPU hard-cap, Job-memory, and active-process limits only
  after configuring and reading back all three. The complete trusted lifecycle
  is refused on Windows until a reparse-safe directory-handle publisher and isolated
  control plane are provided; Job containment alone is not called complete.
- macOS uses a startup barrier and exact leader/process-group cleanup but reports
  `best-effort-tree`. A process group is not a security or resource sandbox.
  Hermetic filesystem/network requirements fail unless a separately entitled,
  sandboxed host supplies and reports those capabilities.

Unsupported OS/backend combinations return stable machine errors. Capability
grades are `best-effort-tree`, `contained`, and `hermetic`; the executor may
refuse a stronger requested grade but never upgrades an observed grade.

## CI and limits

`.github/workflows/trusted-executor.yml` runs unit/native coverage on Ubuntu,
Windows, and macOS and captures backend capability records. Linux strict CI
passes an explicit delegated path into a real cgroup/pidfd fixture when the
host can create one; otherwise it uploads a machine-readable fail-closed
refusal. The reproducibility job may complete only on a backend that supplies
the required control-plane boundary. Action revisions are pinned and workflow
permissions are read-only, but a workflow file is not evidence that the remote
workflow ran.

Hosted runner images are mutable scheduling products even when their observed
versions are recorded. Job Objects and cgroups do not independently isolate the
filesystem, network, clock, or randomness. macOS strong sandboxing requires a
separately signed/entitled host. Key custody, release trust roots, supported OS
versions, and acceptance of compatibility grades remain Human-owned decisions.
