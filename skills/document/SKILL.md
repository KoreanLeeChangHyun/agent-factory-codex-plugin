---
name: document
description: Define, create, edit, inspect, or maintain Agent Factory Original, Processed, and Specification Documents while preserving loose provenance relationships and type-specific authority.
metadata:
  specification-id: document
  human-entry: .agent-factory/document/specification/document/index.html
  ai-root: skills/document/
---

# Agent Factory Document

## Entry contract

Use this Skill to define or maintain Documents and their type-specific
contracts. `Document` is the neutral umbrella for exactly three active types:

- **Original (원본문서):** source-faithful evidence;
- **Processed (가공문서):** transformations and derived working knowledge;
- **Specification (스펙 문서):** accepted and reconciled project knowledge
  with faithful Human- and AI-facing representations.

Use the conceptual ordering `Original -> Processed -> Specification`, but treat
each arrow only as a possible derivation or evidence relationship. This is not
a mandatory pipeline, state machine, required transition, one-to-one mapping,
completeness or maturity claim, or automatic promotion mechanism. A Document
may remain in one type without producing another. Relationships may be absent,
one-to-many, many-to-one, or many-to-many. Preserve inspectable provenance when
a relationship exists.

Do not introduce Refined as a fourth active Document type or combine the three
active type names.

Gather owns external synchronization and may use a connector whose lifecycle
is prepared through Tool; Tool does not own or produce the resulting Original
Document. Document owns the definitions of all three types and work on
already-resolved Document targets. Explorer may create
Original or Processed Documents as bounded Work evidence, but it is a
Convention-owned capability, not a public Skill, and it does not accept or
reconcile Specification truth.

Ground every material claim in explicit Human instruction, accepted project
decisions, or inspected project evidence. Leave Human-owned priority,
deadline, owner, acceptance, risk acceptance, and completion state unresolved
unless the Human has decided them.

## Reference routing

- `references/original.md`: Read completely whenever creating, changing,
  inspecting, or reasoning about an Original Document. It owns source fidelity,
  identity, provenance, collection context, source-appropriate formats, and
  the boundary with Gather.
- `references/processed.md`: Read completely whenever creating, changing,
  inspecting, or reasoning about a Processed Document. It owns transformations,
  derived working knowledge, non-authoritative status, provenance
  relationships, and the local-adapter Markdown convention.
- `references/specification.md`: Read completely whenever creating, editing,
  redesigning, inspecting, or verifying a Specification. It owns accepted and
  reconciled project knowledge, honest unresolved state, the packaged browser
  template, the mandatory faithful Human/AI pair, and the complete AI-facing
  Project Skill representation contract.
- `references/adapter.md`: Read completely for any Document adapter
  initialization, inspection/planning, physical layout or backend migration,
  integrity-check, or recovery design or work. It distinguishes deterministic
  physical control from semantic Document work and defines the LLM boundary,
  closed plan/IR, fail-closed manager, pair publication, and ownership rules.

## Initialization and migration

Initialization and physical adapter/layout migration remain capabilities of
this public Skill, not another Skill or Agent role. Initialization is
deterministic and needs no LLM. Physical migration preserves `documentType`
and never implies `Original -> Processed -> Specification` promotion. An LLM
may advise on ambiguous classification, provenance, difficult transformations,
semantic reconciliation, or synchronized Specification drafts, but its raw
output is never executable. Only an allowlisted, versioned deterministic plan
compiled and validated from a proposal may reach a deterministic manager after
current-state revalidation and required Human authority. Keep uncertainty
`unknown` or `requiresDecision` and apply the complete contract in
`references/adapter.md`.

## Specification pair

A Specification is one semantic body with faithful Human- and AI-facing
representations. Always keep the two representations semantically synchronized.
A one-sided change is incomplete and unacceptable; if synchronization cannot
be achieved, do not report the change or run as completed. The Human-facing
representation is HTML, CSS, and JavaScript and must be authored in Korean. Its
paired AI-facing representation is a Skill and need not be Korean.

Use a uniform one-to-one pair: one resolved Skill directory and one
Specification directory with the same stable identity. In this plugin,
`skills/<skill-id>/` pairs with
`.agent-factory/document/specification/<skill-id>/`. In a consumer project the
pair uses the exact lowercase hyphen-case `<category>-<title>` identity on both
sides: `.codex/skills/<category>-<title>/` pairs with
`.agent-factory/document/specification/<category>-<title>/`. This plugin is the
explicit exception whose accepted single-name identities remain unchanged.
Never aggregate several Skills into one Specification, pair one Skill with
several Specifications, or mechanically copy a Skill tree into the Human view.
Map each material Human section to exact sources within its paired Skill.

## Boundaries

Keep Explorer working material, Documents, paired Skills, and managed Agent
session state in separate logical roles and resolved stores.
`.agent-factory/` is the current/default local document adapter, not a
universal canonical backend. An explicitly resolved project server, external
store, mounted filesystem, or other backend is permitted, but do not silently
choose, mirror, migrate, or claim implementation of one. Preserve Document
type, provenance, authority, isolation, semantic alignment, accessibility, and
security regardless of storage.

Locally materialized Human-facing Specifications live below
`.agent-factory/document/specification/`. The Human-facing control tower and
browser navigation belong to `workspace`, not Document. Do not silently
promote Explorer material, recreate retired schema/profile/manager machinery,
or introduce Intake, Work Unit, Work Package, Project Core, Recording Agent, or
platform subagent concepts.

Under the current local adapter, each immediate directory below
`document/original/`, `document/processed/`, or `document/specification/` is
exactly one Document package with that directory's stable identity. Internal
files and subdirectories belong to that package; producer, category, and legacy
wrapper layers are not Document packages. Preserved legacy Inquery packages
use direct `legacy-inquery-<legacy-id>` identities below `processed/` and remain
Processed Documents whose historical status is metadata, not another type.

For a new Specification, use the reusable files in `assets/document/` as the
starting point and follow the copy-once and placeholder-refinement workflow in
`references/specification.md`. The template is a flexible baseline for
Specifications, not a schema for every Document.

## Workspace projection

Every Human-facing Specification remains directly readable from its HTML entry
point. The `workspace` Skill may discover, navigate, and render Documents for
Human management, but that projection does not own their semantics, change
their type, or replace a Specification's required paired AI-facing
representation.
