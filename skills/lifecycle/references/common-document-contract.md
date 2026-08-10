# Common Document Contract

## Contents

1. Logical model
2. Required metadata
3. Hierarchy and presentation boundary
4. Artifact profiles
5. Physical conformance
6. Validation boundary

## Logical Model

Specification and Work Unit documents share this logical model:

```text
metadata + title + table of contents + section + content + optional block
```

The common model standardizes identity, navigation, traceability, and Viewer
routing for refined and execution documents. Intake is outside this document
contract and uses its own topic-scoped `metadata + entries + blocks` ledger.

## Required Metadata

Every conforming sectioned document has these semantic metadata fields:

- `id`, `artifactType`, `schemaVersion`, and `documentVersion`.
- `projectId`, `lifecycle`, `createdAt`, and `updatedAt`.
- `language` and a theme name or stable theme id.
- `provenance` with resolvable typed source references.
- `relations` with resolvable typed artifact targets.

Specification additionally requires `documentClass` and `documentProfile.id`
plus `documentProfile.version`. Do not store the canonical title in metadata.

## Hierarchy And Presentation Boundary

Render title as H1, top-level section as H2, and one optional subsection level
as H3. Table-of-contents array order and nesting own order and depth. Reject H4
or deeper content and do not duplicate `order` or `depth` numbers.

JSON stores semantic data. It may store a theme identifier but not actual CSS,
style objects, or style-variable values. Renderers and themes own presentation.

## Artifact Profiles

- `specifications/assets/profiles/*.profile.json` owns common Specification
  sections plus purpose-specific required sections.
- `work-units/assets/profiles/work-unit.profile.json` owns Work Unit
  sections.
- `work-units/assets/profiles/work-package.profile.json` owns Work
  Package definition, durable execution, review, and report sections.
- `lifecycle/assets/schema/sectioned-document/` owns the shared title,
  table-of-contents, section, and block-index component schemas. Artifact
  skills own only artifact-specific metadata schemas and profiles.
- `lifecycle/assets/schema/document-profile.schema.json` validates the
  Specification registry and Work Unit/Work Package profile shape.

A profile section id must occur exactly once. Common and profile-specific
required sections are additive, preserve declared order, and must be disjoint.
Unknown Specification profiles remain `profile-unresolved`; generic rendering
does not make them fully valid.

## Physical Conformance

The sectioned document package stores `data/metadata.json`, `data/title.json`,
`data/table-of-contents.json`, `data/sections/<id>.json`, `blocks/index.json`,
and optional `blocks/**`. The implemented Specification profiles and Work Unit
v4 implement this physical contract. Intake v3 instead stores
`data/metadata.json`, `data/entries/<entry-id>.json`, and `blocks/**`.

The lifecycle-owned `scripts/sectioned_document.py` implements shared package
mechanics for Specification and Work Unit. Intake owns its ledger mechanics in
`intakes/scripts/intake.py` and reuses only the common block-index schema.

Each artifact-owning manager is its JSON construction and serialization owner.
Managers accept semantic data through typed command arguments. LLM callers must not compose JSON
strings or temporary JSON value files. Structured arguments use JSON Pointer
paths with typed options such as `--string`, `--integer`, `--number`,
`--boolean`, `--null`, `--string-list`, `--empty-object`, and `--empty-list`.
Scalar metadata replacements use the corresponding `--value-*` option.

LLM callers must resolve and invoke the artifact-owning script before every
canonical package operation: `intakes/scripts/intake.py`,
`specifications/scripts/specification.py`, or
`work-units/scripts/work_unit.py`. This is a hard precondition,
not a preferred path. Use the script for creation, authoritative display,
mutation, validation, applicable transitions, and block registration.

Specification and Work Unit managers share the sectioned command forms below.
Intake instead exposes `create --topic`, `show --entry`, `entry-put`,
`entry-items-put`, `topic-set`, `validate`, session commands, and block commands.

```text
create <package> --id <id> --title <title> --project-id <project> ...
show <package> [--section <section-id>]
title-set|metadata-set|section-*|block-* <package> ...
delete <package> --confirm-id <id> [--allow-invalid]
```

Delete requires an exact package-id confirmation. A package that fails full
validation is preserved unless the caller also supplies `--allow-invalid`;
even then, deletion proceeds only when descriptor-read canonical identity
matches the package directory. The lifecycle-owned engine performs
descriptor-anchored traversal and mutation, rejects symlink packages, verifies
the opened package identity before and after its atomic tombstone rename, and
does not delete a path replacement introduced between validation and use.

LLM callers must not use `apply_patch`, shell redirection, ad hoc interpreter
programs, file copy or move, temporary JSON value files, or any generic
filesystem or MCP write tool to author canonical Intake, Work Unit, or
Specification JSON. Do not add, invoke, or rely on hooks. If the owning script
is unavailable, fails, or cannot express the operation, stop before mutation,
report the exact command and capability gap, and do not create a direct-write
fallback or exception path.

The Specification manager configures the same engine with its metadata schema
and the profile declared by each package. It rejects unknown profile ids,
versions, and document-class mismatches as `profile-unresolved`; the former
custom manifest layout remains nonconforming. Work Unit v4 uses the common
package directly and validates typed Intake basis references deterministically.

A typed reference contains `artifactType`, `id`, and a project-relative `path`.
It may add `anchor: {sectionId, itemId}`. When an anchor is present, `path` must
target the sectioned package root; validation follows target metadata, TOC, and
the named section to resolve the item. Do not point anchored references directly
at a section file.

## Validation Boundary

Deterministic validation checks schema and profile versions, required metadata,
title uniqueness, table-of-contents integrity, section file identity and exact
file sets, maximum depth, resolvable typed references, registered block
integrity, and absence of actual style data. Readiness also requires the
artifact-owning skill's semantic checks and Human decision boundaries.
