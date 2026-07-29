# Work Package DAG execution evidence

- Work Unit manager regression: 42 tests passed.
- Work Unit execution regression: 65 tests passed.
- Main-agent Work Package contract: 1 test passed.
- Workflow-agent Work Package contract: 1 test passed.
- Specification manager regression: 10 tests passed.
- Latest full skills regression: 186 tests passed.
- Intake, Work Unit, Project Core, durable supervisor Specification, Work
  Package profile, and all Specification schema/full-validation gates passed.
- `ruff check`, plugin validation, skill validation, and `git diff --check`
  passed.

Acceptance fixtures cover cycle/self/missing dependency rejection; invalid
readiness, repository mismatch, branch/worktree collision, and missing member
refusal before ACK without execution side effects; stable A/B parallel
scheduling with C after prerequisite merge; positive maxParallel; immediate
ACK fields; heartbeat; process-death reinvocation; completed-node and
executed-node resume; node-error and merge-conflict recovering with a stable
idempotency key; specification-direct serialization; single package review;
one integration receipt; member traceability; and affected-descendants rework.

The initial full regression exposed an unregistered Work Package profile
schema; the profile was registered in the common document-profile contract.
The completion audit then exposed a branch-only collision gap; `show-ref`
preflight was added and the latest complete regression passed. A pre-existing
stale Specification provenance reference to a lifecycle-cleaned Work Unit was
removed through manager-owned `source-ref-prune`, after which the durable
supervisor Specification passed full validation.
