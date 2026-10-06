# Task Allocation

## 1. Allocation evidence and judgment

- Main decomposes independent outcomes with completion evidence; keep strong dependencies/shared
  state with one owner. Only ready, conflict-free work is a parallel candidate. File count,
  elapsed time and worker count are not complexity limits.
- Choose role/profile separately from model, effort, Fast and permissions: explore investigates;
  workLight handles settled local changes; work handles uncertain design/integration/diagnosis;
  scribe consolidates authorized Documents. Independent Verification requires explicit Human
  request. Only Main dispatches. Prefer existing sessions for same-task corrections; explain
  new/reuse choice from continuity, purpose and boundaries, not elapsed time.
- Include prerequisites, input source/version/time, read/write scope, shared ownership and
  unit/profile/session reasons in brief Scope. Never claim unconfirmed results or ownership ready.
- With installed `submit.taskAllocation: true`, optionally use `loop.py start --allocation-file
  <run>/allocation.json` for a brief, or `tasks[].allocation` in the existing task list, never both.
  Older runtimes receive prose only; source support does not prove installed capability.
- All fields are required when allocation is present; empty arrays explicitly mean none.
- Preserve Human-specified model, effort, Fast and permissions independently of the
  profile. A supplied model catalog is selection evidence, not authority or a ranking.
  Compare task suitability and important constraints only within the allowed selection
  scope; unknown cost/quality stays unknown. Read the candidate's exact detail source
  when needed and recheck its revision. Retain choice and detail-read reasons in the
  existing task/run evidence, including source/revision and unresolved constraints.
- Forward a self-contained bounded brief with goal, completion, scope, dependencies,
  decisions, errors, unresolved issues and exact settings. Reference unrelated task
  bodies/logs through their original run instead of copying them. References never
  replace required scope or permission evidence; full originals remain accessible.
- For same-input comparisons, `exec.py measure --input <JSON>` reads schemaVersion 1
  cases with id, input, completionCriteria and before/after messages/runStatePaths.
  It launches no model. Static bytes and fixture checks are separate from reported run
  usage and task quality. Run totals already include retries; cache/reasoning are
  subsets. Supply sourced quality, detailReads, elapsedSeconds, allocationErrors and
  rework only when observed. Missing values remain null; no unmeasured savings rate.

| Field | Meaning and validation |
|---|---|
| schemaVersion | Integer 1. Unknown fields/versions are rejected. |
| unitReason | Nonempty independent-outcome/completion-evidence reason. |
| profile | id: explore/workLight/work/scribe/verification; nonempty reason. Records judgment, selects no model. |
| session | strategy: new/reuse; nonempty reason. Actual session uses the Agent binding. |
| inputs | Entries: nonempty source, revision, timezone-bearing ISO capturedAt, boolean confirmed. Unresolved revisions may be explicit unknown with confirmed=false. |
| dependencies | Same evidence fields; optional taskId must be a preceding task in this ordered list. Unknown/self/forward/duplicate IDs fail. External prerequisites use source references without local taskId. |
| readScope | Nonempty path/source strings; descriptive, grants no permission. |
| writeScopeReason | Nonempty explanation of the existing brief Scope or requiredFileOperations/documentPaths/workspace. No second write list. |
| sharedResources | Entries: nonempty resource, evidence; boolean confirmed; ownerTaskId: self or an existing task ID. One resource has one owner. Unknown external ownership remains unresolved evidence. |
| parallelCandidate | Boolean judgment. True requires confirmed inputs/dependencies/ownership and ownership of declared resources; overlapping existing declared writes fail. |

- Runtime validates declared consistency, retains allocation in task-list snapshots, loop execution
  binding, run taskBinding and immutable dispatch tuples, and supplies it to Work as evidence.
  Query the exact Agent/run with `exec.py status --document state --field /taskBinding/allocation`;
  historical records may lack this field. Queries never start work.
- Revision/retry/resume uses the accepted snapshot. Same-task sends reject changed/removed accepted
  allocation/scope; different tasks can reuse the session. Planned reasons remain unchanged;
  actual fallback profile/session is recorded separately by the existing run contract.
- Confirmation is Main's evidence assertion, not proof that an external source is true/current.
  Unconfirmed evidence can be retained but cannot be parallel-ready. Declared writes do not
  discover hidden shared state or other workflows' writers. No resource locks are introduced.
- This stage records/validates judgment; it does not automatically decompose work, learn model
  routing or schedule dependencies. Loops stay sequential; Main handles external prerequisites
  and parallel chains. Preserve existing failureClass retries, authority, receipt and Verification.
  A scheduler, learned routing, new UI or framework requires a later scope.
