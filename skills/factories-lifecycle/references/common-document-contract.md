# Common Document Contract

## Contents

1. Logical model
2. Required metadata
3. Hierarchy and presentation boundary
4. Artifact profiles
5. Physical conformance
6. Validation boundary

## Logical Model

Intake, Specification, and Work Unit documents share this logical model:

```text
metadata + title + table of contents + section + content + optional block
```

The common model standardizes identity, navigation, traceability, and Viewer
routing. It does not give the three artifact types the same required section
list. Each owning skill supplies a versioned document profile.

## Required Metadata

Every conforming document has these semantic metadata fields:

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

- `intakes/assets/profiles/intake.profile.json` owns the Intake sections.
- `specifications/assets/profiles/*.profile.json` owns common Specification
  sections plus purpose-specific required sections.
- `work-units-manager/assets/profiles/work-unit.profile.json` owns Work Unit
  sections.
- `factories-lifecycle/assets/schema/sectioned-document/` owns the shared title,
  table-of-contents, section, and block-index component schemas. Artifact
  skills own only artifact-specific metadata schemas and profiles.
- `factories-lifecycle/assets/schema/document-profile.schema.json` validates the
  Specification registry and Work Unit profile shape. The
  Intake manager validates its operational profile and required content-kind
  extension directly.

A profile section id must occur exactly once. Common and profile-specific
required sections are additive, preserve declared order, and must be disjoint.
Unknown Specification profiles remain `profile-unresolved`; generic rendering
does not make them fully valid.

## Physical Conformance

The sectioned document package stores `data/metadata.json`, `data/title.json`,
`data/table-of-contents.json`, `data/sections/<id>.json`, `blocks/index.json`,
and optional `blocks/**`. Intake v2, the implemented Specification profiles,
and Work Unit v4 implement this physical contract.

The lifecycle-owned `scripts/sectioned_document.py` implements the
shared package I/O, table-of-contents, section, block, transaction, and
validation mechanics. Artifact managers configure that engine with their own
metadata schema, profile, package root, lifecycle, readiness, and semantic
validation rules.

The shared engine is the only JSON construction and serialization owner.
Artifact managers accept semantic data through typed command arguments and
delegate canonical writes to the engine. LLM callers must not compose JSON
strings or temporary JSON value files. Structured arguments use JSON Pointer
paths with typed options such as `--string`, `--integer`, `--number`,
`--boolean`, `--null`, `--string-list`, `--empty-object`, and `--empty-list`.
Scalar metadata replacements use the corresponding `--value-*` option.

LLM callers must resolve and invoke the artifact-owning script before every
canonical package operation: `intakes/scripts/intake.py`,
`specifications/scripts/specification.py`, or
`work-units-manager/scripts/work_unit.py`. This is a hard precondition,
not a preferred path. Use the script for creation, authoritative display,
mutation, validation, transitions, block registration, and recovery.

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
