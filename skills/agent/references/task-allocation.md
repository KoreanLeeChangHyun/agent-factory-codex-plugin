# Task Allocation

## 1. Allocation evidence and judgment

- Main decomposes independent outcomes with completion evidence; keep strong dependencies/shared
  state with one owner. Only ready, conflict-free work is a parallel candidate. File count,
  elapsed time and worker count are not complexity limits.
- Choose role/profile separately from model, effort, Fast and permissions: explore investigates;
  workLight handles settled local changes; work handles uncertain design/integration/diagnosis;
  scribe researches, checks sources, writes, integrates and shortens authorized Documents.
  Independent Verification requires explicit Human request. Only Main dispatches.
  Prefer existing sessions for same-task corrections; explain
  new/reuse choice from continuity, purpose and boundaries, not elapsed time.
- Include prerequisites, input source/version/time, read/write scope, shared ownership and
  unit/profile/session reasons in brief Scope. Never claim unconfirmed results or ownership ready.
- With installed `submit.taskAllocation: true`, optionally use `loop.py start --allocation-file
  <run>/allocation.json` for a brief, or `tasks[].allocation` in the existing task list, never both.
  Older runtimes receive prose only; source support does not prove installed capability.
- All fields are required when allocation is present; empty arrays explicitly mean none.
  The only optional fields are `domain`, accepted when installed `submit.taskDomain: true`, and
  `taskType`, accepted when installed `submit.modelRecommendation: true` ([model recommendation](#model-recommendation)).
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
| domain | Optional. Trimmed single-line work-area name (at most 80 characters) such as the product area the outcome belongs to, chosen by Main for this task. Not a profile, role or model. Omit it only when the worker already belongs to a domain; consumers never infer it from titles or history. |
| taskType | Optional. research, small-change, design-diagnosis or documentation, classified by Main. The runtime then adds `modelRecommendation`; never submit that field. |
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

<a id="project-domains"></a>

## 2. Project domains

- With installed `submit.projectDomains: true`, one editable project list of work-area domains and
  worker memberships is shared by the Human (control center) and Main. Run `domains.py list` before
  choosing an allocation `domain`; reuse an existing name (current or former) for the same work area
  and create a new name only when none fits. Never invent a fixed taxonomy or infer from titles alone.
- With installed `submit.domainMembership: true`, every worker belongs to one real, named domain.
  There is no unclassified state: `--placeholder`/`--unclassified` fail with `domain_membership_required`,
  names meaning "no domain" (`미분류`, `unclassified`, …) fail with `domain_name_reserved`, and Main must
  name the actual area, never a catch-all (`기타`, `기본`, `misc`, `general`, …). `loop.py start` refuses
  a Work or Verification worker that has no domain unless the allocation names one Main may link;
  a refused start registers nothing. `loop.py handoff` places the new session in the prior worker's domain.
- `loop.py start` links the accepted allocation domain as Main's (`ai`) choice: a matching domain is
  reused or created and the workers are placed in it, reported as `domainLink` (Work) and
  `verificationDomainLink`. Without an allocation domain, place a new worker first with
  `domains.py link --actor ai --source <run> --agent <id> --name <domain>`; `member` tells whether it belongs.
- Human edits win. Main may not rename a domain the Human named or move a worker the Human placed;
  such writes fail with `domain_protected` and a linked dispatch keeps going. Use `--expected-revision`
  from the last read; `domain_conflict` means reload.
- The list is display/organization data. It never rewrites accepted allocation, taskBinding, receipts
  or run state; a renamed domain keeps former names so recorded tasks stay linked. Delete and merge
  are not supported, and no write may leave a worker without a domain.
- `list` also returns `unresolved`: workers recorded before membership was required (`unassigned`,
  a Human `legacy-unclassified` choice, an `unnamed-domain` provisional domain or a `missing-domain`),
  removed workers included. `domains.py recover [--dry-run]` places only a worker with no entry whose
  own runs and loops recorded exactly one allocation domain; the rest stay listed with `candidates`
  for an explicit `assign`. Only the Human resolves a Human legacy choice; naming a provisional domain
  (`rename`) resolves its workers. Nothing is hidden, deleted or guessed.

<a id="model-recommendation"></a>

## 3. Model recommendation and provider handoff

- With an allocation `taskType`, pass the supplied modelCatalog as `loop.py start --model-catalog-file`.
  The runtime matches it against the Human's `model-affinity.json` in the project runtime root
  (schemaVersion 1; per task type an optional `profile` and ordered `preferences` of exact IDs or `*`
  patterns) and records `allocation.modelRecommendation`: status, recommended/selected model,
  alternatives, excluded and undetected entries, table and catalog hashes. The runtime never creates
  the table; without it the status is `no-affinity-table` and nothing is recommended.
- Only detected candidates are chosen; a missing catalog is `recheck-required`. A specified `--work-model`/`--model` or the Human's captured role model is
  kept (`human-specified`, flagged if undetected). Only a single-task loop applies the recommendation;
  task lists record `recommended`. An existing Work session limits candidates to its provider.
- With installed `submit.providerHandoff: true`, the Human may move a running or stopped loop's Work
  task: `loop.py handoff --work-agent <owner> --loop-id <id> --to-agent <new> --to-model <model>
  --actor human --authorization-reference <ref> --decision-evidence <text> [--reason <text>]`.
  It cancels a live Work run and waits for it to end, writes a bundle (original request, progress,
  changed paths, remaining work and open findings) as the new session's request, reassigns the current
  and later tasks and records `handoffs[]` linking both sessions. The prior session stays read-only.
  Pending dispatches or decisions must be resolved first; Verification steps are not handed off.
