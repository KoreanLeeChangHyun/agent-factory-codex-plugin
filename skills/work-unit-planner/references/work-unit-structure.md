# Work Unit v4 Structure

## Contents

1. Canonical package
2. Metadata and typed references
3. Sections and required kinds
4. Blocks and evidence
5. Lifecycle gates
6. Manager workflow

## Canonical Package

```text
<project-root>/.agent-factory/work-units/<id>/
  data/
    metadata.json
    title.json
    table-of-contents.json
    sections/
      <section-id>.json
  blocks/
    index.json
    **
```

`metadata.json`, `title.json`, the manager-owned TOC, one file per section,
and `blocks/index.json` are required. Schema version `4.0.0` is the current
physical contract. The Work Unit metadata schema stays under this skill;
shared structural schemas and package mechanics stay under `lifecycle/assets/`.
Target packages do not copy them.

The canonical hierarchy is title -> section -> optional subsection. The TOC
owns order and its SHA-256 digest prevents unmanaged structural edits. Section
files own semantic content. A batch item update is one document revision even
when it contains thousands of items.

## Metadata And Typed References

Metadata owns identity, project, lifecycle, timestamps, language, theme name,
provenance, relations, and readiness. Title exists only in `title.json`.

A typed reference is:

```json
{
  "artifactType": "intake",
  "id": "source-intake",
  "path": ".agent-factory/intakes/source-intake",
  "anchor": {"sectionId": "work-unit-basis", "itemId": "BASIS-001"}
}
```

`path` is project-relative and, when `anchor` is present, must target the
sectioned package root. The manager reads target metadata, TOC, and the named
section, verifies identity and TOC integrity, then resolves `itemId` in the
section or one of its subsections. A ready Work Unit requires an
`intake-basis-ref` anchored to `work-unit-basis` in a fully validated ready
Intake.

## Sections And Required Kinds

`assets/profiles/work-unit.profile.json` is the single source of truth. Its
required sections and kinds are:

| Section | Required kinds |
|---|---|
| `basis` | `intake-basis-ref` |
| `work-definition` | `goal`, `scope`, `out-of-scope`, `expected-output` |
| `plan` | `plan-step` |
| `execution-context` | `execution-context` |
| `acceptance-and-verification` | `acceptance-criterion`, `definition-of-done`, `test-criterion`, `quality-check` |
| `execution` | `execution-result` |
| `ai-review` | `ai-checklist`, `ai-review-result` |
| `human-review` | `human-checklist`, `human-review-method`, `human-review-result` |
| `report` | `report-result` |

Each content item requires `id`, `kind`, and `content`; it may include
`attributes`, `sourceRefs`, and a registered `blockRef`. Item ids are unique
within their container. Section and subsection ids are unique document-wide.

The execution-context item content must include `goalId`, `objective`,
`execInvocation`, `executionAgent`, `repository`, `baseRef`, `branch`, and
`worktreePath`. The branch must equal `work-unit/<work-unit-id>`, and
`worktreePath` must equal the absolute
`<repository>/.agent-factory/worktree/<work-unit-id>` path. Existing registered
legacy worktrees keep their recorded path only for rework, inspection, and
Human-approved cleanup; new Work Units use the canonical path.

Active execution also stores one manager-owned `execution-state` item:

```json
{
  "contractVersion": "1.0.0",
  "state": "running",
  "subject": {"algorithm": "gitCommit", "digest": "<head-commit>"},
  "currentRevision": 1,
  "currentAttempt": 1,
  "invocationId": "<primary-execution-invocation-id>",
  "invocationChain": ["<primary-execution-invocation-id>"],
  "history": []
}
```

This item contract version is independent of package `schemaVersion: 4.0.0`.
Consumers that do not find the item may render an existing terminal v4 package
as legacy history. Consumers that find an unknown `contractVersion` must show
it as unsupported and must not treat its evidence or approval as current.
Consumers use named JSON fields rather than array position. A current passing
result carries `attributes.executionTarget` with `contractVersion`, `revision`,
`attempt`, `invocationId`, and `headCommit`; all five fields must equal the
current state.

