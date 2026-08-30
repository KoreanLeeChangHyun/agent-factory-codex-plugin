<agent-factory>
Always load and comply with Agent Factory skills.

Use the six public Skills by responsibility: `agent` owns Agent execution,
Work/Verification capability binding, authority, orchestration, and receipts;
`convention` owns Agent rules, shared safety, least privilege, and approval
conventions; `document` defines and maintains Original, Processed, and
Specification Documents; `gather` owns bounded read-only external source
synchronization and its Original Document output; `tool` owns the logical
lifecycle/control contract for Agent-usable external tools and connectors; and
`workspace` is the Human control tower for managing Agents, documents, and the
project. Explorer and Interview remain capabilities, not separate public
Skills.

Treat Main as the Human-facing adaptive Interview, orchestration, and result
integration layer. Main performs no Work or Verification directly. Route every
bounded task, including research and implementation, to Work and route
independent checking to Verification unless the Human skips it. A failed
Verification returns to the same Work Agent; a pass or Human skip ends the
graph. Explorer is a Convention-owned capability applied within Work, not a
separate Agent role, and never impersonates or interviews the Human.

This repository is the Agent Factory plugin. Store this plugin's distributed
Skills below `<plugin-root>/skills/`; do not create or mirror them below this
repository's `.codex/`.

For every separate project that uses this plugin, store that project's
Project Skills below `<project-root>/.codex/skills/`. Keep each Project Skill in
one self-contained directory with `SKILL.md`, YAML Agent configuration in
`agents/`, reference material in `assets/`, Markdown documents in `references/`,
and Agent-usable scripts in `scripts/`.

Use this project-local structure as the current/default local adapter, not as a
universal document-storage requirement:

```text
<project-root>/.agent-factory/
├── db.sqlite
├── agent/
│   └── <agent-id>/
│       ├── session.json
│       └── runs/
│           └── <run-id>/
├── document/
│   ├── original/
│   ├── processed/
│   ├── specification/
│   │   └── human/
│   └── sync.json
└── workspace/
│   ├── common/
│   ├── explorer/
│   └── skills/
```

Use the exact `db.sqlite` path for the current/default local adapter's shared,
rebuildable, non-authoritative catalog/read model across Agent execution
structure and Documents. It does not own or replace the authoritative files or
stores it projects. Its maintained schema asset is
`skills/workspace/assets/schema/catalog.sql`; the database and SQLite runtime
sidecars are local generated artifacts and must not be committed.

Keep operational Agent runtime state in `agent/`. Keep temporary execution-only
Explorer material in the producing managed Agent run. Classify durable Explorer
evidence as an Original or Processed Document under `document/`. Keep Gather
configuration in `document/sync.json`. Use `document/` for
the three Document types: Original, Processed, and Specification. Their
conceptual ordering is `Original -> Processed -> Specification`, but each arrow
is only a possible derivation or evidence relationship. The types are not a
mandatory pipeline, state machine, required transition, maturity scale, or
one-to-one mapping. A Document may remain in one type; relationships may be
absent or have any cardinality. Preserve inspectable provenance when a
relationship exists without inferring completeness or automatic promotion.
Original Documents may retain diverse source-native formats;
preserve source fidelity, identity, provenance, collection context, and a
native or source-appropriate form instead of imposing a canonical file format.
In this local adapter, active Processed Documents are Markdown (`.md`), while
Processed remains a logical, storage-independent Document type. Store locally
materialized Human-facing Specifications below `document/specification/human/`.
Preserved legacy Inquery artifacts live below
`document/processed/legacy-inquery/`; do not use them as active targets.
Within the local adapter's `workspace/`, `common/` owns the shared browser
shell, `.agent-factory/workspace/explorer/` owns an internal read-only
File/Project metadata projection, and `skills/` owns internal read-only Skill
navigation. These stores define neither an Activity nor nesting under one of
the five Activities. The Explorer projection discovers and displays the project
and classified Document trees without copying or becoming the canonical owner
of either; temporary Explorer material remains in its producing managed Agent
run.
Workspace reads Human-facing Specifications from `document/specification/human/` rather
than owning a document directory.

A Specification is accepted and reconciled project knowledge represented as
one semantic body with two faithful
representations: an AI-facing Skill and a Human-facing Korean HTML, CSS, and
JavaScript document. The pair must always remain semantically synchronized; a
one-sided change is incomplete and unacceptable. If both representations
cannot be synchronized, do not report the change or run as completed. This
plugin repository's Agent Factory core pair is owned by the distributed
`skills/convention/` Skill. A separate consumer project's pair is a Project
Skill below that project's `.codex/skills/`. Do not create a standalone
Human-facing Specification without its resolved pair.

Original, Processed, and Specification Document types and document roles are
logical and storage-independent. Do not introduce Refined as a fourth active
type or combine the three active type names.
An explicitly resolved alternative store, such as a project server, external
document store, mounted filesystem, or configured backend, may replace the
local document adapter while preserving provenance, authority, isolation,
semantic alignment, accessibility, and security. Do not silently choose,
mirror, or migrate a backend. Keep operational Agent runtime state under the
declared local runtime contract unless separately changed. Do not put Project
Skills or gathered source collections below `.agent-factory/`; Gather uses its
resolved destination outside this work root.

Do not create `.agent-factory/tool/` or silently select a Tool registry or
state backend. Tool preserves the authority of each host, plugin, MCP server,
project manifest, or explicitly selected provider and records only logical
lifecycle metadata, never credentials or tokens. Gather declares connector
capability, minimum permission scope, Human-approval need, and selection bounds;
Tool must not escalate scope. Until concrete Tool connection/token and Gather
capability/scope interfaces exist, keep the observed Google Drive and OneDrive
authentication implementation in Gather and treat migration as unresolved.
</agent-factory>
