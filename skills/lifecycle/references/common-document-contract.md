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

- `intake/assets/profiles/intake.profile.json` owns the Intake sections.
- `specification/assets/profiles/*.profile.json` owns common Specification
  sections plus purpose-specific required sections.
- `work-unit-planner/assets/profiles/work-unit.profile.json` owns Work Unit
  sections.
- `lifecycle/assets/schema/document-profile.schema.json` validates the
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
and optional `blocks/**`. Intake v2 and Work Unit v4 implement this physical
contract.

Specification profiles are registered contracts; a Specification manager and
profile schemas must implement the same physical package before a package is
claimed as conforming. Work Unit v4 uses the common package directly and
validates typed Intake basis references deterministically.

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