## Blocks And Evidence

Large logs, screenshots, and binary or non-JSON material belong under
`blocks/**`. Register them with `block-put`; never edit the index manually.
Fast validation checks exact file set and byte size. Full validation also
checks SHA-256. Orphans, missing files, symlinks, traversal, and tampering are
invalid.

Review evidence arrays name registered block paths. A passing quality check or
report without evidence is invalid for transition to `review`.

After a Human-approved integration, use `integration-put` to register the raw
`worktree.py integrate` JSON under `blocks/**`. The manager validates Work Unit,
repository, source branch, target branch, worktree, Human decision, commit,
relationship, strategy, and operation-result fields against the package and
stores a normalized `integration-result` in `report` in the same transaction.
The same receipt and path is idempotent. A different receipt must use a new
path, so prior integration snapshots are never overwritten.

## Lifecycle Gates

```text
backlog -> ready -> working -> review -> done
    \         \         \         \
     +--------+---------+---------> blocked
```

- `ready`: all readiness flags true, review timestamp present, no blocker,
  every required kind present, execution context complete, branch canonical,
  and anchored Intake basis valid.
- `working`: execution may proceed in the registered branch/worktree.
- `review`: execution is complete and verified; quality check, AI review and
  checklist, and report verification pass; required evidence is registered.
- `done`: only from review with `--human-review approved`. The manager records
  Human approval and timestamp in the same transaction.
- `execution-init`: ready only; creates or resets a pristine planned
  `execution-state/v1` at revision 1 and binds the inspected Git head.
- `attempt-start`: ready or working; starts attempt 1 or archives the current
  attempt and increments it for a same-revision retry. It transitions ready to
  working and invalidates current outcome gates atomically.
- `attempt-resume`: working only; appends a new Codex session id to the current
  attempt's invocation chain without changing attempt or primary invocation.
- `rework-start --human-decision approved`: review only; archives the reviewed
  attempt, increments revision, clears attempt identity, invalidates current
  results and approval, and returns the package to working atomically. A later
  `attempt-start` begins attempt 1 of that revision.
- `blocked`: requires an unresolved blocking `open-item`.

The metadata schema owns allowed status transitions. Semantic gates add the
artifact-specific conditions above.
Integration receipt registration is a separate state axis and therefore does
not transition or reopen `working`, `review`, or `done`.

## Manager Workflow

```bash
python3 assets/scripts/work_unit.py check-schemas
python3 assets/scripts/work_unit.py create \
  <project-root>/.agent-factory/work-units/<id> \
  --id <id> --title <title> --project-id <project-id> --theme default
python3 assets/scripts/work_unit.py section-items-put <package> <section-id> \
  <typed-data-arguments>
python3 assets/scripts/work_unit.py metadata-set <package> readiness \
  --boolean /contractValid true \
  --boolean /intakeTraceabilityValid true \
  --boolean /definitionComplete true \
  --boolean /executionContextComplete true \
  --boolean /verificationPlanComplete true \
  --string /reviewedAt <date-time> \
  --empty-list /findings
python3 assets/scripts/work_unit.py validate <package> --full
python3 assets/scripts/work_unit.py transition <package> ready
python3 assets/scripts/work_unit.py execution-init <package> \
  --head-commit <inspected-head-commit>
python3 assets/scripts/work_unit.py attempt-start <package> \
  --invocation-id <execution-invocation-id> --head-commit <inspected-head-commit>
python3 assets/scripts/work_unit.py attempt-resume <package> \
  --invocation-id <resumed-codex-session-id>
python3 assets/scripts/work_unit.py rework-start <package> \
  --human-decision approved
```

Use `section-item-put` for one item and `section-items-put` for a batch.
Use typed JSON Pointer data arguments; the manager owns JSON construction and
serialization. Do not create JSON input files or pass JSON strings.
Use `show <package> --section <id>` for focused reads of large documents.
Mutations are serialized per package, increment one patch revision, and use a
recovery journal. Manual canonical edits are recovery-only exceptions and must
be followed by full validation.
