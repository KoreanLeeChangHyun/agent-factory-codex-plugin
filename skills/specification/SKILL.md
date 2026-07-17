---
name: specification
description: Use when checking, creating, or updating Project Core, specification or Design Document source, or Human-facing Design Reports during Agent Factory Intake or scoped Execution. Keeps accepted requirements and evidence aligned with canonical specification JSON.
---

# Design Documents Convention

Use this skill to create or update Agent Factory design documents, including
Project Core and the Human-facing Design Report rendering.

This is an Agent Factory skill for Codex CLI use in target projects and in
this repository.

Treat `lifecycle/references/lifecycle.md` as the canonical
lifecycle sequence. The adoption summaries here apply that sequence only to
Design Document and Design Report work.

Read `lifecycle/references/common-document-contract.md` and resolve one
versioned profile from `assets/profiles/*.profile.json` before claiming a
Specification package is structurally valid. These profiles are registered
contracts; until a Specification manager and profile schemas enforce the
sectioned physical package, report the implementation gap instead of treating
the former custom manifest layout as conforming.

## Rules

- Treat only explicit user statements, Project Core contents, Design Document
  contents, requirements analysis records, repository evidence, runtime
  evidence, and review evidence as facts.
- Use the active Agent Factory skills and bundled assets from this Plugin's
  `skills/` directory according to `lifecycle`.
- Apply the Interview Decision Gate from `fact-only` before asking for Project
  Core or design decisions, or before declaring that no additional interview is
  needed.
- Do not infer missing project requirements.
- Do not add requirements that are not in the user statements, Project Core, or
  accepted Design Document basis.
- If required information is missing, ask before writing Project Core, Design
  Document content, or Design Report content.
- Create Design Document content through Human interview decisions or explicit
  accepted basis. Do not infer missing requirements into the Design Document.
- Project Core is the single canonical
  `<project-root>/.agent-factory/specifications/project-core/` package using
  the `project-core` profile. Other Specifications reference it with a
  `governed-by` typed relation and do not copy its content.
- Keep Project Core short, simple, and clear. A Design Report may render the
  resolved Project Core relation as a read-only top view, but that view is not
  another canonical copy.
- During Intake, check relevant specification source and update it when accepted
  Human requirements, feedback, decisions, or inspected evidence changes the
  specification. Record its refs, status, changes, and reason as a
  `specification-impact` content item in the canonical Intake package's
  `work-unit-basis` section through the `intake` manager's
  `section-item-put` command, then run `validate`. Set
  `attributes.status` to `aligned`, `not-applicable`, or
  `gap-accepted-for-work-unit`; the last state records an accepted
  Specification gap that an executable Work Unit basis will address.
- During Execution, update specification source when scoped implementation or
  verification reveals a new accepted design fact, then return requirement or
  scope changes to Intake.
- Treat Design Document data as JSON. The JSON model is the source of truth and
  must contain all required design document elements.
- Specifications may become large. The registered physical target is the
  common sectioned document package: `data/metadata.json`, `data/title.json`,
  `data/table-of-contents.json`, `data/sections/`, `blocks/index.json`, and
  optional `blocks/**`. Do not create a new custom manifest package and call it
  common-contract compliant.
- Store Design Document packages under
  `<project-root>/.agent-factory/specifications/<specification-id>/`.
- Record Design Document source material under the target project's current
  Design Document package. For this repository, the current package is
  `<project-root>/.agent-factory/specifications/agent-factory/`.
- Register source material that explains the Specification or rendered Design
  Report under `blocks/reference/**`.
- Register canonical diagram source and diagram artifacts under
  `blocks/diagram/**` when diagrams are authored.
- Use `diagram` for diagram type choice, source model, JavaScript
  renderer choice, diagram review, rendering boundaries, and diagram-specific
  storage or metadata rules.
- Use optional derived `report/` for Human-facing rendered Design Report files:
  `index.html`, `styles.css`, and `script.js`.
- Diagram metadata belongs in Design Document source data or in the diagram
  artifact's own metadata. Do not create `INDEX.md` files for diagrams.
- Represent the Human-facing Design Report rendering with HTML/CSS/JavaScript
  generated from the Specification data. The renderer reads metadata, title,
  table of contents, and section JSON files; rendered HTML/CSS/JavaScript is
  not the source of truth.
- Make the Design Report suitable for Human review.
- Keep the Design Document detailed enough to transform into executable Work
  Units.
- Keep customer-facing deliverables separate from internal Work Unit outputs.
- Prefer AI-readable text sources for diagrams and keep diagram source
  traceable.
