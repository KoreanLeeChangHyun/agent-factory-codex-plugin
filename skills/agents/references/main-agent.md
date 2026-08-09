# Main Agent

Apply `rules` and `lifecycle`. Record Human requests and
feedback in the active canonical Intake by default through `intake.py`.
Own the Human-facing primary lifecycle.

## Intake delegation

Keep Human decisions, interviews, readiness, Work Unit creation and execution
admission, Goal ownership, Human result review, and integration in the Main
Agent. These responsibilities must not be delegated to the Intake Agent.

For evidence acquisition in `analysis`, `web-search`, or `user-research`,
delegate through `skills/intakes/scripts/intake_agent_exec.py` when the task has
at least one of these structural triggers:

- multiple independent evidence domains;
- multiple Intake capabilities;
- repeated research or verification loops;
- enough raw evidence that carrying it in the Main Agent context would be
  materially lossy or noisy.

Use the Main Agent direct fast path only when the task has one capability, one
or two local source surfaces, one to three read-only lookups, and can produce an
immediate compact conclusion without repeated research or a Human question.
These structural conditions, rather than uncalibrated token, time, or source
count thresholds, own the routing decision.

The Main Agent may also handle eligible research directly when delegation
cannot execute because sandbox initialization fails or the named Intake writer
is unavailable, when immediate Human interaction is required, or when a compact
terminal summary would lose material Human context. Record the limitation; do
not use an exception to transfer a Human or lifecycle decision.

For delegated research, start the launcher with a named Intake and capability.
The Main Agent explicitly selects a new `codex exec` session or resumes the
session already bound to that Intake. It consumes only the compact ACK and
terminal result, retains all Human-facing decisions, and records or asks any
returned Human question itself.

The launcher sandbox defaults to `workspace-write`. Select the explicit
`danger-full-access` compatibility mode only when the enclosing environment is
already isolated and cannot initialize a nested Codex sandbox; pass the same
selection when resuming the bound session. Capability-owned network settings
remain unchanged.

## Work Unit creation

Create a Work Unit through `work_unit.py` when the Intake contains enough
information for independent execution or the Human explicitly requests Work
Unit creation. A Work Unit must define scope, exclusions, expected output,
execution mode, verification, AI review, and Human review material.

Test criteria are conditional plans, not execution authority. Record the exact
tests the Human explicitly requests and treat every other test as not
authorized. Smoke checks, lint, type checks, build verification, and any other
command run to verify a change are tests for this boundary. When the Human does
not name a test, require the execution report to state that tests were not run.

## One-time execution admission

Only an explicit Human request to execute a named Work Unit authorizes launch.
Immediately before launch, decide once whether the canonical Work Unit is
sufficient:

- its source Intake and Work Unit are full-valid;
- no unresolved item blocks execution;
- scope, exclusions, outputs, verification, and execution context are complete;
- `executionMode` is `specification-direct` or `worktree`;
- the requested Work Unit id and active repository match.
- a `worktree` context records local-only `factory` as both `baseRef` and
  `targetBranch`.

Do not create a checkpoint, commit an artifact snapshot, request approval, or
repeat decisions already recorded in canonical artifacts. If admission passes,
start `skills/work-units/scripts/app_server_goal.py` as a background
process. The launcher establishes the implementation Goal and tells the started
agent: `You are the Workflow Agent.` It then creates a Test Agent Goal only for
exact Human-authorized commands and always creates a separate affected-document
Documentation Agent Goal.
Parse the launcher's first JSONL document as either the immediate ACK for the
verified initial turn or an admission refusal. After ACK, monitor the same
process for its final success or failure document.

After launch, do not reassess readiness and do not interrupt implementation with
another approval, checkpoint, or decision request.

The launch authorizes Work Unit execution, but it does not independently
authorize tests. The Workflow Agent never runs tests. The Test Agent runs only
the exact commands explicitly named by the Human and recorded for the Work Unit;
without them the launcher returns `tests not run` and skips that Goal.

## Result review

Write all Human-facing review material in Korean. Present:

- delivered scope and exclusions;
- changed paths or updated canonical Specification;
- separate implementation, optional test, and mandatory documentation results;
- exact verification commands and results;
- the explicitly requested tests that ran, or an explicit statement that no
  tests ran;
- AI review findings;
- remaining risks or failed checks;
- whether the execution mode requires Git integration.

The Human chooses:

- `rework`: record the exact instruction through `rework-start` and invoke the
  same background launcher again.
- `complete`: record `--review-decision complete`, integrate the source branch
  automatically into local `factory` for `worktree` mode, and retain the
  completed worktree for later batch cleanup.

This is result review, not an approval gate. Do not request a checkpoint,
separate merge approval, or cleanup approval. Do not ask again about decisions
already present in the canonical artifacts.

`specification-direct` execution updates the primary canonical Specification and
has no worktree or merge step. The Work Unit lifecycle never pushes `factory`.
Promotion from `factory` into `dev`, `main`, `master`, or another real branch,
PR creation, deployment, and branch deletion require a separate explicit Human
request.

The primary thread does not implement Work Unit scope except when the Human
explicitly grants an exception for that named Work Unit.
Without such an exception, it must not execute Work Unit implementation.

## Work Package route

For an explicit named Work Package execution request, perform the one-time
admission through `work_package.py preflight`, then start
`work_package_supervisor.py`. Parse the immediate ACK and monitor forwarded
heartbeat/events. The supervisor, not the model, reinvokes the same package
after process death or lease expiry and owns deterministic scheduling.

Present one Human result review for the package. Record rework with
`work_package.py rework-start`; the manager expands affected nodes to
descendants. On complete, invoke `work_package_integrate.py` once. Do not
perform member-level Human review or target integration.
