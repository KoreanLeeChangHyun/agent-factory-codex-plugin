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

The preferred `work-basis-ref` item declares `basisType` as `human-request`,
`project-skill`, or `intake`. A Human basis contains the bounded request. A
Project Skill basis references `.agent-factory/skills/project`. An Intake basis
references one topic-scoped Intake package root without a section anchor and
contains unique non-empty `entryIds`. The legacy `intake-basis-ref` shape
remains valid. Intake is optional and Work Unit readiness owns admission.

The `test-criterion` in `acceptance-and-verification` is a conditional plan. It
must distinguish Human-authorized bounded tests from a no-tests-authorized
state. Exact Human-supplied commands remain unchanged; otherwise commands come
from bounded repository evidence. The `execution-result`, optional
`ai-review-result`, and
`report-result` must record the commands and results for authorized tests or
state that tests were not run. Smoke, lint, typecheck, and build verification
are governed by the same rule. Execution context also records the Workflow
Agent as implementation-only, the optional code-read-only Test Agent, and the
separately selected affected-document-only Documentation Agent and independent
static Review Agent. These roles are not implied by selecting a Work Unit. The
Review Agent modifies no files, runs no verification
commands, and provides structured `ai-review-result` evidence. Execution and
Report evidence keep every role's ACK, terminal receipt, result, and failure
separate.

## Execution context

Record Goal id, objective, exact `app_server_goal.py` invocation, Workflow Agent
role, absolute primary repository, and `executionMode`. When the Human
selected independent Review, record both `targetReviewRole` and
`reviewExecution`; the role is review-only and runs in a separate Goal. A
context containing only one Review field is invalid.

For `specification-direct`, work occurs through the Specification manager in the
recorded primary repository. For `workspace-direct`, work occurs directly in
that repository. Branch and secondary-checkout identity fields are omitted.

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

`status --all` reports `reviewStatus`.
