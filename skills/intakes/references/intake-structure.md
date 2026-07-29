# Intake Package Contract

## Contents

1. Document hierarchy
2. Package files
3. Intake profile
4. Section content
5. Validation and readiness
6. Scale boundary

## Document Hierarchy

Use this Human-readable hierarchy:

```text
Title (H1)
Table of contents
Section (H2)
  Subsection (H3, optional)
```

Allow no subsection below H3. The manager generates
`data/table-of-contents.json`; its array order owns rendering order and its
nesting owns depth. Do not store separate `order` or `depth` values.

## Package Files

- `data/metadata.json`: identity, type, versions, project, lifecycle, time,
  language, theme name, provenance, typed relations, and readiness.
- `data/title.json`: the single canonical document title.
- `data/table-of-contents.json`: manager-owned ordered section and subsection
  index with an integrity digest.
- `data/sections/<section-id>.json`: one independently validated top-level
  section and its optional one-level subsections.
- `blocks/index.json`: manager-owned block path, media type, description,
  SHA-256, and byte-size index.
- `blocks/**`: package-local non-JSON or large source material.

## Intake Profile

`assets/profiles/intake.profile.json` owns these required sections in order:

1. `request-and-goal`: Human request, desired outcome, and success meaning.
2. `context-and-scope`: context, scope, and out of scope.
3. `stakeholders-and-approval`: stakeholders, Human decision owner, and
   approval boundaries.
4. `evidence-and-findings`: Human, interview, user-observation, web, repository,
   runtime, data, and document evidence with facts distinct from interpretation.
5. `requirements-and-constraints`: requirements, constraints, assumptions, and
   acceptance criteria.
6. `decisions-and-open-items`: decision status, alternatives when applicable,
   conflicts, risks, and blocking or non-blocking open items.
7. `work-unit-basis`: specification impact, executable candidates,
   traceability, dependencies, and execution order.

The profile also declares the only optional top-level sections. A required
section must appear exactly once and required-section relative order must not
change.

## Section Content

Each section owns `id`, `title`, `content`, and `subsections`. Each content item
uses:

```json
{
  "id": "stable-item-id",
  "kind": "evidence",
  "content": {},
  "attributes": {},
  "sourceRefs": [],
  "blockRef": "blocks/optional/path"
}
```

Only `id`, `kind`, and `content` are universally required. Use `sourceRefs` for
typed artifact traceability. Use `blockRef` only for a block registered through
`block-put`. For an unresolved open item, use kind `open-item` and record
  `attributes.blocking` and `attributes.resolved` explicitly. Every typed
  reference requires `artifactType`, `id`, and a project-relative resolvable
  `path`. Actual CSS, style objects, and style-variable values are not semantic
  Intake content; attach source evidence as a registered block when needed.

Capability skills add or replace individual content items with
`section-item-put`. For many items in the same section, use one
`section-items-put` array so the package receives one document revision:

- Human requests and feedback: `request-and-goal` or the relevant semantic
  section.
- Web search: `evidence-and-findings`, normally kind `web-evidence`.
- Internal analysis: `evidence-and-findings`, normally kind
  `internal-evidence`.
- User research: `evidence-and-findings`, normally kind `user-evidence`, with
  observed behavior separate from participant statements and interpretations.
- Interview: `evidence-and-findings` for the interview record and
  `decisions-and-open-items` for its accepted decision.
- Specification: `work-unit-basis`, kind `specification-impact`.
- Synthesis: requirements, decisions, acceptance criteria, open items, and
  Work Unit basis remain in their owning sections rather than a duplicate
  synthesis object.

The profile-required `evidence` family is satisfied by `evidence`,
`web-evidence`, `internal-evidence`, `user-evidence`, or `interview`; capability
skills do not add a duplicate generic evidence item only to satisfy readiness.
Every `specification-impact` item records `attributes.status` as exactly one of
`aligned`, `not-applicable`, or `gap-accepted-for-work-unit`. An accepted gap
must be carried into an executable Work Unit basis rather than treated as an
aligned Specification.

## Validation And Readiness

The manager validates every component independently and then validates package
relationships. It rejects missing required sections, undeclared sections,
duplicate IDs, table-of-contents drift, H4-depth data, unsafe paths, missing
typed path targets, unregistered, orphaned, or modified blocks, actual style
data, invalid transitions, and incomplete ready-state profile content. Normal
`validate` is the fast authoring check; `validate --full` recomputes block
hashes and is mandatory at the `ready` boundary.

Use `draft` while authoring, `validating` during semantic review, `blocked` only
with an unresolved blocking open item, and `ready` only after deterministic and
semantic checks pass. New feedback may reopen `ready` to `draft`.
Use terminal `closed` for completed historical records and terminal
`superseded` for records replaced by a later canonical decision or contract.
Both require an evidence-backed disposition item and must not be reopened.
A canonical mutation reopens `ready` as `draft` and invalidates semantic
readiness in the same transaction. Canonical mutation is rejected for terminal
`closed` and `superseded` packages.

## Scale Boundary

Section files prevent one growing evidence collection from forcing every
reader to load the whole document. Use `show --section` for focused structural
validation and reading; it deliberately does not parse unrelated section
content, so it never replaces package-level `validate`.
The manager streams block copies and hashes instead of loading complete block
files into memory. Batch large same-section updates with `section-items-put`.
The package recovery journal protects multi-file commits. Keep the title, metadata, and
table of contents small.

If one section becomes difficult to scan, first divide it into one level of
subsections. If that remains insufficient, create another top-level
profile-declared section or a separate Intake. Do not add deeper nesting.
