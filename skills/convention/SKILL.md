---
name: convention
description: Apply Agent Factory's core model and cross-cutting conventions for project structure, development, libraries, design, annotations, Document types, and Skill ownership.
---

# Agent Factory Convention

## Entry contract

Use this Skill whenever work designs, reviews, or explains Agent Factory core
concepts or applies its cross-cutting conventions, including Document types,
capability boundaries, Skill ownership and naming, document storage,
project structure, development, libraries, design, or annotations. Read every
applicable reference before acting.

Agent Factory has exactly five public distributed Skills: `gather`,
`convention`, `agent`, `document`, and `workspace`. Explorer and Interview remain core
capabilities rather than public Skill entry points. Convention owns their
durable semantics and the paired AI-facing core representation; Agent's Main
and Work roles apply them within the managed execution graph.

Treat Original, Processed, and Specification Documents as loosely related
logical types independent of storage. Their conceptual ordering is
`Original -> Processed -> Specification`, but the arrows express only possible
derivation or evidence relationships. They are not a mandatory pipeline, state
machine, required transition, maturity scale, or one-to-one mapping. A
Document may remain in one type, and relationships may be absent or have any
cardinality. Preserve inspectable provenance for actual derivation or evidence
relationships without inferring completeness, acceptance, authority, or
automatic promotion from a type name. Preserve Original Documents in a native
or source-appropriate form, including fidelity, identity, provenance, and
collection context; never impose one canonical original format. Under the
current/default `.agent-factory/` local adapter, active Processed Documents use
Markdown (`.md`), but that representation does not make the logical Processed
type storage-dependent or turn preserved `processed/legacy-inquery/` material
into an active target or precedent. An explicitly resolved project server or
external backend may own any document root without weakening provenance,
authority, isolation, semantic alignment, accessibility, or security. Never
invent or silently select a backend.

A Specification is accepted and reconciled project knowledge represented as
one semantic body by an
AI-facing Skill and a Human-facing Korean HTML, CSS, and JavaScript document.
Always keep both representations semantically synchronized. A one-sided change
is incomplete and unacceptable; if synchronization cannot be achieved, the
change or run must not be reported as completed.

Keep distributed plugin Skills below `<plugin-root>/skills/`. Keep consumer
Project Skills below `<project-root>/.codex/skills/<category>-<name>/`. Use the
accepted `<category>-<name>` form for newly named Skill identities when the
owning context requires two parts, and preserve existing accepted identities.

## Reference routing

- `references/agent-factory-core.md`: Apply the accepted Document model,
  capabilities, engineering stack, Skill ownership, storage-independent
  document roles, and Specification paired representations.
- `references/directory-structure.md`: Apply the recommended local/default
  project layout and ownership boundaries.
- `references/development.md`: Apply shared implementation and maintenance
  conventions while preserving the owning project's established patterns.
- `references/libraries.md`: Select dependencies and formats using the
  recommended library policy.
- `references/design.md`: Apply shared Human-facing interface and document
  design conventions.
- `references/annotation.md`: Create or review comments, documentation
  comments, and traceable TODO annotations.
- `references/svg-icon.md`: Apply the detailed SVG-only icon convention when
  user-facing icons are involved.
- `references/diagrams.md`: Select and author ERD, game-behavior, and sequence
  diagrams, and keep AI-readable Mermaid sources aligned with Human-facing
  representations.
- `references/explorer.md`: Apply Explorer's information, provenance, and
  authority boundaries when defining or routing evidence exploration.
- `references/interview.md`: Apply Interview's information and Human-authority
  boundaries when Main conducts adaptive elicitation.

## Bootstrap assets

`assets/AGENTS.md` is the plugin-provided project instruction template.
`scripts/init_agents.py` copies it once to `<project-root>/AGENTS.md` and refuses
to overwrite any existing path. The plugin manifest itself does not inject
project files.
