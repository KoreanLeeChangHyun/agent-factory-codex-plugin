# Trusted executor and reproducibility exploration

Investigate an implementable design for the Agent Factory plugin covering:

1. executor-generated cryptographically signed evidence;
2. a hermetic execution manifest that covers source, ignored-input policy,
   submodules, lockfiles, toolchain, environment allowlist, runner image, command,
   network/time/randomness policy;
3. content-addressed artifact sealing and verification;
4. a Linux cgroup v2 + pidfd execution backend;
5. Windows Job Object and macOS process-containment backends;
6. crash, PID reuse, artifact mutation, signature forgery, and environment
   mutation chaos tests;
7. CI matrix and repeated identical-source reproducibility verification.

Use current official primary sources where possible (Linux kernel/man-pages,
Microsoft, Apple, SLSA, Sigstore, GitHub Actions). Inspect the current repository
implementation and test structure. You are explicitly authorized to perform
read-only runtime capability probes and bounded experiments in your isolated
Explorer workspace, but must not edit canonical project files or run the
repository's test suite.

Produce `.agent-factory/explorer/trusted-executor-cross-platform-20260828/notes.md`
with observed facts, platform/API constraints, proposed module/schema/CLI design,
security assumptions, CI strategy, test-retirement criteria, contradictions,
and residual limitations. Include direct source URLs and clearly label
inferences. Do not make Human-owned acceptance or risk decisions.
