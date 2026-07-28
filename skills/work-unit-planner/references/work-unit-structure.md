# Work Unit Structure

Canonical packages live at
`<project-root>/.agent-factory/work-units/<work-unit-id>/` and are managed only
through `work_unit.py`.

Required sections:

1. `basis`
2. `work-definition`
3. `plan`
4. `execution-context`
5. `acceptance-and-verification`
6. `execution`
7. `ai-review`
8. `human-review`
9. `report`

## Execution context

Record Goal id, objective, exact `app_server_goal.py` invocation, Workflow Agent
role, absolute primary repository, base ref, and `executionMode`.

For `worktree`, record the derived branch and canonical linked worktree path.
For `specification-direct`, branch/worktree fields may retain derived identity
for compatibility but no worktree is created or used.

## Execution-state v2

```json
{
  "contractVersion": "2.0.0",
  "state": "planned",
  "currentRevision": 1,
  "currentAttempt": null,
  "invocationId": null,
  "invocationChain": [],
  "history": [],
  "progress": {
    "completedSteps": [],
    "pendingStep": null,
    "records": [],
    "retry": {}
  },
  "recovery": {
    "status": "planned",
    "ownerInvocationId": null,
    "blockerId": null,
    "evidence": null
  }
}
```

No Git commit, content hash, snapshot, or checkpoint belongs to execution state.
Outcome evidence targets contain contract version, revision, attempt, and
invocation id only.

## Commands

```text
work_unit.py execution-init <package>
work_unit.py execution-migrate <package>
work_unit.py attempt-start <package> --invocation-id <id>
work_unit.py attempt-resume <package> --invocation-id <id>
work_unit.py execution-progress <package> \
  --step-id <id> --state <pending|completed> --idempotency-key <key>
work_unit.py rework-start <package> --instruction <text>
work_unit.py transition <package> review
work_unit.py transition <package> done --review-decision complete
```

Integration receipt registration uses `integration-put`; receipts have no
approval field. `status --all` reports `reviewStatus`.
