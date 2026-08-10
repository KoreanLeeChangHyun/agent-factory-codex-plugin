# Specification Convention

Use this capability to create or update Agent Factory Specifications, including
Project Core and the canonical Specification JSON consumed by the separate
Chrome extension Design Report viewer.

This is an Agent Factory skill for Codex CLI use in target projects and in
this repository.

## Mandatory Manager Script Gate

Treat `scripts/specification.py` as a hard precondition for every canonical
Specification package operation. Resolve it from the parent `specifications` skill root and
invoke it before creating, showing, mutating, validating, registering or
removing blocks, or recovering Project Core or any other Specification package.

- Use the manager command that owns the requested operation. Use `show` and
  `validate` for authoritative package inspection and validation.
- Supply only typed semantic arguments. Let the manager construct, serialize,
  order, version, and transactionally write canonical JSON.
- Never create, update, delete, replace, move, or repair canonical
  Specification JSON with `apply_patch`, shell redirection, an ad hoc program,
  file copy or move, temporary JSON files, or any generic filesystem or MCP
  write tool.
- Never add, invoke, or rely on a hook to enforce this rule. The skill
  instruction and exact manager invocation are the enforcement contract.
- If `scripts/specification.py` is unavailable, fails, or cannot express the
  required operation, stop before mutation. Report the exact command, package,
  operation, and failure or capability gap. Do not fall back to direct JSON
  editing and do not create an exception path.
- When a previously valid Specification is unreadable only because repository
  lifecycle cleanup removed one provenance target, use `source-ref-prune` with
  the exact artifact type, id, and path. It refuses an existing target and
  commits only when the remaining package passes full validation.

Treat `lifecycle/references/lifecycle.md` as the canonical
lifecycle sequence. The adoption summaries here apply that sequence only to
Specification work and Design Report review through the external viewer.

Read `lifecycle/references/common-document-contract.md` and resolve one
versioned profile from `assets/profiles/*.profile.json` before claiming a
Specification package is structurally valid. Use
`scripts/specification.py` to create, mutate, and validate the common sectioned
physical package. The manager resolves the profile declared in package
metadata and rejects unknown or mismatched profiles as `profile-unresolved`.
The former custom manifest layout remains nonconforming and has no implicit
migration path.

The lifecycle-owned sectioned-document engine is the only document skeleton
and JSON serialization owner. `scripts/specification.py` remains the
Specification controller for profile selection and semantic validation. Supply
only typed semantic data arguments to mutation commands; never compose JSON
strings or temporary JSON value files.

Use only `scripts/specification.py` with typed semantic arguments for canonical
Specification package management. The Mandatory Manager Script Gate applies
without an exception.

The manager's canonical package command examples are:

```text
python3 scripts/specification.py create <package> --id <id> --title <title> --project-id <project> --profile <profile-id> --language <language> --theme <theme>
python3 scripts/specification.py show <package> [--section <section-id>]
python3 scripts/specification.py delete <package> --confirm-id <id> [--allow-invalid]
python3 scripts/specification.py title-set <package> <title>
python3 scripts/specification.py metadata-set <package> <field> <typed-data-arguments>
python3 scripts/specification.py section-put <package> <typed-data-arguments>
```

Use `--allow-invalid` only as the explicit opt-in for deleting a package that
fails full validation; the manager still requires exact confirmation and
canonical identity.

## Rules

- Treat only explicit user statements, Project Core contents, Specification
  contents, requirements analysis records, repository evidence, runtime
  evidence, and review evidence as facts.
- Use the active Agent Factory skills and bundled assets from this Plugin's
  `skills/` directory according to `lifecycle`.
- Apply the Interview Decision Gate from `rules` before asking for Project
  Core or design decisions, or before declaring that no additional interview is
  needed.
- Do not infer missing project requirements.
- Do not add requirements that are not in the user statements, Project Core, or
  accepted Specification basis.
- If required information is missing, ask before writing Project Core or
  Specification content.
- Create Specification content through Human interview decisions or explicit
  accepted basis. Do not infer missing requirements into the Specification.
- Project Core is the single canonical
  `<project-root>/.agent-factory/specifications/project-core/` package using
  the `project-core` profile. Other Specifications reference it with a
  `governed-by` typed relation and do not copy its content.
- Keep Project Core short, simple, and clear. A Design Report may render the
  resolved Project Core relation as a read-only top view, but that view is not
  another canonical copy.
- During Intake, check a relevant Specification when one exists or when the
  Human explicitly requires one. Append the check and its reference as an
  Intake entry. Specification creation remains optional; the Main Agent decides
  whether a reusable refined contract is warranted unless the Human states a
  condition, and explicit Human conditions take priority.
- During Execution, update specification source when scoped implementation or
  verification reveals a new accepted design fact, then return requirement or
  scope changes to Intake.
- Treat Specification data as JSON. The JSON model is the source of truth and
  must contain all required Specification elements.
- Specifications may become large. The registered physical target is the
  common sectioned document package: `data/metadata.json`, `data/title.json`,
  `data/table-of-contents.json`, `data/sections/`, `blocks/index.json`, and
  optional `blocks/**`. Do not create a new custom manifest package and call it
  common-contract compliant.