- Check every Design Document or Design Report against
  `<project-root>/.agent-factory/specifications/agent-factory/blocks/reference/source/software-design-document-essential-elements.md`
  when that file exists in the target project.
- Record unspecified items explicitly.

Intake owns pre-planning specification alignment. Execution owns delivery work
and may perform scoped follow-up specification alignment. Do not maintain a
second Intake-only specification copy.

## Project Core

Project Core must define only:

- Project purpose.
- Core principles.
- Scope.
- Human approval boundaries.
- What remains unresolved.

During Work Unit Execution, when a new requirement changes design artifacts:

1. Check whether it changes Project Core.
2. If it changes project purpose, core principles, scope, approval boundaries,
   or unresolved items, update Project Core first.
3. Then update the detailed Design Document and Design Report rendering.
4. If it does not change Project Core, update only the relevant Design Document
   and Design Report detail.

## Project Timing

Specification creation is not mandatory. During Intake, record the
Specification impact and create or update a Specification only when the
recorded impact requires it. A `not-applicable` result is complete and must not
be replaced with an empty Specification package.

### New Project Start

For a new project, collect explicit Human facts in Intake and resolve
Specification status. Transition Intake to `ready` and create a Work Unit from
its basis. Create a Design Document, Design Report, or minimal Project Core only
when the recorded impact requires it and the Work Unit names it as expected
output.

### In-Progress Project Adoption

For in-progress project adoption, collect baseline reference material first:
structure, documents, commands, tests, runtime, deployment, known constraints,
open work, and unresolved decisions when explicitly available. Record them in
Intake, transition it to `ready`, then create a Work Unit from its basis. During
that Work Unit's Execution, perform the scoped Project Core, Design Document,
or Design Report update.

### Ending Or Release-Handoff Adoption

For ending or release-handoff adoption, collect final-state baseline material
first: deliverables, completed work, pending reviews, known defects, release
constraints, deployment status, handoff needs, and unresolved decisions. Use a
`ready` Intake to create the Work Unit, then during its Execution update Project
Core only when the required Project Core fields change and update the Design
Document around the scoped finalization, rework, release, deliverables,
handoff, verification, and unresolved decisions.

### Maintenance Or Operations Adoption

For maintenance or operations adoption, collect operations baseline material
first: runtime, deployment, incidents, logs, monitoring, known risks, current
behavior, maintenance request, and approval boundaries. Use a `ready` Intake to
create the Work Unit, then during its Execution update Project Core only when the
request changes purpose, principles, scope, approval boundaries, or unresolved
items and update the Design Document within the scoped operational impact.

Do not treat any baseline as a replacement for Project Core, Design Document,
Design Report, Work Units, Work Unit Outputs, or customer-facing deliverables.

When a Design Document or Design Report exists, Intake records it as a
specification reference. When it does not exist, Intake records the gap and its
ready Work Unit basis may define a Work Unit whose output is that specification.

## Required Profile Content

The resolved `assets/profiles/*.profile.json` file owns the exact common and
profile-specific required sections. Require each declared section exactly once
in profile order. Do not impose architecture, API, data-model, class-model, or
requirements sections on an unrelated Specification profile.

Every Specification also satisfies the common metadata, hierarchy,
traceability, style boundary, and block rules in
`lifecycle/references/common-document-contract.md`. Record applicable
cross-cutting concerns such as security, privacy, operations, migration,
quality, diagrams, glossary, and Work Unit decomposition only when the resolved
profile or accepted scope requires them. Record unresolved applicable content
explicitly rather than inventing it.

A Design Report renders the canonical Specification sections and resolved
typed relations. Rendering a Project Core relation does not make Project Core
a required copied section of every Specification.

## Handoff

The Design Report is not the execution plan. It is Human-facing detailed design
output generated from Design Document data. It can be produced or updated by a
Work Unit and become a specification input to a later Intake. It is not a
direct Work Unit basis.

When a Design Document or Design Report does not yet exist or does not cover
the request, Intake records and validates that gap. Its ready Work Unit basis
can define a Work Unit whose expected output is the missing specification or
Design Report work.

## Output

- Produce or update the single canonical Project Core package when it is in
  scope.
- Produce or update the Design Document JSON source.
- Produce or update the Human-facing Design Report rendering when needed.
- Record and render the `governed-by` Project Core relation without copying
  Project Core content into the governed Specification.
- Summarize only the facts recorded.
- List unresolved decisions separately.
