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
physical contract. Reusable schemas stay under this skill's `assets/schema/`;
target packages do not copy them.

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
`worktreePath`. The branch must equal `work-unit/<work-unit-id>`.

## Blocks And Evidence

Large logs, screenshots, and binary or non-JSON material belong under
`blocks/**`. Register them with `block-put`; never edit the index manually.
Fast validation checks exact file set and byte size. Full validation also
checks SHA-256. Orphans, missing files, symlinks, traversal, and tampering are
invalid.

Review evidence arrays name registered block paths. A passing quality check or
report without evidence is invalid for transition to `review`.

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
- `blocked`: requires an unresolved blocking `open-item`.

The metadata schema owns allowed status transitions. Semantic gates add the
artifact-specific conditions above.

## Manager Workflow

```bash
python3 assets/scripts/work_unit.py check-schemas
python3 assets/scripts/work_unit.py create \
  <project-root>/.agent-factory/work-units/<id> \
  --id <id> --title <title> --project-id <project-id> --theme default
python3 assets/scripts/work_unit.py section-items-put <package> <section-id> \
  --value-file <items.json>
python3 assets/scripts/work_unit.py metadata-set <package> readiness \
  --value-file <readiness.json>
python3 assets/scripts/work_unit.py validate <package> --full
python3 assets/scripts/work_unit.py transition <package> ready
```

Use `section-item-put` for one item and `section-items-put` for a batch.
Use `show <package> --section <id>` for focused reads of large documents.
Mutations are serialized per package, increment one patch revision, and use a
recovery journal. Manual canonical edits are recovery-only exceptions and must
be followed by full validation.