- Run `python3 scripts/specification.py check-schemas` after changing the
  Specification metadata schema or any registered profile. Create a package
  with `create --profile <profile-id>`, then use the manager's title, metadata,
  section, and block commands for mutations and run `validate` afterward.
- Specification packages currently have the deterministic lifecycle state
  `draft`. The manager intentionally exposes no transition command. Do not
  infer lifecycle states from Intake or Work Unit lifecycles.
- Store Specification packages under
  `<project-root>/.agent-factory/specifications/<specification-id>/`.
- Register source material that explains the Specification under
  `blocks/reference/**`.
- Register canonical diagram source and diagram artifacts under
  `blocks/diagram/**` when diagrams are authored.
- Use `specifications` for diagram type choice, canonical source model, diagram review,
  and diagram-specific storage or metadata rules. The separate Chrome extension
  owns canonical Specification package rendering and Human-facing Design Report
  rendering behavior.
- Diagram metadata belongs in Specification source data or in the diagram
  artifact's own metadata. Do not create `INDEX.md` files for diagrams.
- Treat the Design Report as a Human-facing view that the separate Chrome
  extension derives from validated canonical Specification JSON. Do not create
  `report/`, `report/index.html`, `report/styles.css`, `report/script.js`, or any
  other derived HTML, CSS, or JavaScript viewer files in a Specification
  package.
- Keep the canonical Specification data suitable for Human review through the
  external viewer. The viewer's loading protocol and implementation remain
  outside the Specification capability unless the Human explicitly scopes that separate project.
- Keep the Specification detailed enough to transform into executable Work
  Units.
- Keep customer-facing deliverables separate from internal Work Unit outputs.
- Prefer AI-readable text sources for diagrams and keep diagram source
  traceable.
- Check every Specification against
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
- Human decision boundaries.
- What remains unresolved.

During Work Unit Execution, when a new requirement changes design artifacts:

1. Check whether it changes Project Core.
2. If it changes project purpose, core principles, scope, decision boundaries,
   or unresolved items, update Project Core first.
3. Then update the detailed Specification JSON.
4. If it does not change Project Core, update only the relevant Specification
   JSON. The external viewer derives the Design Report view from that source.

## Project Timing

Specification creation is not mandatory. Reference an existing applicable
Specification when useful. Otherwise the Main Agent may create a Work Unit
directly from sufficient Intake entries. Create or update a Specification only
when a reusable refined contract is warranted or the Human requires it.

### New Project Start

For a new project, collect explicit Human facts in Intake and create a Work
Unit from the exact sufficient entries. Create a Specification or minimal
Project Core only when needed and name it as Work Unit output. The
external viewer derives the Design Report view from the resulting canonical
Specification JSON.

### In-Progress Project Adoption

For in-progress project adoption, collect baseline reference material first:
structure, documents, commands, tests, runtime, deployment, known constraints,
open work, and unresolved decisions when explicitly available. Record them in
Intake, then create a Work Unit from the exact sufficient entries. During
that Work Unit's Execution, perform the scoped Project Core or Specification
update.

### Ending Or Release-Handoff Adoption

For ending or release-handoff adoption, collect final-state baseline material
first: deliverables, completed work, pending reviews, known defects, release
constraints, deployment status, handoff needs, and unresolved decisions. Use
the exact relevant Intake entries to create the Work Unit, then during Execution update Project
Core only when the required Project Core fields change and update the
Specification around the scoped finalization, rework, release, deliverables,
handoff, verification, and unresolved decisions.

### Maintenance Or Operations Adoption

For maintenance or operations adoption, collect operations baseline material
first: runtime, deployment, incidents, logs, monitoring, known risks, current
behavior, maintenance request, and Human decision boundaries. Use the exact
relevant Intake entries to create the Work Unit, then during Execution update Project Core only when the
request changes purpose, principles, scope, decision boundaries, or unresolved
items and update the Specification within the scoped operational impact.

Do not treat any baseline as a replacement for Project Core, Specification,
Work Units, Work Unit Outputs, or customer-facing deliverables.

When a Specification exists, Intake records its canonical package reference.
When it does not exist, no placeholder or mandatory gap record is required; a
Work Unit may create one when its scope requires that output.

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

The separate Chrome extension renders the Design Report view from canonical
Specification sections and resolved typed relations. Rendering a Project Core
relation does not make Project Core a required copied section of every
Specification.

## Handoff

The Design Report is not a stored artifact or the execution plan. It is a
Human-facing view derived at viewing time by the separate Chrome extension from
canonical Specification data. A Work Unit produces or updates the canonical
Specification JSON, not Design Report HTML, CSS, or JavaScript. Intake and Work
Unit traceability reference the canonical Specification package rather than the
derived view.

When a Specification does not yet exist or does not cover the request, a Work
Unit may still be created directly from Intake entries and may optionally name
the missing or incomplete Specification JSON as expected output.

## Output

- Produce or update the single canonical Project Core package when it is in
  scope.
- Produce or update the Specification JSON source.
- Do not produce Design Report HTML, CSS, or JavaScript; the separate Chrome
  extension owns the Human-facing derived view.
- Record the `governed-by` Project Core relation without copying Project Core
  content into the governed Specification.
- Summarize only the facts recorded.
- List unresolved decisions separately.
