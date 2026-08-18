# Work Unit Execution

This is an optional advanced route. Start it only when the Human explicitly
requests the named Work Unit. The normal feedback-first route uses a Work Agent
in the current Git workspace instead.

## Launch

The primary agent performs one full-valid sufficiency decision immediately
before execution. Then run:

```text
python3 scripts/app_server_goal.py \
  --repository <absolute-primary-root> \
  --work-unit-id <work-unit-id> \
  [--thread-id <existing-goal-thread-id>]
```

The launcher is the Goal preflight. It:

- validates the canonical primary-root Work Unit;
- accepts ready initial execution, planned rework, or a manager-owned active
  attempt that must be resumed;
- creates and verifies the matching active Goal;
- starts a background Workflow Agent Goal for implementation only;
- starts a Test Agent Goal only for Human-authorized bounded commands, otherwise
  records `tests not run`;
- starts Documentation and independent static Review Agent Goals only when the
  Human separately selected those roles;
- emits one immediate JSONL ACK after the verified initial `turn/start`;
- automatically continues a turn that ends as `interrupted`;
- returns an explicit error after bounded recovery instead of leaving a live
  process waiting forever.

When `--thread-id` is supplied, the launcher verifies that the existing thread
already owns the matching active Goal and starts the new turn without calling
`thread/start`. A missing or mismatched thread or Goal must fail closed before
`turn/start`. Without `--thread-id`, the launcher retains the new-thread path.
For a new thread, `thread/goal/set` and `thread/goal/get` must agree before
`turn/start`; for a reused thread, `thread/goal/get` must return the matching
active Goal. Admission refusal before a valid initial turn emits no ACK. After
ACK, the launcher emits its final success or failure JSON document when
execution terminates.

Once launched, do not repeat readiness, checkpoint, or approval decisions.
Execution occurs only in the recorded primary workspace.

Launch and admission do not authorize tests. The Workflow Agent never executes
tests. A separate Test Agent executes only commands authorized by the Human and
recorded in the Work Unit: exact supplied commands unchanged, or the smallest
bounded commands selected from repository evidence after a general test
request. With no authorization the launcher skips that Goal and reports
`tests not run`. Documentation and independent Review Goals are also skipped
unless separately selected.

## Execution modes

`workspace-direct`:

- edits ordinary code and project files in the recorded primary Git workspace;
- creates no branch or secondary checkout and has no Git integration phase;
- preserves unrelated uncommitted changes.

`specification-direct`:

- updates the primary-root `.agent-factory/specifications` package only through
  `specification.py`;
- has no Git integration or cleanup phase.

These are the only execution modes. Commit, branch operations, PR creation,
push, deployment, and restart remain separate explicit Human actions.

## Execution state

Execution state uses Work Unit revision, attempt, invocation chain, and
idempotent step records. It does not bind artifact state to Git hashes,
immutable snapshots, or checkpoints. `attempt-resume` appends the new Goal
thread id to the current attempt.

## Work Package execution

Run a ready package through:

```text
python3 scripts/work_package_supervisor.py \
  --repository <absolute-primary-root> \
  --package-id <package-id>
```

The supervisor requires the executor's first JSONL event to be ACK, forwards
heartbeat and state events, and reinvokes the same package after ACK-bound
process death or heartbeat timeout. Admission refusal before ACK is
non-mutating and is not retried.

`work_package_exec.py` uses manager preflight, stable topological/id selection,
sequential primary-workspace node execution, Specification-direct
serialization and full validation, durable leases and idempotency keys, and
`app_server_resolution_goal.py` recovery. A dependent node starts only after
its prerequisites have completed in the same workspace. It reaches package
review only after every node and every selected verification and AI review
passes.

The member launcher returns failure when either `aiReviewResult.result` or
`checklistResult` fails. The package executor independently enforces that gate
and derives package review evidence from passing member results. Node recovery
and supervisor restart loops use finite positive budgets and return an error
when exhausted.

Every Work Package records the primary repository as its execution target.
After the Human chooses complete, record the accepted result through the owning
manager. There is no integration phase. Do not commit, push, or promote the
result without a separate explicit Human request.
