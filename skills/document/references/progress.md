# Progress writing

<a id="authority-and-scope"></a>

## 1. Authority and scope

- Apply the shared [Document requirements](../SKILL.md).
- Use Progress for contract task progress, current status, completed work, blockers and
  remaining work. Use Refined for research, analysis and reusable working knowledge.
- A Progress document records observations; it grants no execution, approval or
  Specification authority. Link existing task/run evidence when available rather
  than treating the document as the runtime state store.
- Link the runtime-generated progress view when a managed loop returns one; see
  [runtime progress and repair](../../agent/references/home-runtime.md#progress-projection).
  A missing or stale view is a reporting issue, not evidence that work completed.
- Main owns the shared contract progress record and updates it from exact Work
  results and Verification receipts. Workers return their progress in their results;
  they do not need write authority over this shared record to finish in-scope work.
- Preserve existing Refined documents with the `process` category unless migration is explicitly
  requested. New progress records use this type.

<a id="package-and-metadata"></a>

## 2. Package and metadata

- Store each contract at `docs/progress/<contract-id>/`. Use `contract-v<N>.md` for
  versioned contract sections and the execution record bound to that version.
  Keep `progress.md` as the catalog entry and contract version index. Existing
  `progress.md` task records retain their historical content.
- Record task IDs, actual status, check evidence and blockers in the bound contract
  version's execution-record section. Preserve prior contract sections; revise them
  only by writing a new version. Link sibling attachments from the contract or index.
- Each `contract-v<N>.md` records the same contract ID and numeric version represented by
  its directory and filename: metadata `document-type: processed`, `contract-id: <id>` and
  integer `contract-version: <N>`. `progress.md` uses `document-type: progress` and the same
  `contract-id`. After writing, run `catalog_documents.py --project-root <root>` and fix
  every reported error before claiming the contract was saved. Link every sibling attachment from `progress.md` or a
  contract version; missing, unlinked or nested attachment content is invalid.
- A direct-execution record documents work that ran without a contract. Its
  `progress.md` sets `record-type: direct-execution`, omits `contract-version` and has no
  `contract-v<N>.md`; the catalog lists it with no contract versions. Use it only to keep
  existing contract-less records; new direct (worker mode) work needs no
  `docs/progress/` record unless the Human requests one. Do not write a contract after
  the fact to fill the gap.
- Use `status` for a current snapshot and `worklog` for chronological progress.
- Catalog and search discover canonical `docs/progress/` records, legacy root `progress/` contracts and older `SKILL.md` packages;
  they are not activated as Skills
  or exported to `.codex/skills/`, `.claude/skills/` or `.agents/skills/`.
- Catalog entries expose contract versions, task IDs and attachments. Canonical/legacy
  duplicate identities and inconsistent contract metadata fail instead of being hidden.

<a id="writing"></a>

## 3. Writing

- Identify the task or scope and the observation date so readers can assess freshness.
- Record relevant completed work, current work, remaining work and blockers.
- Distinguish reported completion from checks actually performed. Link evidence
  where available and retain unresolved decisions without inventing outcomes.
- For a status snapshot, update the current state. For a worklog, retain dated
  entries so earlier observations are not presented as the current state.
