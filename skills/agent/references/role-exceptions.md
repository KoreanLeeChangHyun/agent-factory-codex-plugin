# Direct role exceptions

## 1. Assigned Documents and records

- Explorer assignments are exact project-relative `documentPaths` on the selected task of
  `--task-list-file`/`--task-id`; existing accepted-contract `requiredFileOperations` add/modify
  entries take precedence. Binding validation retains these paths and announcement comparison
  rejects replacement. Assign one owner per file; no assignment grants no project writes.
  Allowed locations are Original source metadata, Refined research/comparison/analysis,
  evidence artifacts and own handoff records. Code/configuration, other owners' files,
  `docs/skills/`, shared progress/contract files, deletion/moves and rule publication stay denied.
  Paths are normalized and checked against symlinks at launch and at write time.
- Explorer owns its assigned research package. Scribe owns assigned integration,
  restructuring and shared canonical Documents; one owner or managed CLI updates common
  summaries/catalogs. All roles may record their own work, sources, checks, errors and
  judgment differences in designated records; recording is not adoption/publication authority.
  Main directly records assignment/waits/blockers/retry/stop reasons and actual Human
  decisions with source, time and affected scope. Preserve existing control authorization
  and state transitions; never promote a proposal or fabricate completion/pass.
- New runs capture `roleBoundaryPolicy: 1`; `roleDirectExceptions` advertises these capabilities.
  Historical Explorer runs without the marker retain project read-only capture behavior.
  Model/profile/permission selection remains independent; bindings never widen a read-only
  or otherwise narrower parent execution policy.

<a id="ordinary-local-commit"></a>

## 2. Ordinary local commit

- Main may directly commit an already approved exact change set after the selected route
  completes. Implementation approval alone is not commit approval; use existing identical
  commit authority without asking again. Work/Verification never commit, and code Work Unit
  integration remains runtime-owned. Main detects/assigns conflicts; semantic resolution is Work.
- Use `python3 <plugin-root>/scripts/commit.py --input <main-run>/commit.json` for a check,
  then add `--apply` only under actual authority. No arbitrary Git argv is accepted.
- The manifest contains `repository` (exact project-owned root), `branch`, `head`, `paths`
  (repository-relative exact files), `contentHashes` (SHA-256 per file, null for an already
  authorized removed file), `diffHash` (SHA-256 of `git diff --binary --no-ext-diff --no-textconv HEAD -- <selected paths present in HEAD>`;
  hash empty bytes if none are present; added files remain bound by `contentHashes` before and after staging),
  `message`, canonical `workStatePath`, and `authority: {decision: "approved", source, time, scope}`.
  The recorded authority must identify the Human's actual commit decision and exact set;
  hashes capture that approved set, including any approved pre-existing content in those files.
  Main must not infer authority from tool access or label a proposal approved.
- Use `verificationStatePath` for exact pass evidence when the selected route requires it;
  `loopStatePath` may supply an existing recorded Human skip. A scribe draft always requires
  its completed loop's recorded Human acceptance through `loopStatePath`. No extra Verification
  is required for work/plan-work; use their Work receipt and own-check evidence.
- The tool validates the canonical completed receipt, owning Main, paths, branch, HEAD,
  content/diff hashes, absence of conflicts/history operations and an empty or exactly
  approved index (pre-staged content must match the approved working files). It uses
  the same repository integration lock as managed integration/cleanup, stages only exact
  paths, rechecks the index/content and invokes ordinary `git commit -m` with hooks enabled.
  All index writers must honor this lock/serialization; external editors/Git clients are not
  controlled by this tool. A concurrent or hook failure leaves progress for the assigned
  worker; it never resets the index, bypasses hooks or silently repairs implementation.
- This grants no push, amend, rebase, reset, force, deletion, implementation edits or semantic
  conflict resolution. Source changes are not installed-session updates or deployment evidence.


<a id="coordination-records"></a>

## 3. Main coordination records

- Main may write its own sourced control/decision notes inside the run directory. For an
  accepted long-term contract, use `python3 <plugin-root>/scripts/coordination.py --input <run>/record.json`.
- The input is `announcementPath` (this run's canonical immutable task announcement) and
  `record: {kind, source, time, scope, note}`. `kind` is assignment, waiting, blocked, retry,
  stop or decision. Preserve actual Human decision evidence in source/note; never infer approval.
- The tool validates Main ownership and the existing contract binding, locks the runtime
  record writer, and appends below the existing unique execution-record marker. It cannot
  rewrite the contract or another role's result, transition execution state, record a pass,
  publish rules or edit implementation. Control actions still use the existing authorized
  runtime APIs. Shared summaries/catalogs remain assigned to scribe or the managed CLI.
